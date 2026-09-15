from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.h024_acquisition import (
    H024AcquisitionError,
    archive_session,
    build_xbrl_evidence,
    discover_sources,
    discovery_session,
    fetch_discovery,
    fetch_xbrl,
    sha256_bytes,
    trailing_discovery_window,
    utc_now_text,
)
from marketlab.h024_prospective import (
    append_evidence,
    append_scan,
    append_signal,
    append_sources,
    build_scan_record,
    build_signal_record,
    evidence_by_source,
    new_evidence_ledger,
    new_scan_ledger,
    new_signal_ledger,
    new_source_ledger,
    signal_exists,
    validate_calendar,
    validate_evidence_ledger,
    validate_scan_ledger,
    validate_signal_ledger,
    validate_source_ledger,
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _load_or_initialize(path: Path, factory) -> dict[str, Any]:
    return _load_json(path) if path.exists() else factory()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one H024 prospective PIT source scan")
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--discovery-attempts", type=int, default=4)
    parser.add_argument("--xbrl-attempts", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if (
        args.lookback_days < 1
        or args.timeout_seconds <= 0
        or args.discovery_attempts < 1
        or args.xbrl_attempts < 1
    ):
        raise ValueError("invalid H024 scan configuration")

    calendar = _load_json(args.calendar)
    validate_calendar(calendar)

    source_path = args.state_dir / "source-ledger.json"
    evidence_path = args.state_dir / "evidence-ledger.json"
    signal_path = args.state_dir / "signal-ledger.json"
    scan_path = args.state_dir / "scan-ledger.json"
    source_ledger = _load_or_initialize(source_path, new_source_ledger)
    evidence_ledger = _load_or_initialize(evidence_path, new_evidence_ledger)
    signal_ledger = _load_or_initialize(signal_path, new_signal_ledger)
    scan_ledger = _load_or_initialize(scan_path, new_scan_ledger)
    validate_source_ledger(source_ledger)
    validate_evidence_ledger(evidence_ledger)
    validate_signal_ledger(signal_ledger)
    validate_scan_ledger(scan_ledger)

    start_source_count = int(source_ledger["record_count"])
    start_evidence_count = int(evidence_ledger["record_count"])
    start_signal_count = int(signal_ledger["record_count"])
    started_at = utc_now_text()

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    window_start, window_end = trailing_discovery_window(
        now_utc=now,
        lookback_days=args.lookback_days,
    )
    api = discovery_session(args.timeout_seconds)
    response = fetch_discovery(
        api,
        start=window_start,
        end=window_end,
        timeout=args.timeout_seconds,
        attempts=args.discovery_attempts,
    )
    discovery_raw = response.content
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    discovery_path = args.raw_dir / (
        f"pit-gg-{window_start.isoformat()}-{window_end.isoformat()}.json"
    )
    discovery_path.write_bytes(discovery_raw)
    try:
        payload = response.json()
    except ValueError as exc:
        raise H024AcquisitionError("H024 PIT-GG response is not JSON") from exc
    sources = discover_sources(payload)
    observed_at = utc_now_text()
    source_ledger = append_sources(
        source_ledger,
        sources,
        first_seen_at_utc=observed_at,
    )

    archive = archive_session()
    acquisition_statuses: Counter[str] = Counter()
    new_evidence_source_ids: list[str] = []
    for source in sources:
        source_id = str(source["source_id"])
        if evidence_by_source(evidence_ledger, source_id) is not None:
            continue
        try:
            xbrl_response = fetch_xbrl(
                archive,
                url=str(source["xml_url"]),
                timeout=args.timeout_seconds,
                attempts=args.xbrl_attempts,
            )
        except H024AcquisitionError:
            acquisition_statuses["FETCH_RETRY_PENDING"] += 1
            continue
        raw = xbrl_response.content
        xbrl_path = args.raw_dir / "xbrl" / f"{source_id}.xml"
        xbrl_path.parent.mkdir(parents=True, exist_ok=True)
        xbrl_path.write_bytes(raw)
        evidence = build_xbrl_evidence(source, raw)
        evidence_ledger = append_evidence(
            evidence_ledger,
            source_ledger,
            evidence,
            frozen_at_utc=utc_now_text(),
        )
        new_evidence_source_ids.append(source_id)
        acquisition_statuses[str(evidence["status"])] += 1

    new_signal_ids: list[str] = []
    new_signal_statuses: Counter[str] = Counter()
    for source in sources:
        source_id = str(source["source_id"])
        if signal_exists(signal_ledger, source_id):
            continue
        record = build_signal_record(
            source_ledger=source_ledger,
            evidence_ledger=evidence_ledger,
            calendar=calendar,
            source_id=source_id,
            frozen_at_utc=utc_now_text(),
        )
        if record is None:
            continue
        signal_ledger = append_signal(signal_ledger, record)
        new_signal_ids.append(str(record["signal_id"]))
        new_signal_statuses[str(record["status"])] += 1

    completed_at = utc_now_text()
    scan_record = build_scan_record(
        scanned_at_utc=completed_at,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        discovery_raw_sha256=sha256_bytes(discovery_raw),
        source_ids=[str(source["source_id"]) for source in sources],
    )
    scan_ledger = append_scan(scan_ledger, scan_record)

    validate_source_ledger(source_ledger)
    validate_evidence_ledger(evidence_ledger)
    validate_signal_ledger(signal_ledger)
    validate_scan_ledger(scan_ledger)
    _write_json(source_path, source_ledger)
    _write_json(evidence_path, evidence_ledger)
    _write_json(signal_path, signal_ledger)
    _write_json(scan_path, scan_ledger)

    report = {
        "schema_version": 1,
        "hypothesis_id": "H024",
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "discovered_regulation_7_2_source_count": len(sources),
        "new_source_count": int(source_ledger["record_count"]) - start_source_count,
        "new_evidence_count": int(evidence_ledger["record_count"]) - start_evidence_count,
        "new_signal_count": int(signal_ledger["record_count"]) - start_signal_count,
        "new_evidence_source_ids": new_evidence_source_ids,
        "acquisition_status_counts": dict(sorted(acquisition_statuses.items())),
        "new_signal_ids": new_signal_ids,
        "new_signal_status_counts": dict(sorted(new_signal_statuses.items())),
        "scan_id": scan_record["scan_id"],
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "evidence_ledger_sha256": evidence_ledger["ledger_sha256"],
        "signal_ledger_sha256": signal_ledger["ledger_sha256"],
        "scan_ledger_sha256": scan_ledger["ledger_sha256"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.report, report)
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
