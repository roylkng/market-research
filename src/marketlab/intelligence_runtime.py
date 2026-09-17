"""Company-centred integration of evidence, source health and research gaps.

The report deliberately abstains from ranking investments or forecasting prices.
Only acquired source bytes can produce extracted company facts.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import requests

from marketlab.intelligence_core import Evidence, EvidenceError, active_evidence
from marketlab.intelligence_sources import (
    PublicFetcher, SourceBlocked, extract_claims, normalized_html, parse_rss,
    publication_upper_bound,
)
from marketlab.intelligence_store import (
    FACETS, ResearchStore, canonical, digest, now_text, timestamp,
)


def serializable_evidence(evidence: Evidence) -> dict:
    result = asdict(evidence)
    for key in ("published_at", "first_seen_at", "processed_at", "expires_at"):
        result[key] = result[key].isoformat()
    return result


def decode_evidence(row: dict) -> Evidence:
    payload = dict(row["evidence"])
    for key in ("published_at", "first_seen_at", "processed_at", "expires_at"):
        payload[key] = timestamp(payload[key])
    return Evidence(**payload)


def collect_source(store: ResearchStore, source: dict, panel: dict,
                   fetcher: PublicFetcher) -> dict:
    started = now_text()
    source_id = source["source_id"]
    run = {"source_id": source_id, "source_spec_sha256": digest(source),
           "started_at": started, "url": source["url"],
           "scope": source.get("subject", "RADAR:NSE"),
           "window_complete": False, "discovery_kind": source["kind"]}
    try:
        raw, response = fetcher.fetch(source["url"])
        raw_hash = store.save_object(raw)
        run.update(response)
        run["raw_sha256"] = raw_hash
        if not raw:
            raise EvidenceError("Empty source body")
        if source["kind"] == "rss":
            leads = parse_rss(raw, members=panel["members"], source_id=source_id,
                              observed_at=response["observed_at"])
            # A repeated item preserves the original observation timestamp.
            existing = {r["lead_id"]: r for r in store.records("lead")}
            new_count = 0
            for lead in leads:
                if lead["lead_id"] not in existing:
                    store.append("lead", lead["lead_id"], lead)
                    new_count += 1
            run.update(status="FEED_SNAPSHOT_ONLY", item_count=len(leads),
                       new_item_count=new_count,
                       identity_counts=dict(Counter(r["identity_state"] for r in leads)))
        elif source["kind"] == "html":
            if "html" not in response["content_type"].lower():
                raise EvidenceError("Expected an HTML source, received another content type")
            if source["subject"] not in {r["symbol"] for r in panel["members"]}:
                raise EvidenceError("Company source is outside this deep panel")
            text = normalized_html(raw)
            text_hash = store.save_object(text.encode())
            processed = now_text()
            claims = extract_claims(text, source)
            publication = publication_upper_bound(source)
            if claims and publication is None:
                raise EvidenceError("Financial claims require a reviewed publication date")
            document_id = digest([source_id, raw_hash, text_hash, digest(source)])
            prior_docs = {r["document_id"]: r for r in store.records("document")}
            if document_id in prior_docs:
                document = prior_docs[document_id]
            else:
                document = {"document_id": document_id, "source_id": source_id,
                            "subject": source["subject"], "raw_sha256": raw_hash,
                            "text_sha256": text_hash, "source_url": response["resolved_url"],
                            "publication_upper_bound": publication,
                            "publication_precision": "DAY" if publication else "UNKNOWN",
                            "first_seen_at": response["observed_at"], "processed_at": processed,
                            "source_spec_sha256": digest(source), "claims": claims}
                store.append("document", document_id, document)
            for claim in document["claims"]:
                if text[claim["span_start"]:claim["span_end"]] != claim["quote"]:
                    raise EvidenceError("Claim quote does not match retained text span")
                claim_id = digest([document_id, claim])
                evidence = Evidence(
                    identifier=claim_id, subject=source["subject"], facet=claim["facet"],
                    claim_key=canonical({k: claim[k] for k in
                        ("concept", "period_end", "unit", "currency", "basis")}),
                    value=claim["value"], role=claim["role"], publisher=source["publisher"],
                    origin=source.get("origin_id", source_id),
                    source_url=document["source_url"], content_sha256=document["raw_sha256"],
                    published_at=timestamp(document["publication_upper_bound"]),
                    first_seen_at=timestamp(document["first_seen_at"]),
                    processed_at=timestamp(document["processed_at"]),
                    # Snapshot review expires. This does not make old financial periods current.
                    expires_at=timestamp(document["processed_at"]) + timedelta(days=7),
                    quote=claim["quote"],
                )
                store.append("evidence", claim_id, {"evidence": serializable_evidence(evidence),
                    "document_id": document_id, "source_id": source_id,
                    "concept": claim["concept"], "unit": claim["unit"],
                    "currency": claim["currency"], "basis": claim["basis"],
                    "period_end": claim["period_end"], "span_start": claim["span_start"],
                    "span_end": claim["span_end"]})
            run.update(status="DOCUMENT_PARSED" if claims else "DOCUMENT_INDEX_ONLY",
                       document_id=document_id, claim_count=len(document["claims"]))
        else:
            raise EvidenceError("Unsupported source kind")
    except SourceBlocked as exc:
        run.update(status="SOURCE_BLOCKED", error=str(exc))
    except requests.RequestException as exc:
        # Never print response bodies, credentials or session state into reports.
        run.update(status="FETCH_FAILED", error=type(exc).__name__)
    except (EvidenceError, ValueError, UnicodeError) as exc:
        run.update(status="PARSE_FAILED", error=str(exc))
    except Exception as exc:
        # Preserve the attempted source and fail the overall run explicitly.
        run.update(status="INTERNAL_ERROR", error=type(exc).__name__)
    run["completed_at"] = now_text()
    run["attempt_id"] = digest(run)
    store.append("attempt", run["attempt_id"], run)
    return run


def _coverage(facet: str, configured: list[dict], attempts: list[dict],
              claims: list[dict], as_of: str) -> dict:
    sources = [s for s in configured if facet in s.get("facets", [])]
    scoped_attempts = [a for a in attempts if a["source_id"] in {s["source_id"] for s in sources}]
    latest = {}
    for row in sorted(scoped_attempts, key=lambda r: (timestamp(r["completed_at"]), r["attempt_id"])):
        latest[row["source_id"]] = row
    state = "NOT_COLLECTED"
    if latest:
        failures = [r["status"] for r in latest.values() if r["status"] in
                    {"SOURCE_BLOCKED", "FETCH_FAILED", "PARSE_FAILED", "INTERNAL_ERROR"}]
        if failures:
            state = "DEGRADED_SOURCE"
        elif any(timestamp(as_of) - timestamp(r["completed_at"]) > timedelta(days=1)
                 for r in latest.values()):
            state = "STALE_SOURCE_SNAPSHOT"
        else:
            state = "PARTIAL_SOURCE_COVERAGE"
    return {"facet": facet, "state": state, "window_complete": False,
            "configured_source_ids": sorted(s["source_id"] for s in sources),
            "source_states": {key: val["status"] for key, val in sorted(latest.items())},
            "active_claim_count": sum(r["evidence"]["facet"] == facet for r in claims)}


def _mechanisms(subject: str, configs: list[dict], claims: list[dict]) -> list[dict]:
    indexed = {}
    for row in claims:
        indexed.setdefault((row["source_id"], row["concept"]), []).append(row)
    output = []
    for spec in configs:
        if spec["subject"] != subject:
            continue
        refs, missing = [], []
        for requested in spec["requires"]:
            candidates = indexed.get((requested["source_id"], requested["concept"]), [])
            if len(candidates) != 1:
                missing.append(requested)
            else:
                refs.append(candidates[0]["evidence"]["identifier"])
        output.append({**spec, "status": "EVIDENCE_LINKED_HYPOTHESIS" if not missing else
                       "BLOCKED_MISSING_OR_AMBIGUOUS_EVIDENCE", "evidence_ids": sorted(refs),
                       "missing_evidence": missing, "probability": None})
    return output


def compare_reported_values(spec: dict, claims: list[dict]) -> dict:
    """No cross-basis growth arithmetic and no invented independent expectations."""
    result = {**spec, "value": None, "status": "MISSING_OR_AMBIGUOUS_INPUT"}
    pair = []
    for source in (spec["current"], spec["prior"]):
        rows = [r for r in claims if r["source_id"] == source
                and r["concept"] == spec["concept"]]
        if len(rows) != 1:
            return result
        pair.append(rows[0])
    current, prior = pair
    result["evidence_ids"] = [r["evidence"]["identifier"] for r in pair]
    if any(current[k] != prior[k] for k in ("unit", "currency", "basis")):
        return {**result, "status": "BASIS_UNIT_OR_CURRENCY_MISMATCH"}
    if current["period_end"] <= prior["period_end"]:
        return {**result, "status": "INVALID_PERIOD_ORDER"}
    try:
        a, b = (Decimal(r["evidence"]["value"]) for r in pair)
        if not a.is_finite() or not b.is_finite():
            raise InvalidOperation
        if spec["operation"] == "growth_pct":
            if b <= 0:
                return {**result, "status": "NONPOSITIVE_BASE"}
            value = (a / b - 1) * 100
        elif spec["operation"] == "difference_pp" and current["unit"] == "percent":
            value = a - b
        else:
            return {**result, "status": "UNSUPPORTED_OPERATION"}
    except InvalidOperation:
        return {**result, "status": "INVALID_NUMERIC_INPUT"}
    return {**result, "status": "OBSERVED_ARITHMETIC_NOT_EXPECTATIONS_SURPRISE",
            "value": str(value), "current_period": current["period_end"],
            "prior_period": prior["period_end"]}


def build_report(store: ResearchStore, panel: dict, config: dict, *, as_of: str) -> dict:
    cutoff = timestamp(as_of)
    all_evidence = store.records("evidence")
    active_ids = {row.identifier for row in active_evidence(
        [decode_evidence(r) for r in all_evidence], cutoff)}
    visible = [r for r in all_evidence if r["evidence"]["identifier"] in active_ids]
    attempts = [r for r in store.records("attempt") if timestamp(r["completed_at"]) <= cutoff]
    leads = [r for r in store.records("lead") if timestamp(r["first_seen_at"]) <= cutoff]
    packets, tasks = [], []
    for member in panel["members"]:
        subject = member["symbol"]
        facts = [r for r in visible if r["evidence"]["subject"] == subject]
        configured = [s for s in config["sources"] if s.get("subject") in (subject, "RADAR:NSE")]
        coverage = [_coverage(f, configured, attempts, facts, as_of) for f in FACETS]
        mechanisms = _mechanisms(subject, config.get("mechanisms", []), facts)
        conflicts = []
        groups = {}
        for row in facts:
            if row["evidence"]["role"] == "REPORTED_FACT":
                groups.setdefault(row["evidence"]["claim_key"], []).append(row)
        for key, group in groups.items():
            if len({r["evidence"]["value"] for r in group}) > 1:
                conflicts.append({"claim_key": key,
                                  "evidence_ids": [r["evidence"]["identifier"] for r in group]})
        packet = {**member, "as_of": as_of, "research_state": "PARTIAL_RESEARCH",
                  "evidence": facts, "coverage": coverage, "mechanisms": mechanisms,
                  "conflicts": conflicts,
                  "comparisons": [compare_reported_values(c, facts) for c in
                                  config.get("comparisons", []) if c["subject"] == subject],
                  "discovery_lead_ids": [r["lead_id"] for r in leads if subject in r["symbols"]],
                  "forecast": None, "investment_rank": None,
                  "forecast_status": "NO_VALIDATED_FORECAST_MODEL", "live_capital_allowed": False}
        packet["packet_sha256"] = digest(packet)
        packets.append(packet)
        # A task queue is not a stock rank. Every missing facet remains visible.
        for row in coverage:
            tasks.append({"symbol": subject, "facet": row["facet"],
                          "reason": row["state"], "task": "COMPLETE_SOURCE_COVERAGE_AND_REVIEW",
                          "investment_recommendation": False})
    report = {"schema_version": 1, "engine": "COMPANY_INTELLIGENCE_V2_SLICE1",
              "as_of": as_of, "panel_id": panel["panel_id"], "panel_sha256": digest(panel),
              "configuration_sha256": digest(config), "company_count": len(packets),
              "companies_with_extracted_evidence": sum(bool(p["evidence"]) for p in packets),
              "active_evidence_count": len(visible), "source_attempts": attempts,
              "source_status_counts": dict(Counter(r["status"] for r in attempts)),
              "radar": {"observed_lead_count": len(leads),
                        "identity_counts": dict(Counter(r["identity_state"] for r in leads)),
                        "coverage": "FEED_SNAPSHOT_ONLY_NOT_EXCHANGE_WIDE_COMPLETENESS"},
              "packets": packets, "research_queue": tasks,
              "market_snapshot": None, "forecast_model": None,
              "legacy_experiments_modified": False, "live_capital_allowed": False}
    report["report_sha256"] = digest(report)
    return report


def render_report(report: dict) -> str:
    lines = ["# MarketLab v2 company research", "", f"Evidence cutoff: {report['as_of']}", "",
             f"Companies registered: {report['company_count']}. Companies with extracted evidence: "
             f"{report['companies_with_extracted_evidence']}.",
             "No investment ranking, return forecast or live-capital permission.", "",
             "## Acquisition", "", "| Source | Result | Claims/items |", "|---|---|---:|"]
    for row in report["source_attempts"]:
        lines.append(f"| {row['source_id']} | {row['status']} | "
                     f"{row.get('claim_count', row.get('item_count', 0))} |")
    lines += ["", "## Company evidence", ""]
    for packet in report["packets"]:
        if not packet["evidence"] and not packet["mechanisms"]:
            continue
        lines += [f"### {packet['symbol']}", "", "| Reported metric | Value | Basis | Source |",
                  "|---|---:|---|---|"]
        for fact in packet["evidence"]:
            e = fact["evidence"]
            lines.append(f"| {fact['concept']} ({fact['period_end']}) | {e['value']} {fact['unit']} | "
                         f"{fact['basis']} | {e['source_url']} |")
        for comp in packet["comparisons"]:
            lines += ["", f"Comparison {comp['concept']}: {comp['status']}, value={comp['value']}"]
        for mechanism in packet["mechanisms"]:
            lines += ["", f"**{mechanism['status']}**: {mechanism['event']}",
                      mechanism["economic_channel"],
                      f"Countercase: {mechanism['countercase']}",
                      f"Invalidation: {mechanism['invalidation']}",
                      f"Expectations: {mechanism['expectations']}"]
        lines += ["", "Coverage: " + ", ".join(
            f"{c['facet']}={c['state']}" for c in packet["coverage"]), ""]
    lines += ["## Remaining research", "",
              "All 100 companies have nine explicit coverage slots. Identity registration is not "
              "completed fundamental analysis. Individual document snapshots do not prove complete "
              "news coverage. Social, market-price, independent expectations and valuation adapters "
              "are not connected in this slice.", "",
              f"Report SHA-256: `{report['report_sha256']}`", ""]
    return "\n".join(lines)


def export_report(report: dict, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    # Use content-addressed output: repeated snapshots never overwrite earlier research.
    identity = report["report_sha256"]
    for suffix, text in (("json", canonical(report) + "\n"), ("md", render_report(report))):
        path = destination / f"report-{identity}.{suffix}"
        if path.exists() and path.read_text() != text:
            raise EvidenceError("Conflicting immutable report output")
        path.write_text(text)
