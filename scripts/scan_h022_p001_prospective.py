from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.h003_candidates import FrozenTranscriptSource, H003CandidateStore, extract_source
from marketlab.h003_sources import H003SourceError, select_transcript_sources
from marketlab.h022_expanded_candidates import validate_report as validate_expanded_report
from marketlab.h022_p001_acquisition import validate_operational_context
from marketlab.h022_p001_stream import (
    append_e002_record,
    append_sources,
    build_scan_manifest,
    new_e002_ledger,
    new_source_ledger,
    reconstruct_static_prior_records,
    scan_complete,
    seal_pending_signals,
    unresolved_source_records,
    validate_e002_ledger,
    validate_source_ledger,
    validate_stream_consistency,
)
from marketlab.h022_prospective import (
    HISTORICAL_BASELINE_REPORT_SHA256,
    HISTORICAL_BASELINE_SOURCE_BUNDLE_SHA256,
    PROSPECTIVE_START,
    source_disposition,
    validate_e002_record,
    validate_signal_ledger,
)
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import load_universe_snapshot

IST = ZoneInfo("Asia/Kolkata")
KNOWN_EXPANDED_RECORD_FIELDS = frozenset({"membership_status", "signal_eligible"})


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_object(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _load_list(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise TypeError(f"expected JSON object list: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _source_dict(source: Any) -> dict[str, Any]:
    return {
        "schema_version": source.schema_version,
        "source_id": source.source_id,
        "symbol": source.symbol,
        "seq_id": source.seq_id,
        "exchange_published_at_utc": source.exchange_published_at_utc,
        "attachment_url": source.attachment_url,
        "announcement_description": source.announcement_description,
        "attachment_text": source.attachment_text,
        "discovery_row_sha256": source.discovery_row_sha256,
    }


def _frozen_source(source: dict[str, Any]) -> FrozenTranscriptSource:
    return FrozenTranscriptSource(
        source_id=str(source["source_id"]),
        symbol=str(source["symbol"]),
        seq_id=str(source["seq_id"]),
        exchange_published_at_utc=str(source["exchange_published_at_utc"]),
        attachment_url=str(source["attachment_url"]),
        discovery_row_sha256=str(source["discovery_row_sha256"]),
    )


def _retain_discovery(store: Path, *, symbol: str, raw: bytes) -> dict[str, Any]:
    digest = _sha256(raw)
    path = store / "discovery" / "raw" / "sha256" / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise RuntimeError("content-addressed P001 discovery collision")
    else:
        path.write_bytes(raw)
    return {
        "symbol": symbol,
        "sha256": digest,
        "byte_count": len(raw),
        "path": path.as_posix(),
    }


def _clean_historical_record(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        key: value
        for key, value in record.items()
        if key not in KNOWN_EXPANDED_RECORD_FIELDS
    }
    validate_e002_record(cleaned)
    return cleaned


def _historical_records(report: dict[str, Any], *, symbols: set[str]) -> list[dict[str, Any]]:
    validate_expanded_report(report)
    if report.get("report_sha256") != HISTORICAL_BASELINE_REPORT_SHA256:
        raise ValueError("historical H022 baseline report digest changed")
    if report.get("source_bundle_sha256") != HISTORICAL_BASELINE_SOURCE_BUNDLE_SHA256:
        raise ValueError("historical H022 baseline source-bundle digest changed")
    if report.get("complete") is not True or report.get("outcome_data_attached") is not False:
        raise ValueError("historical H022 baseline is not complete/outcome-free")
    rows = report.get("records")
    if not isinstance(rows, list):
        raise TypeError("historical H022 baseline records must be a list")
    selected: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("historical H022 baseline record must be an object")
        if str(row.get("symbol") or "").strip().upper() in symbols:
            selected.append(_clean_historical_record(row))
    return selected


def _load_source_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return new_source_ledger()
    ledger = _load_object(path)
    validate_source_ledger(ledger)
    return ledger


def _load_e002_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return new_e002_ledger()
    ledger = _load_object(path)
    validate_e002_ledger(ledger)
    return ledger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan official NSE sources and advance the H022-P001 prospective stream"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--historical-report", type=Path, required=True)
    parser.add_argument("--context-dir", type=Path, required=True)
    parser.add_argument("--source-ledger", type=Path, required=True)
    parser.add_argument("--e002-ledger", type=Path, required=True)
    parser.add_argument("--signal-ledger", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--cutoff-utc")
    parser.add_argument("--pause-seconds", type=float, default=0.15)
    parser.add_argument("--fetch-attempts", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.pause_seconds < 0:
        raise ValueError("pause-seconds must be non-negative")
    if args.fetch_attempts < 1:
        raise ValueError("fetch-attempts must be positive")

    started_at = datetime.now(UTC)
    cutoff = (
        _timestamp(args.cutoff_utc, field="cutoff_utc")
        if args.cutoff_utc
        else started_at
    )
    if cutoff < PROSPECTIVE_START:
        raise SystemExit("H022-P001 prospective scan cutoff precedes frozen start")
    if cutoff > started_at:
        raise SystemExit("H022-P001 scan cutoff cannot be in the future")

    universe_document = _load_object(args.universe)
    universe = load_universe_snapshot(args.universe)
    symbols = {member.symbol.upper() for member in universe.members}

    context_manifest = _load_object(args.context_dir / "discovery-manifest.json")
    core_gate = _load_object(args.context_dir / "context-gate.json")
    prior_index = _load_object(args.context_dir / "static-prior-index.json")
    operational_context = _load_object(args.context_dir / "operational-context.json")
    catchup_records = _load_list(args.context_dir / "catchup-records.json")
    validate_operational_context(
        operational_context=operational_context,
        core_gate=core_gate,
        prior_index=prior_index,
        discovery_manifest=context_manifest,
        universe_snapshot=universe_document,
    )

    historical_report = _load_object(args.historical_report)
    historical_records = _historical_records(historical_report, symbols=symbols)
    static_prior_records = reconstruct_static_prior_records(
        prior_index=prior_index,
        historical_records=historical_records,
        catchup_records=catchup_records,
    )

    source_ledger = _load_source_ledger(args.source_ledger)
    e002_ledger = _load_e002_ledger(args.e002_ledger)
    signal_ledger = _load_object(args.signal_ledger)
    validate_signal_ledger(signal_ledger)
    validate_stream_consistency(
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
        signal_ledger=signal_ledger,
    )

    from_date = PROSPECTIVE_START.astimezone(IST).date()
    to_date = cutoff.astimezone(IST).date()
    client = NSEClient(timeout=25.0, attempts=args.fetch_attempts)
    discovery_rows: list[dict[str, Any]] = []
    discovery_artifacts: list[dict[str, Any]] = []

    for index, member in enumerate(universe.members, start=1):
        symbol = member.symbol.upper()
        try:
            payload, raw = client.corporate_announcements_with_raw(
                symbol,
                from_date=from_date.strftime("%d-%m-%Y"),
                to_date=to_date.strftime("%d-%m-%Y"),
            )
            retained = _retain_discovery(args.store, symbol=symbol, raw=raw)
            discovery_artifacts.append(retained)
            selected = select_transcript_sources(
                payload,
                symbol=symbol,
                window_start=from_date,
                window_end=to_date,
                cutoff_utc=cutoff,
            )
            sources = [
                _source_dict(source)
                for source in selected
                if _timestamp(
                    str(source.exchange_published_at_utc),
                    field=f"{source.source_id}.published",
                )
                >= PROSPECTIVE_START
            ]
            row = {
                "symbol": symbol,
                "coverage_status": "COMPLETE",
                "incomplete_reason": None,
                "discovery_sha256": retained["sha256"],
                "source_count": len(sources),
                "sources": sources,
            }
        except (NSEAcquisitionError, H003SourceError, RuntimeError, ValueError) as exc:
            row = {
                "symbol": symbol,
                "coverage_status": "INCOMPLETE",
                "incomplete_reason": f"{type(exc).__name__}: {exc}",
                "discovery_sha256": None,
                "source_count": 0,
                "sources": [],
            }
        discovery_rows.append(row)
        print(
            f"[{index:03d}/{len(universe.members):03d}] {symbol}: "
            f"{row['coverage_status']} sources={row['source_count']}"
            + (
                f" reason={row['incomplete_reason']}"
                if row["incomplete_reason"]
                else ""
            ),
            flush=True,
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    discovery_completed = datetime.now(UTC)
    scan_manifest = build_scan_manifest(
        universe_snapshot=universe_document,
        cutoff_utc=_utc_text(cutoff),
        completed_at_utc=_utc_text(discovery_completed),
        rows=discovery_rows,
    )
    _write_json(args.out_dir / "scan-manifest.json", scan_manifest)
    _write_json(args.out_dir / "discovery-artifacts.json", discovery_artifacts)
    if not scan_complete(scan_manifest):
        summary = {
            "schema_version": 1,
            "status": "DISCOVERY_INCOMPLETE",
            "started_at_utc": _utc_text(started_at),
            "cutoff_utc": _utc_text(cutoff),
            "completed_at_utc": _utc_text(datetime.now(UTC)),
            "scan_sha256": scan_manifest["scan_sha256"],
            "incomplete_symbols": scan_manifest["incomplete_symbols"],
            "outcome_data_attached": False,
            "live_capital_allowed": False,
        }
        _write_json(args.out_dir / "summary.json", summary)
        raise SystemExit("H022-P001 full-U001 prospective discovery is incomplete")

    discovered_sources = [
        source
        for row in scan_manifest["records"]
        for source in row["sources"]
    ]
    source_ledger = append_sources(
        source_ledger,
        discovered_sources,
        first_seen_at_utc=_utc_text(discovery_completed),
        signal_ledger=signal_ledger,
    )

    candidate_store = H003CandidateStore(args.store / "e002")
    extraction_attempts: list[dict[str, Any]] = []
    for index, source_row in enumerate(
        unresolved_source_records(source_ledger, e002_ledger), start=1
    ):
        source = source_row["source"]
        source_id = str(source["source_id"])
        frozen = _frozen_source(source)
        attempt: dict[str, Any] = {
            "source_id": source_id,
            "symbol": frozen.symbol,
            "attempted_at_utc": _utc_text(datetime.now(UTC)),
            "status": "UNRESOLVED",
        }
        try:
            raw_pdf = client.archive_bytes(frozen.attachment_url)
            attempt["raw_sha256"] = _sha256(raw_pdf)
            attempt["raw_byte_count"] = len(raw_pdf)
            record = extract_source(frozen, raw_pdf, store=candidate_store).to_dict()
            attempt["e002_status"] = record.get("status")
            attempt["failure_reason"] = record.get("failure_reason")
            attempt["record_id"] = record.get("record_id")
            if record.get("status") == "TEXT_READY":
                validate_e002_record(record)
                if source_disposition(record) != "PROSPECTIVE_SIGNAL_ELIGIBLE":
                    raise ValueError("E002 record is not prospectively eligible")
                e002_ledger = append_e002_record(e002_ledger, record)
                attempt["status"] = "TEXT_READY"
        except (NSEAcquisitionError, OSError, RuntimeError, ValueError) as exc:
            attempt["error"] = f"{type(exc).__name__}: {exc}"
        extraction_attempts.append(attempt)
        print(
            f"[extract {index:03d}] {frozen.symbol} {source_id[:12]} "
            f"status={attempt['status']}",
            flush=True,
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    signal_freeze = datetime.now(UTC)
    signal_ledger, blocked_signals = seal_pending_signals(
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
        signal_ledger=signal_ledger,
        static_prior_records=static_prior_records,
        universe_snapshot=universe_document,
        core_gate=core_gate,
        discovery_manifest=context_manifest,
        prior_index=prior_index,
        operational_context=operational_context,
        frozen_at_utc=_utc_text(signal_freeze),
    )
    validate_stream_consistency(
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
        signal_ledger=signal_ledger,
    )

    _write_json(args.out_dir / "source-ledger.json", source_ledger)
    _write_json(args.out_dir / "e002-ledger.json", e002_ledger)
    _write_json(args.out_dir / "signal-ledger.json", signal_ledger)
    _write_json(args.out_dir / "extraction-attempts.json", extraction_attempts)
    _write_json(args.out_dir / "blocked-signals.json", blocked_signals)
    unresolved = unresolved_source_records(source_ledger, e002_ledger)
    summary = {
        "schema_version": 1,
        "status": "COMPLETE_SCAN",
        "started_at_utc": _utc_text(started_at),
        "cutoff_utc": _utc_text(cutoff),
        "discovery_completed_at_utc": _utc_text(discovery_completed),
        "signal_freeze_utc": _utc_text(signal_freeze),
        "completed_at_utc": _utc_text(datetime.now(UTC)),
        "scan_sha256": scan_manifest["scan_sha256"],
        "discovered_source_count": source_ledger["record_count"],
        "text_ready_source_count": e002_ledger["record_count"],
        "unresolved_source_count": len(unresolved),
        "unresolved_source_ids": [row["source"]["source_id"] for row in unresolved],
        "signal_record_count": signal_ledger["record_count"],
        "blocked_signal_count": len(blocked_signals),
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "e002_ledger_sha256": e002_ledger["ledger_sha256"],
        "signal_ledger_sha256": signal_ledger["ledger_sha256"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
