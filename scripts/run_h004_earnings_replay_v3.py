#!/usr/bin/env python3
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from marketlab.nse import NSEClient

import run_h004_earnings_replay_v2 as replay

LEGACY_START = date(2024, 7, 1)
LEGACY_END = date(2025, 9, 30)
_LEGACY_INDEX: dict[tuple[str, str], list[dict[str, Any]]] | None = None
_BASE_XBRL_METRICS = replay.xbrl_period_metrics


def operating_xbrl_period_metrics(raw: bytes) -> dict[str, Any] | None:
    metrics = _BASE_XBRL_METRICS(raw)
    if metrics is None:
        return None
    pbei = metrics["profit_before_exceptional_and_tax_inr"]
    finance = metrics["finance_costs_inr"]
    depreciation = metrics["depreciation_inr"]
    other_income = metrics.get("other_income_inr") or 0.0
    revenue = metrics["revenue_inr"]
    operating_ebitda = pbei - other_income + finance + depreciation
    metrics["ebitda_proxy_inr"] = operating_ebitda
    metrics["ebitda_margin_pct"] = operating_ebitda / revenue * 100.0
    metrics["ebitda_proxy_definition"] = (
        "profit_before_exceptional_and_tax - other_income + finance_costs + depreciation"
    )
    return metrics


def two_month_chunks(start: date, end: date):
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        second_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        last_day = calendar.monthrange(second_month.year, second_month.month)[1]
        chunk_end = date(second_month.year, second_month.month, last_day)
        yield max(start, cursor), min(end, chunk_end)
        cursor = chunk_end + timedelta(days=1)


def bulk_legacy_index(client: NSEClient) -> dict[tuple[str, str], list[dict[str, Any]]]:
    global _LEGACY_INDEX
    if _LEGACY_INDEX is not None:
        return _LEGACY_INDEX
    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    total_rows = 0
    for start, end in two_month_chunks(LEGACY_START, LEGACY_END):
        payload, _ = client._json_get_with_raw(
            replay.LEGACY_FINANCIALS,
            params={
                "index": "equities",
                "period": "Quarterly",
                "from_date": start.strftime("%d-%m-%Y"),
                "to_date": end.strftime("%d-%m-%Y"),
            },
        )
        rows = payload if isinstance(payload, list) else []
        total_rows += len(rows)
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").strip().upper()
            qe = replay.parse_legacy_quarter_end(row.get("toDate"))
            published = replay.parse_legacy_broadcast(row.get("broadCastDate"))
            url = replay.valid_xbrl_url(row.get("xbrl"))
            if not symbol or not qe or not published or not url:
                continue
            index[(symbol, replay.basis_of(row))].append(row)
        print(f"legacy bulk {start}..{end}: rows={len(rows)} indexed_keys={len(index)}")
    for group in index.values():
        group.sort(key=lambda item: replay.parse_legacy_broadcast(item.get("broadCastDate")))
    print(f"legacy bulk total_rows={total_rows} indexed_keys={len(index)}")
    _LEGACY_INDEX = index
    return index


def bulk_prior_filing(
    client: NSEClient,
    prior_index: dict[tuple[str, str], list[dict[str, Any]]],
    current: dict[str, Any],
    unused_cache: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str | None]:
    integrated = replay.integrated_prior(prior_index, current)
    if integrated is not None:
        return integrated, "INTEGRATED"

    symbol = str(current.get("symbol") or "").strip().upper()
    current_qe = replay.parse_integrated_quarter_end(current.get("qe_Date"))
    if not symbol or not current_qe:
        return None, None
    target = replay.previous_year_day(current_qe)
    cutoff = replay.current_broadcast(current)
    candidates = []
    for row in bulk_legacy_index(client).get((symbol, replay.basis_of(current)), []):
        qe = replay.parse_legacy_quarter_end(row.get("toDate"))
        published = replay.parse_legacy_broadcast(row.get("broadCastDate"))
        if not qe or not published or published >= cutoff:
            continue
        if abs((qe - target).days) > 7:
            continue
        candidates.append((published, row))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1], "LEGACY_BULK"


if __name__ == "__main__":
    replay.xbrl_period_metrics = operating_xbrl_period_metrics
    replay.prior_filing = bulk_prior_filing
    replay.main()
