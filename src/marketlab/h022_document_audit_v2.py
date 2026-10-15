"""Strict H022/P001 document-comparability audit v2.

Adds frozen-scope, E002 extraction, and local-Git snapshot binding around the
v1 shadow classifier. It does not modify prospective ledgers or outcome scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h022_document_audit import (
    AuditError,
    _sealed,
    audit_snapshot as audit_snapshot_v1,
    canonical_hash,
    compare_documents,
    load_json,
    timestamp,
    write_report,
)

VERSION = "h022-document-comparability/2"
PROTOCOL_ID = "H022-P001"
HYPOTHESIS_ID = "H022"
COHORT_ID = "FY27-Q2-2026-09-06"
COHORT_SHA256 = "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
SOURCE_RULE_ID = "H003-C001"
SOURCE_RULE_SHA256 = "a48e9cd1e1d56b69429696168fb1a2097b288d3179c7830ac79cbd8582835f0e"
PROSPECTIVE_START_UTC = "2026-09-14T18:30:00Z"
FEATURE_VERSION = "management_forward_information_delta_v1"
E002_RULE_ID = "H003-E002"
E002_RULE_SHA256 = "5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2"
PARSER_VERSION = "h003_pdf_text_v1"
PARSER_LIBRARY_VERSION = "6.17.0"
INPUT_PATHS = (
    "research/prospective/h022/P001/signal-ledger.json",
    "research/prospective/h022/P001/source-ledger.json",
    "research/prospective/h022/P001/e002-ledger.json",
)


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _require_equal(actual: Any, expected: Any, reason: str) -> None:
    if actual != expected:
        raise AuditError(reason)


def _validate_top_level(doc: dict[str, Any], *, kind: str) -> None:
    _sealed(doc, "ledger_sha256")
    _require_equal(doc.get("protocol_id"), PROTOCOL_ID, f"{kind}_protocol_drift")
    _require_equal(doc.get("hypothesis_id"), HYPOTHESIS_ID, f"{kind}_hypothesis_drift")
    _require_equal(doc.get("cohort_id"), COHORT_ID, f"{kind}_cohort_drift")
    _require_equal(doc.get("cohort_sha256"), COHORT_SHA256, f"{kind}_cohort_hash_drift")
    _require_equal(doc.get("schema_version"), 1, f"{kind}_schema_version_drift")
    _require_equal(doc.get("outcome_data_attached"), False, f"{kind}_outcome_data_forbidden")
    records = doc.get("records")
    if not isinstance(records, list) or doc.get("record_count") != len(records):
        raise AuditError(f"{kind}_record_count_mismatch")


def validate_frozen_scope(
    signals: dict[str, Any], sources: dict[str, Any], e002: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Require the exact frozen P001 identities before interpreting any document."""
    _validate_top_level(signals, kind="signal")
    _validate_top_level(sources, kind="source")
    _validate_top_level(e002, kind="e002")
    _require_equal(sources.get("source_rule_id"), SOURCE_RULE_ID, "source_rule_id_drift")
    _require_equal(sources.get("source_rule_sha256"), SOURCE_RULE_SHA256, "source_rule_hash_drift")
    _require_equal(sources.get("prospective_start_utc"), PROSPECTIVE_START_UTC, "source_start_drift")
    _require_equal(sources.get("live_capital_allowed"), False, "source_live_capital_forbidden")
    _require_equal(e002.get("prospective_start_utc"), PROSPECTIVE_START_UTC, "e002_start_drift")
    _require_equal(e002.get("live_capital_allowed"), False, "e002_live_capital_forbidden")

    source_map: dict[str, dict[str, Any]] = {}
    for record in sources["records"]:
        if not isinstance(record, dict) or not isinstance(record.get("source"), dict):
            raise AuditError("invalid_source_record")
        source = record["source"]
        sid = source.get("source_id")
        if not isinstance(sid, str) or sid in source_map:
            raise AuditError("duplicate_or_invalid_source_id")
        source_map[sid] = record

    extraction_map: dict[str, dict[str, Any]] = {}
    for record in e002["records"]:
        if not isinstance(record, dict):
            raise AuditError("invalid_e002_record")
        sid = record.get("source_id")
        if not isinstance(sid, str) or sid in extraction_map:
            raise AuditError("duplicate_or_invalid_e002_source_id")
        _require_equal(record.get("rule_id"), E002_RULE_ID, "e002_rule_id_drift")
        _require_equal(record.get("rule_sha256"), E002_RULE_SHA256, "e002_rule_hash_drift")
        _require_equal(record.get("parser_version"), PARSER_VERSION, "e002_parser_drift")
        _require_equal(
            record.get("parser_library_version"),
            PARSER_LIBRARY_VERSION,
            "e002_parser_library_drift",
        )
        status = record.get("status")
        if status not in {"TEXT_READY", "FAILED"}:
            raise AuditError("unsupported_e002_status")
        if status == "TEXT_READY":
            for key in ("raw_sha256", "text_sha256", "record_id"):
                value = record.get(key)
                if not isinstance(value, str) or len(value) != 64:
                    raise AuditError("invalid_e002_digest")
            if record.get("failure_reason") is not None:
                raise AuditError("ready_e002_has_failure_reason")
        extraction_map[sid] = record

    signal_ids: set[str] = set()
    for signal in signals["records"]:
        if not isinstance(signal, dict):
            raise AuditError("invalid_signal_record")
        _sealed(signal, "signal_record_sha256")
        _require_equal(signal.get("protocol_id"), PROTOCOL_ID, "signal_record_protocol_drift")
        _require_equal(signal.get("hypothesis_id"), HYPOTHESIS_ID, "signal_record_hypothesis_drift")
        _require_equal(signal.get("cohort_id"), COHORT_ID, "signal_record_cohort_drift")
        _require_equal(signal.get("cohort_sha256"), COHORT_SHA256, "signal_record_cohort_hash_drift")
        _require_equal(signal.get("feature_version"), FEATURE_VERSION, "signal_feature_version_drift")
        _require_equal(
            signal.get("source_disposition"),
            "PROSPECTIVE_SIGNAL_ELIGIBLE",
            "signal_source_disposition_drift",
        )
        sid = signal.get("source_id")
        if not isinstance(sid, str) or sid in signal_ids:
            raise AuditError("duplicate_or_invalid_signal_source")
        signal_ids.add(sid)
        source_record = source_map.get(sid)
        extraction = extraction_map.get(sid)
        if source_record is None or extraction is None:
            raise AuditError("signal_source_or_extraction_missing")
        source = source_record["source"]
        for key in ("symbol", "exchange_published_at_utc"):
            _require_equal(signal.get(key), source.get(key), f"signal_source_{key}_mismatch")
            _require_equal(signal.get(key), extraction.get(key), f"signal_e002_{key}_mismatch")
        _require_equal(
            signal.get("source_record_id"), extraction.get("record_id"), "signal_e002_record_id_mismatch"
        )
        _require_equal(signal.get("raw_sha256"), extraction.get("raw_sha256"), "signal_e002_raw_mismatch")
        _require_equal(signal.get("text_sha256"), extraction.get("text_sha256"), "signal_e002_text_mismatch")
        _require_equal(
            source.get("attachment_url"), extraction.get("attachment_url"), "source_e002_url_mismatch"
        )
        if extraction.get("status") != "TEXT_READY":
            raise AuditError("sealed_signal_depends_on_nonready_extraction")

    if signal_ids != set(source_map) or signal_ids != set(extraction_map):
        raise AuditError("current_inventory_set_mismatch")
    return extraction_map


def verify_git_snapshot(
    repo_root: Path, snapshot_commit: str, raws: tuple[bytes, bytes, bytes]
) -> dict[str, str]:
    """Authenticate the caller-supplied commit against the local checkout and exact blobs."""
    root = repo_root.resolve()
    if len(snapshot_commit) != 40 or any(c not in "0123456789abcdef" for c in snapshot_commit):
        raise AuditError("pinned_commit_required")

    def git(*args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise AuditError("git_snapshot_verification_failed") from exc
        return result.stdout.strip()

    resolved = git("rev-parse", f"{snapshot_commit}^{commit}")
    _require_equal(resolved, snapshot_commit, "snapshot_commit_resolution_mismatch")
    observed: dict[str, str] = {}
    for path, raw in zip(INPUT_PATHS, raws, strict=True):
        expected = git("rev-parse", f"{snapshot_commit}:{path}")
        actual = _git_blob_sha(raw)
        _require_equal(actual, expected, "working_file_differs_from_pinned_blob")
        observed[path] = expected
    return observed


def _validate_previous(previous: dict[str, Any], report: dict[str, Any], review_time: datetime) -> str:
    _sealed(previous, "audit_sha256")
    for key in ("protocol_id", "cohort_sha256", "scope_identity_sha256"):
        _require_equal(previous.get(key), report.get(key), "previous_audit_scope_mismatch")
    if previous.get("audit_version") != VERSION:
        raise AuditError("previous_audit_version_mismatch")
    if review_time < timestamp(previous.get("reviewed_at_utc")):
        raise AuditError("review_time_rollback")
    return previous["audit_sha256"]


def audit_snapshot(
    signal_raw: bytes,
    source_raw: bytes,
    e002_raw: bytes,
    *,
    snapshot_commit: str,
    reviewed_at_utc: str,
    git_blob_shas: dict[str, str] | None = None,
    previous_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    signals, sources, e002 = map(load_json, (signal_raw, source_raw, e002_raw))
    extraction_map = validate_frozen_scope(signals, sources, e002)
    report = audit_snapshot_v1(
        signal_raw,
        source_raw,
        snapshot_commit=snapshot_commit,
        reviewed_at_utc=reviewed_at_utc,
        previous_audit=None,
    )
    report["audit_version"] = VERSION
    report["scope"] = (
        "exact H022-P001 frozen identities; source metadata plus bound E002 extraction; "
        "both current and prior links; no document-body promotion without review"
    )
    scope_identity = {
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "source_rule_id": SOURCE_RULE_ID,
        "source_rule_sha256": SOURCE_RULE_SHA256,
        "feature_version": FEATURE_VERSION,
        "e002_rule_id": E002_RULE_ID,
        "e002_rule_sha256": E002_RULE_SHA256,
        "parser_version": PARSER_VERSION,
        "parser_library_version": PARSER_LIBRARY_VERSION,
    }
    report["scope_identity"] = scope_identity
    report["scope_identity_sha256"] = canonical_hash(scope_identity)

    for annotation in report["annotations"]:
        extraction = extraction_map[annotation["source_id"]]
        annotation["current_extraction"] = {
            "status": extraction["status"],
            "record_id": extraction.get("record_id"),
            "raw_sha256": extraction.get("raw_sha256"),
            "text_sha256": extraction.get("text_sha256"),
            "page_count": extraction.get("page_count"),
            "text_char_count": extraction.get("text_char_count"),
            "failure_reason": extraction.get("failure_reason"),
            "text_body_supplied_to_audit": False,
        }
        if extraction["status"] != "TEXT_READY":
            annotation["current"] = {
                "document_kind": "EXTRACTION_FAILED",
                "eligibility": "REVIEW_REQUIRED",
                "evidence_basis": "bound_e002_extraction",
                "reasons": ["extraction_failure_is_not_zero_commitments"],
                "full_document_verified": False,
            }
            annotation.update(
                compare_documents(
                    annotation["current"],
                    annotation["prior"],
                    frozen_primary_signal=annotation["original_primary_signal"],
                )
            )

    e002_blob = _git_blob_sha(e002_raw)
    if git_blob_shas is not None:
        _require_equal(
            git_blob_shas.get(INPUT_PATHS[2]), e002_blob, "e002_git_blob_binding_mismatch"
        )
        for item in report["input_files"]:
            _require_equal(
                git_blob_shas.get(item["path"]), item["git_blob_sha"], "git_blob_binding_mismatch"
            )
    report["input_files"].append(
        {
            "path": INPUT_PATHS[2],
            "git_blob_sha": e002_blob,
            "file_sha256": hashlib.sha256(e002_raw).hexdigest(),
            "declared_ledger_sha256": e002["ledger_sha256"],
        }
    )
    report["e002_record_count"] = len(extraction_map)
    report["git_blob_bindings_checked"] = git_blob_shas is not None
    report["previous_audit_sha256"] = None
    if previous_audit is not None:
        report["previous_audit_sha256"] = _validate_previous(
            previous_audit, report, timestamp(reviewed_at_utc)
        )
    report.pop("audit_sha256", None)
    report["audit_sha256"] = canonical_hash(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--snapshot-commit", required=True)
    parser.add_argument("--reviewed-at-utc")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument(
        "--no-git-verify",
        action="store_true",
        help="allow fixture/library use without authenticating the local checkout; not for repository audits",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    paths = tuple(root / path for path in INPUT_PATHS)
    try:
        before = tuple(path.read_bytes() for path in paths)
        blobs = None if args.no_git_verify else verify_git_snapshot(root, args.snapshot_commit, before)
        report = audit_snapshot(
            *before,
            snapshot_commit=args.snapshot_commit,
            reviewed_at_utc=args.reviewed_at_utc or datetime.now(UTC).isoformat(),
            git_blob_shas=blobs,
            previous_audit=load_json(args.previous.read_bytes()) if args.previous else None,
        )
        if tuple(path.read_bytes() for path in paths) != before:
            raise AuditError("inputs_changed_during_audit")
        output = args.output if args.output.is_absolute() else root / args.output
        write_report(report, output, root)
        print(
            json.dumps(
                {
                    "audit_sha256": report["audit_sha256"],
                    "signal_count": report["signal_count"],
                    "classification_counts": report["classification_counts"],
                    "frozen_inputs_unchanged": True,
                    "git_blob_bindings_checked": report["git_blob_bindings_checked"],
                    "advisory_only": True,
                },
                sort_keys=True,
            )
        )
        blocked = any(
            row["comparability"] != "COMPARABLE_DOCUMENTS_ONLY"
            for row in report["annotations"]
        )
        return 2 if args.check and blocked else 0
    except (AuditError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "audit_written": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
