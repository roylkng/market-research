from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from marketlab.h023_prospective import (
    H023ProspectiveError,
    primary_current_source,
    prior_source_at_event,
    source_first_seen,
    validate_event_ledger,
    validate_scan_ledger,
    validate_source_ledger,
    validate_universe_snapshot,
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def verify(
    *, universe: dict[str, Any], source_ledger: dict[str, Any], event_ledger: dict[str, Any], scan_ledger: dict[str, Any]
) -> dict[str, Any]:
    members = validate_universe_snapshot(universe)
    validate_source_ledger(source_ledger)
    validate_event_ledger(event_ledger)
    validate_scan_ledger(scan_ledger)

    source_by_id = {
        str(row["source"]["source_id"]): row["source"] for row in source_ledger["records"]
    }
    for source in source_by_id.values():
        if str(source["symbol"]) not in members:
            raise H023ProspectiveError(
                f"source ledger contains symbol outside frozen U001: {source['symbol']}"
            )

    status_counts: dict[str, int] = {}
    for event in event_ledger["records"]:
        status = str(event["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
        symbol = str(event["symbol"])
        report_date = str(event["report_date"])
        current = event["current_source"]
        current_id = str(current["source_id"])
        if source_by_id.get(current_id) != current:
            raise H023ProspectiveError(
                f"{event['event_id']}: current source is not exactly present in source ledger"
            )
        expected_current = primary_current_source(
            source_ledger, symbol=symbol, report_date=report_date
        )
        if expected_current != current:
            raise H023ProspectiveError(
                f"{event['event_id']}: event is not bound to first official current filing"
            )
        if source_first_seen(source_ledger, current_id) != event["source_first_seen_at_utc"]:
            raise H023ProspectiveError(
                f"{event['event_id']}: source first-seen timestamp does not match ledger"
            )

        expected_prior = prior_source_at_event(
            source_ledger,
            symbol=symbol,
            current_report_date=report_date,
            current_broadcast_at_utc=str(current["broadcast_at_utc"]),
        )
        if status == "NO_SIGNAL_PRIOR_UNAVAILABLE":
            if expected_prior is not None or event["prior_source"] is not None:
                raise H023ProspectiveError(
                    f"{event['event_id']}: no-prior event has an available prior source"
                )
        elif status in {"SIGNAL", "PRIOR_SOURCE_BLOCKED"}:
            prior = event["prior_source"]
            if expected_prior != prior:
                raise H023ProspectiveError(
                    f"{event['event_id']}: event prior is not latest source public at current broadcast"
                )
            if prior is None or source_by_id.get(str(prior["source_id"])) != prior:
                raise H023ProspectiveError(
                    f"{event['event_id']}: prior source is not exactly present in source ledger"
                )
        elif status == "SOURCE_BLOCKED" and event["prior_source"] is not None:
            raise H023ProspectiveError(
                f"{event['event_id']}: source-blocked event must not carry prior source"
            )

    latest_scan_id = None
    if scan_ledger["records"]:
        latest = scan_ledger["records"][-1]
        latest_scan_id = latest["scan_id"]
        expected_symbols = set(members)
        master_symbols = set(latest["master_response_sha256_by_symbol"])
        source_symbols = set(latest["source_ids_by_symbol"])
        if master_symbols != expected_symbols or source_symbols != expected_symbols:
            raise H023ProspectiveError(
                "latest H023 scan does not exactly cover the frozen U001 symbol set"
            )
        for symbol, source_ids in latest["source_ids_by_symbol"].items():
            for source_id in source_ids:
                source = source_by_id.get(str(source_id))
                if source is None or source["symbol"] != symbol:
                    raise H023ProspectiveError(
                        f"latest scan references unknown/mismatched source: {symbol}/{source_id}"
                    )

    return {
        "hypothesis_id": "H023",
        "member_count": len(members),
        "source_record_count": source_ledger["record_count"],
        "event_record_count": event_ledger["record_count"],
        "event_status_counts": dict(sorted(status_counts.items())),
        "scan_record_count": scan_ledger["record_count"],
        "latest_scan_id": latest_scan_id,
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "event_ledger_sha256": event_ledger["ledger_sha256"],
        "scan_ledger_sha256": scan_ledger["ledger_sha256"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify H023 prospective state offline")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    result = verify(
        universe=_load(args.universe),
        source_ledger=_load(args.state_dir / "source-ledger.json"),
        event_ledger=_load(args.state_dir / "event-ledger.json"),
        scan_ledger=_load(args.state_dir / "scan-ledger.json"),
    )
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
