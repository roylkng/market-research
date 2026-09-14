from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h023_acquisition import (
    H023AcquisitionError,
    build_xbrl_evidence,
    discover_standard_quarter_sources,
    fetch_master,
    fetch_xbrl,
    master_session,
    sha256_bytes,
    utc_now_text,
    xbrl_session,
)
from marketlab.h023_prospective import (
    PROSPECTIVE_START_UTC,
    H023ProspectiveError,
    append_event,
    append_scan,
    append_sources,
    build_scan_record,
    event_exists,
    new_event_ledger,
    new_scan_ledger,
    new_source_ledger,
    validate_event_ledger,
    validate_scan_ledger,
    validate_source_ledger,
    validate_universe_snapshot,
)
from marketlab.h023_selection import (
    build_strict_event_record,
    strict_primary_current_source,
    strict_prior_source_at_event,
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


def _fetch_evidence(
    *,
    source: dict[str, Any],
    session,
    raw_dir: Path,
    timeout_seconds: float,
    attempts: int,
) -> dict[str, Any]:
    source_id = str(source["source_id"])
    target = raw_dir / "xbrl" / f"{source_id}.xml"
    try:
        response = fetch_xbrl(
            session,
            url=str(source["xbrl_url"]),
            timeout=timeout_seconds,
            attempts=attempts,
        )
    except H023AcquisitionError as exc:
        return {
            "status": "FETCH_FAILED",
            "source_id": source_id,
            "xbrl_sha256": None,
            "mutual_fund_percentage": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return build_xbrl_evidence(source, response.content)


def _utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H023ProspectiveError(f"invalid source broadcast timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise H023ProspectiveError("source broadcast timestamp must include timezone")
    return parsed.astimezone(UTC)


def _eligible_event_keys(source_ledger: dict[str, Any]) -> list[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    source_pairs = {
        (str(row["source"]["symbol"]), str(row["source"]["report_date"]))
        for row in source_ledger["records"]
    }
    for symbol, report_date in source_pairs:
        current = strict_primary_current_source(
            source_ledger, symbol=symbol, report_date=report_date
        )
        if current is None:
            continue
        if _utc_timestamp(str(current["broadcast_at_utc"])) < PROSPECTIVE_START_UTC:
            continue
        keys.add((symbol, report_date))
    return sorted(keys, key=lambda item: (item[1], item[0]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one H023 prospective ownership scan")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.08)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout_seconds <= 0 or args.attempts < 1 or args.pause_seconds < 0:
        raise ValueError("invalid H023 scan configuration")

    universe = _load_json(args.universe)
    members = validate_universe_snapshot(universe)
    source_path = args.state_dir / "source-ledger.json"
    event_path = args.state_dir / "event-ledger.json"
    scan_path = args.state_dir / "scan-ledger.json"
    source_ledger = _load_or_initialize(source_path, new_source_ledger)
    event_ledger = _load_or_initialize(event_path, new_event_ledger)
    scan_ledger = _load_or_initialize(scan_path, new_scan_ledger)
    validate_source_ledger(source_ledger)
    validate_event_ledger(event_ledger)
    validate_scan_ledger(scan_ledger)

    start_source_count = int(source_ledger["record_count"])
    start_event_count = int(event_ledger["record_count"])
    started_at = utc_now_text()
    api = master_session(args.timeout_seconds)
    archive = xbrl_session()
    master_hashes: dict[str, str] = {}
    source_ids_by_symbol: dict[str, list[str]] = {}

    member_order = [str(row["symbol"]).strip().upper() for row in universe["members"]]
    if set(member_order) != set(members):
        raise H023ProspectiveError("H023 universe member order is inconsistent")

    for index, symbol in enumerate(member_order, start=1):
        observed_at = utc_now_text()
        response = fetch_master(
            api,
            symbol=symbol,
            timeout=args.timeout_seconds,
            attempts=args.attempts,
        )
        body = response.content
        master_path = args.raw_dir / "master" / f"{symbol}.json"
        master_path.parent.mkdir(parents=True, exist_ok=True)
        master_path.write_bytes(body)
        master_hashes[symbol] = sha256_bytes(body)
        try:
            payload = response.json()
        except ValueError as exc:
            raise H023AcquisitionError(f"{symbol}: NSE master response is not JSON") from exc
        sources = discover_standard_quarter_sources(payload, symbol=symbol)
        source_ids_by_symbol[symbol] = [str(source["source_id"]) for source in sources]
        source_ledger = append_sources(
            source_ledger,
            sources,
            first_seen_at_utc=observed_at,
            event_ledger=event_ledger,
        )
        print(
            f"[{index:03d}/100] {symbol}: master_bytes={len(body)} "
            f"quarter_sources={len(sources)}",
            flush=True,
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    evidence_cache: dict[str, dict[str, Any]] = {}
    new_event_statuses: Counter[str] = Counter()
    new_event_ids: list[str] = []
    for symbol, report_date in _eligible_event_keys(source_ledger):
        if event_exists(event_ledger, symbol=symbol, report_date=report_date):
            continue
        current = strict_primary_current_source(
            source_ledger, symbol=symbol, report_date=report_date
        )
        if current is None:
            continue
        current_id = str(current["source_id"])
        current_evidence = evidence_cache.get(current_id)
        if current_evidence is None:
            current_evidence = _fetch_evidence(
                source=current,
                session=archive,
                raw_dir=args.raw_dir,
                timeout_seconds=args.timeout_seconds,
                attempts=args.attempts,
            )
            evidence_cache[current_id] = current_evidence
        prior = strict_prior_source_at_event(
            source_ledger,
            symbol=symbol,
            current_report_date=report_date,
            current_broadcast_at_utc=str(current["broadcast_at_utc"]),
        )
        prior_evidence = None
        if prior is not None:
            prior_id = str(prior["source_id"])
            prior_evidence = evidence_cache.get(prior_id)
            if prior_evidence is None:
                prior_evidence = _fetch_evidence(
                    source=prior,
                    session=archive,
                    raw_dir=args.raw_dir,
                    timeout_seconds=args.timeout_seconds,
                    attempts=args.attempts,
                )
                evidence_cache[prior_id] = prior_evidence
        record = build_strict_event_record(
            source_ledger=source_ledger,
            symbol=symbol,
            report_date=report_date,
            frozen_at_utc=utc_now_text(),
            current_evidence=current_evidence,
            prior_evidence=prior_evidence,
        )
        if record is None:
            continue
        event_ledger = append_event(event_ledger, record)
        new_event_ids.append(str(record["event_id"]))
        new_event_statuses[str(record["status"])] += 1

    completed_at = utc_now_text()
    scan_record = build_scan_record(
        universe_snapshot=universe,
        scanned_at_utc=completed_at,
        master_response_sha256_by_symbol=master_hashes,
        source_ids_by_symbol=source_ids_by_symbol,
    )
    scan_ledger = append_scan(scan_ledger, scan_record)

    validate_source_ledger(source_ledger)
    validate_event_ledger(event_ledger)
    validate_scan_ledger(scan_ledger)
    _write_json(source_path, source_ledger)
    _write_json(event_path, event_ledger)
    _write_json(scan_path, scan_ledger)

    report = {
        "schema_version": 1,
        "hypothesis_id": "H023",
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "member_count": 100,
        "complete_member_count": 100,
        "new_source_count": int(source_ledger["record_count"]) - start_source_count,
        "new_event_count": int(event_ledger["record_count"]) - start_event_count,
        "new_event_status_counts": dict(sorted(new_event_statuses.items())),
        "new_event_ids": new_event_ids,
        "scan_id": scan_record["scan_id"],
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "event_ledger_sha256": event_ledger["ledger_sha256"],
        "scan_ledger_sha256": scan_ledger["ledger_sha256"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.report, report)
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
