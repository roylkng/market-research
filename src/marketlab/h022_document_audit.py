"""Noncanonical document-comparability audit. Never imports or alters frozen P001 logic.

Metadata can establish a scheduling warning, never a complete transcript. Positive
content eligibility requires an exact-text-bound review. Review time is distinct
from the original information cutoff. This module performs no network requests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VERSION = "h022-document-comparability/1"
HASH = re.compile(r"^[0-9a-f]{64}$")
KINDS = {"FULL_TRANSCRIPT", "LINK_ONLY_NOTICE", "FUTURE_CALL_NOTICE", "OTHER", "INCOMPLETE"}
FUTURE_CALL = re.compile(
    r"\b(?:will\s+(?:hold|host|conduct)|(?:conference|earnings|analyst)\s+call\s+"
    r"(?:is\s+)?(?:scheduled|will\s+be\s+held))\b", re.I
)
FUTURE_TRANSCRIPT = re.compile(
    r"\btranscript\b.{0,160}?\b(?:will|shall)\b.{0,80}?"
    r"\b(?:published|uploaded|available|provided)\b", re.I
)
NOTICE = re.compile(r"\btranscript\b.{0,120}?\b(?:available|uploaded|website|link)\b", re.I)
FORBIDDEN = {"stock_price", "stock_return", "benchmark_return", "valuation", "momentum",
             "broker_target", "analyst_revision", "post_publication_news", "later_management_call"}


class AuditError(ValueError):
    """Invalid evidence, unsafe output location, or broken immutable linkage."""


def canonical_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise AuditError("non_finite_or_invalid_json") from exc
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError("duplicate_json_key")
        result[key] = value
    return result


def load_json(raw: bytes) -> dict[str, Any]:
    if len(raw) > 32 * 1024 * 1024:
        raise AuditError("input_too_large")
    def invalid(_: str) -> None:
        raise AuditError("non_finite_json")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=invalid)
    except (UnicodeError, ValueError) as exc:
        raise AuditError("invalid_json") from exc
    if not isinstance(doc, dict):
        raise AuditError("object_required")
    canonical_hash(doc)  # Reject exponent overflow as well as NaN/Infinity literals.
    return doc


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise AuditError("timezone_timestamp_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditError("invalid_timestamp") from exc
    if parsed.tzinfo is None:
        raise AuditError("timezone_timestamp_required")
    return parsed.astimezone(UTC)


def _hash(value: Any) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise AuditError("invalid_sha256")
    return value


def _sealed(value: dict[str, Any], key: str) -> None:
    if _hash(value.get(key)) != canonical_hash({k: v for k, v in value.items() if k != key}):
        raise AuditError("sealed_hash_mismatch")


def _outcome_free(value: Any) -> None:
    if isinstance(value, dict):
        if FORBIDDEN.intersection(value):
            raise AuditError("outcome_input_forbidden")
        if value.get("outcome_data_attached", False) is not False:
            raise AuditError("outcome_input_forbidden")
        if value.get("live_capital_allowed", False) is not False:
            raise AuditError("live_capital_forbidden")
        for item in value.values():
            _outcome_free(item)
    elif isinstance(value, list):
        for item in value:
            _outcome_free(item)


def _result(kind: str, eligibility: str, basis: str, reasons: list[str]) -> dict[str, Any]:
    return dict(document_kind=kind, eligibility=eligibility, evidence_basis=basis,
                reasons=reasons, full_document_verified=False)


def classify_document(source: dict[str, Any] | None, *, source_id: str, symbol: str,
                      published_at_utc: str, as_of_utc: str,
                      text: str | None = None, expected_text_sha256: str | None = None,
                      extraction_status: str = "NOT_SUPPLIED",
                      review: dict[str, Any] | None = None) -> dict[str, Any]:
    """Conservative shadow classification, not a replacement for H003-C001.

    A review is an auditable assertion by a reviewer, not a digital identity
    verification. Its text hash must match the retained artifact supplied by the
    caller. No keyword, filename, character count, or candidate count grants
    positive transcript eligibility. A full transcript may include a cover letter.
    """
    _hash(source_id)
    published, cutoff = timestamp(published_at_utc), timestamp(as_of_utc)
    if published > cutoff:
        return _result("AFTER_CUTOFF", "INELIGIBLE", "publication_timestamp",
                       ["source_published_after_original_cutoff"])
    if source is None:
        if text is not None or review is not None:
            raise AuditError("source_binding_required")
        return _result("UNKNOWN", "REVIEW_REQUIRED", "no_source_in_scoped_inventory",
                       ["source_content_not_reviewed"])
    if (source.get("source_id") != source_id or source.get("symbol") != symbol
            or timestamp(source.get("exchange_published_at_utc")) != published):
        raise AuditError("source_identity_mismatch")
    _outcome_free(source)
    announcement = " ".join(str(source.get("attachment_text", "")).split())
    future = bool(FUTURE_CALL.search(announcement) and FUTURE_TRANSCRIPT.search(announcement))
    flags = []
    if future:
        flags.append("announcement_schedules_call_and_defers_transcript")
    if "intimation" in str(source.get("attachment_url", "")).casefold():
        flags.append("filename_intimation_is_triage_only")
    if NOTICE.search(announcement):
        flags.append("announcement_link_or_availability_mention_is_not_document_body")

    if extraction_status not in {"NOT_SUPPLIED", "TEXT_READY", "FAILED"}:
        raise AuditError("unsupported_extraction_status")
    if extraction_status == "FAILED":
        if text is not None or review is not None:
            raise AuditError("failed_extraction_has_content")
        return _result("EXTRACTION_FAILED", "REVIEW_REQUIRED", "extraction_status",
                       flags + ["extraction_failure_is_not_zero_commitments"])
    if text is None:
        if review is not None:
            raise AuditError("review_requires_exact_text")
        if future:
            return _result("FUTURE_CALL_NOTICE", "INELIGIBLE", "retained_announcement_only",
                           flags + ["attachment_body_not_independently_reviewed"])
        return _result("UNKNOWN", "REVIEW_REQUIRED", "retained_announcement_only",
                       flags + ["transcript_completeness_not_established"])
    if extraction_status != "TEXT_READY" or not text.strip():
        raise AuditError("nonempty_ready_text_required")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != _hash(expected_text_sha256):
        raise AuditError("text_digest_mismatch")
    if review is None:
        return _result("UNREVIEWED_CONTENT", "REVIEW_REQUIRED", "hash_verified_text",
                       flags + ["positive_content_review_required"])
    required = {"source_id", "text_sha256", "document_kind", "reviewed_at_utc", "reviewer_ref",
                "evidence_ref", "call_at_utc"}
    if set(review) != required or review.get("document_kind") not in KINDS:
        raise AuditError("invalid_review_contract")
    if review["source_id"] != source_id or review["text_sha256"] != expected_text_sha256:
        raise AuditError("review_binding_mismatch")
    if any(not isinstance(review[k], str) or not review[k].strip()
           for k in ("reviewer_ref", "evidence_ref")):
        raise AuditError("review_provenance_required")
    if timestamp(review["reviewed_at_utc"]) < published:
        raise AuditError("review_predates_source")
    kind = review["document_kind"]
    if kind == "FULL_TRANSCRIPT":
        call = timestamp(review["call_at_utc"])
        if call > published or call > cutoff:
            return _result("EVENT_AFTER_PUBLICATION", "INELIGIBLE", "exact_text_bound_review",
                           flags + ["call_cannot_postdate_its_transcript"])
        if future:
            return _result("METADATA_CONTENT_CONFLICT", "REVIEW_REQUIRED",
                           "exact_text_bound_review", flags + ["resolve_source_content_conflict"])
        result = _result(kind, "ELIGIBLE", "exact_text_bound_review", ["complete_call_reviewed"])
        result["full_document_verified"] = True
    else:
        result = _result(kind, "INELIGIBLE" if kind != "INCOMPLETE" else "REVIEW_REQUIRED",
                         "exact_text_bound_review", ["not_a_complete_management_call_transcript"])
    result["reviewed_at_utc"] = review["reviewed_at_utc"]
    result["reviewer_ref"] = review["reviewer_ref"]
    result["evidence_ref"] = review["evidence_ref"]
    return result


def compare_documents(current: dict[str, Any], prior: dict[str, Any], *,
                      frozen_primary_signal: float | None) -> dict[str, Any]:
    """Interpretation only. Both sides must be eligible. Null is never replaced by zero."""
    if frozen_primary_signal is not None and (
        isinstance(frozen_primary_signal, bool) or not isinstance(frozen_primary_signal, (int, float))
        or not math.isfinite(frozen_primary_signal)
    ):
        raise AuditError("invalid_signal_value")
    states = (current.get("eligibility"), prior.get("eligibility"))
    if any(s not in {"ELIGIBLE", "INELIGIBLE", "REVIEW_REQUIRED"} for s in states):
        raise AuditError("invalid_eligibility")
    if "INELIGIBLE" in states:
        status = "NOT_COMPARABLE"
    elif "REVIEW_REQUIRED" in states:
        status = "REVIEW_REQUIRED"
    elif frozen_primary_signal is None:
        status = "NO_FROZEN_NUMERIC_SIGNAL"
    else:
        status = "COMPARABLE_DOCUMENTS_ONLY"
    return dict(comparability=status,
                advisory_primary_signal=frozen_primary_signal if status == "COMPARABLE_DOCUMENTS_ONLY"
                else None, canonical_signal_replacement=False, canonical_outcome_scoring_changed=False)


def _ledger(doc: dict[str, Any], record_hash_key: str) -> dict[str, dict[str, Any]]:
    _outcome_free(doc)
    _sealed(doc, "ledger_sha256")
    if doc.get("protocol_id") != "H022-P001" or doc.get("hypothesis_id") != "H022":
        raise AuditError("unsupported_protocol")
    records = doc.get("records")
    if not isinstance(records, list) or type(doc.get("record_count")) is not int:
        raise AuditError("record_count_required")
    if len(records) != doc["record_count"]:
        raise AuditError("record_count_mismatch")
    mapped = {}
    for item in records:
        if not isinstance(item, dict):
            raise AuditError("record_object_required")
        _sealed(item, record_hash_key)
        source = item.get("source", item)
        sid = _hash(source.get("source_id"))
        if sid in mapped:
            raise AuditError("duplicate_source_id")
        mapped[sid] = item
    return mapped


def audit_snapshot(signal_raw: bytes, source_raw: bytes, *, snapshot_commit: str,
                   reviewed_at_utc: str, previous_audit: dict[str, Any] | None = None
                   ) -> dict[str, Any]:
    """Audit every row in supplied frozen ledgers using metadata, including prior links.

    The CLI deliberately has no facility to insert newly fetched transcripts into
    P001. Missing historical source content is reported, never guessed from counts.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", snapshot_commit):
        raise AuditError("pinned_commit_required")
    review_time = timestamp(reviewed_at_utc)
    signals, sources = load_json(signal_raw), load_json(source_raw)
    sm = _ledger(signals, "signal_record_sha256")
    src = _ledger(sources, "source_record_sha256")
    for field in ("cohort_id", "cohort_sha256"):
        if signals.get(field) != sources.get(field):
            raise AuditError("cohort_mismatch")
    if set(sm) - set(src):
        raise AuditError("current_source_missing_from_ledger")
    previous_hash = None
    if previous_audit is not None:
        _sealed(previous_audit, "audit_sha256")
        if (previous_audit.get("protocol_id") != "H022-P001"
                or previous_audit.get("audit_version") != VERSION
                or previous_audit.get("cohort_sha256") != signals["cohort_sha256"]):
            raise AuditError("previous_audit_scope_mismatch")
        if review_time < timestamp(previous_audit.get("reviewed_at_utc")):
            raise AuditError("review_time_rollback")
        previous_hash = previous_audit["audit_sha256"]
    annotations = []
    prior_ids = set()
    for sid, signal in sm.items():
        cutoff = signal["signal_frozen_at_utc"]
        if review_time < timestamp(cutoff):
            raise AuditError("audit_cannot_predate_frozen_record")
        published = timestamp(signal["exchange_published_at_utc"])
        first_seen = timestamp(src[sid]["first_seen_at_utc"])
        if not published <= first_seen <= timestamp(cutoff):
            raise AuditError("current_source_time_binding_mismatch")
        current = classify_document(src[sid]["source"], source_id=sid, symbol=signal["symbol"],
                                    published_at_utc=signal["exchange_published_at_utc"],
                                    as_of_utc=cutoff)
        pid = signal.get("prior_source_id")
        if pid is None:
            prior = _result("NO_UNIQUE_FROZEN_PRIOR", "REVIEW_REQUIRED", "frozen_prior_selection",
                            ["no_prior_substitution_permitted"])
        else:
            _hash(pid)
            prior_ids.add(pid)
            if signal.get("prior_group_source_ids") != [pid]:
                raise AuditError("prior_group_binding_mismatch")
            if timestamp(signal["prior_exchange_published_at_utc"]) >= published:
                raise AuditError("prior_not_strictly_earlier")
            if pid in src and timestamp(src[pid]["first_seen_at_utc"]) > timestamp(cutoff):
                raise AuditError("prior_first_seen_after_cutoff")
            prior = classify_document(src[pid]["source"] if pid in src else None,
                                      source_id=pid, symbol=signal["symbol"],
                                      published_at_utc=signal["prior_exchange_published_at_utc"],
                                      as_of_utc=cutoff)
        annotations.append(dict(symbol=signal["symbol"], source_id=sid, prior_source_id=pid,
                                original_signal_record_sha256=signal["signal_record_sha256"],
                                original_signal_frozen_at_utc=cutoff,
                                original_primary_signal=signal.get("primary_signal"),
                                current=current, prior=prior,
                                **compare_documents(current, prior,
                                  frozen_primary_signal=signal.get("primary_signal"))))
    counts = Counter(row["comparability"] for row in annotations)
    provenance = []
    for name, raw, doc in (("signal-ledger.json", signal_raw, signals),
                           ("source-ledger.json", source_raw, sources)):
        provenance.append(dict(path="research/prospective/h022/P001/" + name,
                               git_blob_sha=hashlib.sha1(b"blob " + str(len(raw)).encode()
                                                        + b"\0" + raw).hexdigest(),
                               file_sha256=hashlib.sha256(raw).hexdigest(),
                               declared_ledger_sha256=doc["ledger_sha256"]))
    report = dict(audit_version=VERSION, protocol_id="H022-P001", snapshot_commit=snapshot_commit,
                  cohort_sha256=signals["cohort_sha256"], reviewed_at_utc=reviewed_at_utc,
                  previous_audit_sha256=previous_hash, advisory_only=True,
                  canonical_signal_replacement=False, canonical_outcome_scoring_changed=False,
                  live_capital_allowed=False, outcome_data_used=False,
                  scope="all supplied signals; source metadata only; both current and prior links",
                  source_metadata_count=len(src), signal_count=len(sm),
                  prior_source_count=len(prior_ids),
                  prior_source_metadata_missing_count=len(prior_ids - set(src)),
                  full_document_review_count=0, classification_counts=dict(sorted(counts.items())),
                  input_files=provenance, annotations=annotations)
    report["audit_sha256"] = canonical_hash(report)
    return report


def write_report(report: dict[str, Any], output: Path, repo_root: Path) -> None:
    """Create once. An identical retry is harmless; changed content is never overwritten."""
    _sealed(report, "audit_sha256")
    root, dest = repo_root.resolve(), output.resolve()
    allowed = root / "research" / "audits" / "h022" / "P001"
    if not dest.is_relative_to(allowed) or dest.suffix != ".json" or dest == allowed:
        raise AuditError("output_must_be_separate_audit_json")
    raw = (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
           + "\n").encode()
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Fully write before atomically publishing. link() refuses an existing name.
    fd, temporary = tempfile.mkstemp(prefix=".audit-", dir=dest.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, dest)
        except FileExistsError:
            if dest.read_bytes() != raw:
                raise AuditError("existing_audit_is_immutable") from None
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--snapshot-commit", required=True)
    parser.add_argument("--reviewed-at-utc")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--check", action="store_true", help="exit 2 when shadow review has blockers")
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    folder = root / "research/prospective/h022/P001"
    try:
        paths = (folder / "signal-ledger.json", folder / "source-ledger.json")
        before = tuple(path.read_bytes() for path in paths)
        report = audit_snapshot(*before, snapshot_commit=args.snapshot_commit,
                                reviewed_at_utc=args.reviewed_at_utc or datetime.now(UTC).isoformat(),
                                previous_audit=load_json(args.previous.read_bytes())
                                if args.previous else None)
        if tuple(path.read_bytes() for path in paths) != before:
            raise AuditError("inputs_changed_during_audit")
        write_report(report, args.output if args.output.is_absolute() else root / args.output, root)
        print(json.dumps(dict(audit_sha256=report["audit_sha256"],
                              signal_count=report["signal_count"],
                              classification_counts=report["classification_counts"],
                              frozen_inputs_unchanged=True, advisory_only=True), sort_keys=True))
        blocked = any(a["comparability"] != "COMPARABLE_DOCUMENTS_ONLY"
                      for a in report["annotations"])
        return 2 if args.check and blocked else 0
    except (AuditError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "audit_written": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
