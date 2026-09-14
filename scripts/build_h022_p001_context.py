from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h003_candidates import (
    FrozenTranscriptSource,
    H003CandidateStore,
    extract_source,
)
from marketlab.h003_sources import H003SourceError, select_transcript_sources
from marketlab.h022_expanded_candidates import validate_report as validate_expanded_report
from marketlab.h022_p001_acquisition import (
    build_discovery_manifest,
    build_operational_context,
    catchup_query_dates,
    discovery_complete,
)
from marketlab.h022_prospective import (
    HISTORICAL_BASELINE_REPORT_SHA256,
    HISTORICAL_BASELINE_SOURCE_BUNDLE_SHA256,
    HISTORICAL_CUTOFF,
    PROSPECTIVE_START,
    source_disposition,
    validate_e002_record,
)
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import load_universe_snapshot

KNOWN_EXPANDED_RECORD_FIELDS = frozenset({"membership_status", "signal_eligible"})


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _strip_expanded_metadata(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        key: value
        for key, value in record.items()
        if key not in KNOWN_EXPANDED_RECORD_FIELDS
    }
    validate_e002_record(cleaned)
    return cleaned


def _historical_u001_records(
    report: dict[str, Any], *, symbols: set[str]
) -> list[dict[str, Any]]:
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
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("historical H022 baseline record must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol not in symbols:
            continue
        cleaned = _strip_expanded_metadata(row)
        source_id = str(cleaned["source_id"])
        if source_id in seen:
            raise ValueError(f"duplicate historical E002 source id: {source_id}")
        seen.add(source_id)
        published = datetime.fromisoformat(
            str(cleaned["exchange_published_at_utc"])
        ).astimezone(UTC)
        if published > HISTORICAL_CUTOFF:
            raise ValueError(f"historical baseline source exceeds cutoff: {source_id}")
        selected.append(cleaned)
    selected.sort(
        key=lambda row: (
            str(row["exchange_published_at_utc"]),
            str(row["symbol"]),
            str(row["source_id"]),
        )
    )
    return selected


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


def _strict_catchup_source(source: Any) -> bool:
    published = datetime.fromisoformat(
        str(source.exchange_published_at_utc)
    ).astimezone(UTC)
    return HISTORICAL_CUTOFF < published < PROSPECTIVE_START


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build H022-P001 mandatory pre-start context and static-prior evidence"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--historical-report", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
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
    if started_at < PROSPECTIVE_START:
        raise SystemExit(
            "H022-P001 context gate cannot complete before the frozen prospective boundary"
        )

    universe_document = _load_json(args.universe)
    if not isinstance(universe_document, dict):
        raise TypeError("U001 universe must be a JSON object")
    universe = load_universe_snapshot(args.universe)
    symbols = {member.symbol.upper() for member in universe.members}
    historical_document = _load_json(args.historical_report)
    if not isinstance(historical_document, dict):
        raise TypeError("historical H022 baseline report must be a JSON object")
    historical_records = _historical_u001_records(
        historical_document,
        symbols=symbols,
    )

    from_date, to_date = catchup_query_dates()
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
            sources = [
                _source_dict(source)
                for source in select_transcript_sources(
                    payload,
                    symbol=symbol,
                    window_start=from_date,
                    window_end=to_date,
                    cutoff_utc=PROSPECTIVE_START,
                )
                if _strict_catchup_source(source)
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

    discovery_completed_at = datetime.now(UTC)
    discovery_manifest = build_discovery_manifest(
        universe_snapshot=universe_document,
        rows=discovery_rows,
        generated_at_utc=_utc_text(discovery_completed_at),
    )
    _write_json(args.out_dir / "discovery-manifest.json", discovery_manifest)
    _write_json(args.out_dir / "discovery-artifacts.json", discovery_artifacts)
    if not discovery_complete(discovery_manifest):
        _write_json(
            args.out_dir / "summary.json",
            {
                "schema_version": 1,
                "status": "DISCOVERY_INCOMPLETE",
                "started_at_utc": _utc_text(started_at),
                "completed_at_utc": _utc_text(datetime.now(UTC)),
                "discovery_manifest_sha256": discovery_manifest["manifest_sha256"],
                "incomplete_symbols": discovery_manifest["incomplete_symbols"],
                "catchup_source_count": discovery_manifest["catchup_source_count"],
                "outcome_data_attached": False,
                "live_capital_allowed": False,
            },
        )
        raise SystemExit("H022-P001 catch-up discovery is incomplete; context gate not sealed")

    source_by_id = {
        str(source["source_id"]): source
        for row in discovery_manifest["records"]
        for source in row["sources"]
    }
    candidate_store = H003CandidateStore(args.store / "e002")
    catchup_records: list[dict[str, Any]] = []
    extraction_failures: list[dict[str, str]] = []
    for index, source_id in enumerate(discovery_manifest["catchup_source_ids"], start=1):
        source_document = source_by_id[source_id]
        frozen = _frozen_source(source_document)
        try:
            raw_pdf = client.archive_bytes(frozen.attachment_url)
            record = extract_source(frozen, raw_pdf, store=candidate_store).to_dict()
            validate_e002_record(record)
            if source_disposition(record) != "CONTEXT_ONLY_PRE_START":
                raise ValueError("extracted source is not CONTEXT_ONLY_PRE_START")
            if record["status"] != "TEXT_READY":
                raise ValueError(
                    f"H003-E002 extraction status is {record['status']}: {record['failure_reason']}"
                )
            catchup_records.append(record)
            status = "TEXT_READY"
        except (NSEAcquisitionError, ValueError, OSError) as exc:
            extraction_failures.append(
                {
                    "source_id": source_id,
                    "symbol": frozen.symbol,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            status = "FAILED"
        print(
            f"[extract {index:03d}/{len(source_by_id):03d}] {frozen.symbol} "
            f"{source_id[:12]} status={status}",
            flush=True,
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    catchup_records.sort(
        key=lambda row: (
            str(row["exchange_published_at_utc"]),
            str(row["symbol"]),
            str(row["source_id"]),
        )
    )
    _write_json(args.out_dir / "catchup-records.json", catchup_records)
    _write_json(args.out_dir / "extraction-failures.json", extraction_failures)
    if extraction_failures:
        _write_json(
            args.out_dir / "summary.json",
            {
                "schema_version": 1,
                "status": "EXTRACTION_INCOMPLETE",
                "started_at_utc": _utc_text(started_at),
                "completed_at_utc": _utc_text(datetime.now(UTC)),
                "discovery_manifest_sha256": discovery_manifest["manifest_sha256"],
                "catchup_source_count": len(source_by_id),
                "text_ready_count": len(catchup_records),
                "failure_count": len(extraction_failures),
                "outcome_data_attached": False,
                "live_capital_allowed": False,
            },
        )
        raise SystemExit("H022-P001 catch-up extraction is incomplete; context gate not sealed")

    completed_at = datetime.now(UTC)
    core_gate, prior_index, operational = build_operational_context(
        universe_snapshot=universe_document,
        discovery_manifest=discovery_manifest,
        historical_records=historical_records,
        catchup_records=catchup_records,
        completed_at_utc=_utc_text(completed_at),
    )
    _write_json(args.out_dir / "context-gate.json", core_gate)
    _write_json(args.out_dir / "static-prior-index.json", prior_index)
    _write_json(args.out_dir / "operational-context.json", operational)
    summary = {
        "schema_version": 1,
        "status": "COMPLETE",
        "started_at_utc": _utc_text(started_at),
        "completed_at_utc": _utc_text(completed_at),
        "historical_u001_record_count": len(historical_records),
        "catchup_source_count": len(catchup_records),
        "discovery_manifest_sha256": discovery_manifest["manifest_sha256"],
        "context_gate_sha256": core_gate["context_gate_sha256"],
        "prior_index_sha256": prior_index["prior_index_sha256"],
        "operational_context_sha256": operational["operational_context_sha256"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
