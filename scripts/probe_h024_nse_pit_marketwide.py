from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from probe_h024_nse_pit_source import (
    _clean,
    _request,
    _rows,
    _session,
    _sha256,
    _write_json,
)

DIRECT_ACTOR_CATEGORIES = frozenset(
    {"Promoters", "Promoter Group", "Director", "Key Managerial Personnel"}
)
BROAD_ACTOR_CATEGORIES = DIRECT_ACTOR_CATEGORIES | {"Immediate relative"}


def _number(value: object) -> float | None:
    text = _clean(value).replace(",", "")
    if not text or text.casefold() in {"nil", "na", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _is_market_purchase(row: dict[str, Any]) -> bool:
    return (
        _clean(row.get("acqMode")) == "Market Purchase"
        and _clean(row.get("tdpTransactionType")) == "Buy"
        and _clean(row.get("secType")) == "Equity Shares"
    )


def _event_inventory(
    rows: list[dict[str, Any]], categories: frozenset[str]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not _is_market_purchase(row):
            continue
        if _clean(row.get("personCategory")) not in categories:
            continue
        key = (
            _clean(row.get("symbol")).upper(),
            _clean(row.get("date")),
            _clean(row.get("xbrl")),
        )
        if not all(key):
            continue
        groups[key].append(row)

    events: list[dict[str, Any]] = []
    for (symbol, published_at, xbrl), event_rows in sorted(groups.items()):
        values = [_number(row.get("secVal")) for row in event_rows]
        quantities = [_number(row.get("secAcq")) for row in event_rows]
        before_pct = [_number(row.get("befAcqSharesPer")) for row in event_rows]
        after_pct = [_number(row.get("afterAcqSharesPer")) for row in event_rows]
        events.append(
            {
                "symbol": symbol,
                "exchange_published_at": published_at,
                "xbrl": xbrl,
                "row_count": len(event_rows),
                "actor_count": len({_clean(row.get("acqName")) for row in event_rows}),
                "person_categories": sorted(
                    {_clean(row.get("personCategory")) for row in event_rows}
                ),
                "acquirer_names": sorted(
                    {_clean(row.get("acqName")) for row in event_rows}
                ),
                "purchase_value_inr": sum(
                    value for value in values if value is not None
                ),
                "purchase_quantity": sum(
                    value for value in quantities if value is not None
                ),
                "reported_ownership_delta_pp": sum(
                    after - before
                    for before, after in zip(before_pct, after_pct, strict=True)
                    if before is not None and after is not None
                ),
                "intimation_dates": sorted(
                    {_clean(row.get("intimDt")) for row in event_rows}
                ),
                "exchanges": sorted(
                    {_clean(row.get("exchange")) for row in event_rows}
                ),
                "pids": sorted({_clean(row.get("pid")) for row in event_rows}),
                "dids": sorted({_clean(row.get("did")) for row in event_rows}),
            }
        )
    return events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Market-wide source-only inventory for NSE Regulation 7(2) insider purchases"
    )
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = _session(args.timeout_seconds)
    response = _request(
        session,
        symbol="",
        from_date=args.from_date,
        to_date=args.to_date,
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    raw = response.content
    if args.raw is not None:
        args.raw.parent.mkdir(parents=True, exist_ok=True)
        args.raw.write_bytes(raw)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("market-wide NSE PIT response is not JSON") from exc
    rows = _rows(payload)
    direct = _event_inventory(rows, DIRECT_ACTOR_CATEGORIES)
    broad = _event_inventory(rows, BROAD_ACTOR_CATEGORIES)

    category_counts = Counter(_clean(row.get("personCategory")) for row in rows)
    mode_counts = Counter(_clean(row.get("acqMode")) for row in rows)
    transaction_counts = Counter(
        _clean(row.get("tdpTransactionType")) for row in rows
    )
    market_purchase_rows = [row for row in rows if _is_market_purchase(row)]
    symbols = {
        _clean(row.get("symbol")).upper()
        for row in rows
        if _clean(row.get("symbol"))
    }
    unique_xbrls = {
        _clean(row.get("xbrl")) for row in rows if _clean(row.get("xbrl"))
    }
    market_purchase_symbols = {
        _clean(row.get("symbol")).upper() for row in market_purchase_rows
    }
    report = {
        "schema_version": 1,
        "hypothesis_candidate": "H024_INSIDER_CAPITAL_COMMITMENT",
        "probe_id": "H024-NSE-PIT-MARKETWIDE-INVENTORY-V1",
        "purpose": (
            "Market-wide source-only feasibility count for explicit open-market equity purchases "
            "in official NSE Regulation 7(2) PIT disclosures. No price/return outcome consumed."
        ),
        "generated_at_utc": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "source": {
            "endpoint": "https://www.nseindia.com/api/corporates-pit",
            "type": "individual",
            "from_date": args.from_date,
            "to_date": args.to_date,
            "raw_sha256": _sha256(raw),
            "raw_byte_count": len(raw),
        },
        "summary": {
            "row_count": len(rows),
            "symbol_count": len(symbols),
            "unique_xbrl_count": len(unique_xbrls),
            "market_purchase_row_count": len(market_purchase_rows),
            "market_purchase_symbol_count": len(market_purchase_symbols),
            "direct_actor_event_count": len(direct),
            "direct_actor_symbol_count": len({event["symbol"] for event in direct}),
            "broad_actor_event_count": len(broad),
            "broad_actor_symbol_count": len({event["symbol"] for event in broad}),
        },
        "person_category_counts": dict(category_counts.most_common()),
        "acquisition_mode_counts": dict(mode_counts.most_common()),
        "transaction_type_counts": dict(transaction_counts.most_common()),
        "direct_actor_categories": sorted(DIRECT_ACTOR_CATEGORIES),
        "broad_actor_categories": sorted(BROAD_ACTOR_CATEGORIES),
        "direct_actor_market_purchase_events": direct,
        "broad_actor_market_purchase_events": broad,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out, report)
    print(json.dumps(report["summary"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
