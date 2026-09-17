"""Explicit reviewed excerpts, never misrepresented as original-source bytes.

This import boundary trusts the reviewer to have checked the cited source. It
validates structure and provenance, not truth, completeness or independent audit.
The persisted import time always prevents historical decision backdating.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from marketlab.intelligence_core import Evidence, EvidenceError
from marketlab.intelligence_runtime import build_report, serializable_evidence
from marketlab.intelligence_sources import approved_url, publication_upper_bound
from marketlab.intelligence_store import (
    FACETS,
    ResearchStore,
    canonical,
    digest,
    now_text,
    timestamp,
)

METHOD = "WEB_ASSISTED_EXCERPT"


def import_reviewed_capture(store: ResearchStore, capture: dict, panel: dict) -> dict:
    if capture.get("capture_method") != METHOD:
        raise EvidenceError("Only explicitly labelled reviewed excerpts are accepted")
    if capture.get("original_document_bytes_retained") is not False or capture.get(
            "original_document_sha256") is not None:
        raise EvidenceError("An excerpt cannot claim original-document bytes or hash")
    if capture.get("window_complete") is not False:
        raise EvidenceError("A reviewed excerpt cannot prove complete source coverage")
    required = ("source_id", "subject", "publisher", "source_url", "reviewed_by", "source_locator")
    if any(not isinstance(capture.get(k), str) or not capture[k].strip() for k in required):
        raise EvidenceError("Reviewed source identity and locator are required")
    if capture["subject"] not in {r["symbol"] for r in panel["members"]}:
        raise EvidenceError("Reviewed company is outside this panel")
    approved_url(capture["source_url"])
    imported_at = now_text()
    if timestamp(capture["observed_at"]) > timestamp(imported_at):
        raise EvidenceError("Review observation is in the future")
    claims = capture.get("claims")
    if not isinstance(claims, list) or not claims:
        raise EvidenceError("Reviewed numeric capture needs explicit claims")
    # Small quotations support audit without archiving third-party article text.
    if sum(len(c.get("quote", "").split()) for c in claims) > 25:
        raise EvidenceError("Reviewed capture exceeds short-excerpt allowance")
    seen = set()
    for claim in claims:
        for key in ("concept", "facet", "period_end", "unit", "currency", "basis", "value", "quote"):
            if not isinstance(claim.get(key), str) or not claim[key].strip():
                raise EvidenceError(f"Reviewed claim lacks {key}")
        if claim["facet"] not in FACETS or claim.get("role") not in {
                "REPORTED_FACT", "MANAGEMENT_GUIDANCE", "EXTERNAL_ESTIMATE"}:
            raise EvidenceError("Unsupported reviewed claim facet or role")
        date.fromisoformat(claim["period_end"])
        identity = tuple(claim[k] for k in ("concept", "period_end", "unit", "currency", "basis"))
        if identity in seen:
            raise EvidenceError("Duplicate reviewed claim identity")
        seen.add(identity)
        try:
            value = Decimal(claim["value"])
            numbers = {Decimal(v.replace(",", "")) for v in re.findall(
                r"(?<!\w)[+-]?\d[\d,]*(?:\.\d+)?", claim["quote"])}
        except InvalidOperation as exc:
            raise EvidenceError("Invalid reviewed numeric value") from exc
        if not value.is_finite() or value not in numbers:
            raise EvidenceError("Reviewed numeric value is not present in the excerpt")
    capture_id = digest(capture)
    prior = next((r for r in store.records("reviewed_capture") if r["capture_id"] == capture_id), None)
    if prior is not None:
        imported_at = prior["imported_at"]
    excerpts = "\n".join(c["quote"] for c in claims)
    excerpt_hash = store.save_object(excerpts.encode())
    known_publication = publication_upper_bound(capture)
    published_at = known_publication or imported_at
    prepared = []
    offset = 0
    for claim in claims:
        identifier = digest([capture_id, claim])
        evidence = Evidence(
            identifier=identifier, subject=capture["subject"], facet=claim["facet"],
            claim_key=canonical({k: claim[k] for k in
                ("concept", "period_end", "unit", "currency", "basis")}),
            value=claim["value"], role=claim["role"], publisher=capture["publisher"],
            origin=capture["source_id"], source_url=capture["source_url"],
            content_sha256=excerpt_hash, published_at=timestamp(published_at),
            first_seen_at=timestamp(capture["observed_at"]), processed_at=timestamp(imported_at),
            expires_at=max(timestamp(imported_at), timestamp(published_at)) + timedelta(days=7),
            quote=claim["quote"],
        )
        prepared.append({"evidence": serializable_evidence(evidence),
            "document_id": capture_id, "source_id": capture["source_id"],
            **{k: claim[k] for k in ("concept", "unit", "currency", "basis", "period_end")},
            "span_start": offset, "span_end": offset + len(claim["quote"]),
            "artifact_kind": METHOD, "content_hash_basis": "RETAINED_EXCERPTS_NOT_ORIGINAL_HTML",
            "original_document_sha256": None, "original_document_bytes_retained": False,
            "publication_precision": "DAY" if known_publication else "UNKNOWN",
            "reviewed_by": capture["reviewed_by"], "source_locator": capture["source_locator"]})
        offset += len(claim["quote"]) + 1
    receipt = {"capture_id": capture_id, "imported_at": imported_at,
               "capture": capture, "excerpt_sha256": excerpt_hash,
               "evidence_ids": [r["evidence"]["identifier"] for r in prepared],
               "coverage_completed": False, "automated_source_recovered": False}
    # All input/Evidence validation completes before any canonical record write.
    # Individual appends are idempotent, so interruption is recoverable by replay.
    store.append("reviewed_capture", capture_id, receipt)
    for row in prepared:
        store.append("evidence", row["evidence"]["identifier"], row)
    return receipt


def build_reviewed_report(store: ResearchStore, panel: dict, config: dict, *, as_of: str) -> dict:
    report = build_report(store, panel, config, as_of=as_of)
    report["reviewed_source_imports"] = [
        {"capture_id": r["capture_id"], "subject": r["capture"]["subject"],
         "source_id": r["capture"]["source_id"], "imported_at": r["imported_at"],
         "evidence_ids": r["evidence_ids"], "artifact_kind": METHOD,
         "original_document_sha256": None, "automated_source_recovered": False}
        for r in store.records("reviewed_capture") if timestamp(r["imported_at"]) <= timestamp(as_of)]
    report["reviewed_source_notice"] = (
        "Reviewed browser excerpts are not original source files, unattended acquisition, "
        "complete news coverage or independent human verification. Failed collectors remain failed.")
    report.pop("report_sha256")
    report["report_sha256"] = digest(report)
    return report
