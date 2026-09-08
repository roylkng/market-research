#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from marketlab.nse import NSEClient, NSEEndpoint

import run_h004_earnings_replay as base

PRIMARY_TURNOVER = 20_000_000.0
DISCOVERY_TURNOVER = 2_500_000.0
STAGE1_VALID_SESSIONS = 10
LEGACY_FINANCIALS = NSEEndpoint(
    "legacy_financials",
    "https://www.nseindia.com/api/corporates-financial-results",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-start", default="2025-10-01")
    parser.add_argument("--event-end", default="2026-07-31")
    parser.add_argument("--price-start", default="2025-05-01")
    parser.add_argument("--price-end", default="2026-08-31")
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def parse_integrated_quarter_end(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.title(), fmt).date()
        except ValueError:
            continue
    return None


def parse_legacy_quarter_end(value: Any) -> date | None:
    return parse_integrated_quarter_end(value)


def previous_year_day(value: date) -> date:
    return base.previous_year(value)


def basis_of(row: dict[str, Any]) -> str:
    token = str(row.get("consolidated") or "").strip().casefold()
    return "C" if token == "consolidated" else "S"


def valid_xbrl_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if text.startswith("https://nsearchives.nseindia.com/") and not text.endswith("/-"):
        return text
    return None


def xbrl_period_metrics(raw: bytes) -> dict[str, Any] | None:
    try:
        facts, contexts = base.facts_and_contexts(raw)
    except Exception:
        return None
    ctx = base.primary_context(facts)
    if not ctx:
        return None
    meta = contexts.get(ctx) or {}
    start = base.parse_iso_date(meta.get("start"))
    end = base.parse_iso_date(meta.get("end"))
    if not start or not end:
        return None
    duration_days = (end - start).days + 1
    if duration_days < 70 or duration_days > 110:
        return None

    revenue = base.fact(facts, ["RevenueFromOperations"], ctx)
    pbei = base.fact(
        facts,
        [
            "ProfitBeforeExceptionalItemsAndTax",
            "ProfitBeforeExceptionalItemsAndTaxShareOfProfitLossOfAssociatesJointVentures",
        ],
        ctx,
    )
    pbt = base.fact(facts, ["ProfitBeforeTax"], ctx)
    exceptional = base.fact(facts, ["ExceptionalItemsBeforeTax", "ExceptionalItems"], ctx)
    finance = base.fact(facts, ["FinanceCosts"], ctx)
    depreciation = base.fact(
        facts,
        [
            "DepreciationDepletionAndAmortisationExpense",
            "DepreciationAndAmortisationExpense",
            "DepreciationExpense",
        ],
        ctx,
    )
    pat = base.fact(
        facts,
        ["ProfitLossForPeriod", "ProfitLossForPeriodFromContinuingOperations"],
        ctx,
    )
    other_income = base.fact(facts, ["OtherIncome"], ctx)
    if pbei is None and pbt is not None:
        pbei = pbt - (exceptional or 0.0)
    if any(value is None for value in (revenue, pbei, finance, depreciation, pat)):
        return None
    if revenue <= 0:
        return None
    ebitda_proxy = pbei + finance + depreciation
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "duration_days": duration_days,
        "revenue_inr": revenue,
        "profit_before_exceptional_and_tax_inr": pbei,
        "finance_costs_inr": finance,
        "depreciation_inr": depreciation,
        "ebitda_proxy_inr": ebitda_proxy,
        "ebitda_margin_pct": ebitda_proxy / revenue * 100.0,
        "pat_inr": pat,
        "pat_crore": pat / 10_000_000.0,
        "other_income_inr": other_income,
        "exceptional_inr": exceptional,
        "pbt_inr": pbt,
    }


def positive_growth(current: float, prior: float) -> float | None:
    if prior <= 0:
        return None
    return (current / prior - 1.0) * 100.0


def compare_periods(current: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    revenue_yoy = positive_growth(current["revenue_inr"], prior["revenue_inr"])
    ebitda_yoy = positive_growth(current["ebitda_proxy_inr"], prior["ebitda_proxy_inr"])
    pat_yoy = positive_growth(current["pat_inr"], prior["pat_inr"])
    margin_change = current["ebitda_margin_pct"] - prior["ebitda_margin_pct"]
    tests = {
        "revenue_yoy_gte_20": revenue_yoy is not None and revenue_yoy >= 20.0,
        "ebitda_yoy_gte_30": ebitda_yoy is not None and ebitda_yoy >= 30.0,
        "pat_yoy_gte_40": pat_yoy is not None and pat_yoy >= 40.0,
        "margin_change_gte_1pp": margin_change >= 1.0,
    }
    anchor = all(tests.values()) and current["pat_crore"] >= 2.0
    nonoperating_share = None
    if current.get("pbt_inr") not in (None, 0):
        nonoperating = abs(current.get("other_income_inr") or 0.0) + abs(
            current.get("exceptional_inr") or 0.0
        )
        nonoperating_share = nonoperating / abs(current["pbt_inr"])
    return {
        "revenue_yoy_pct": revenue_yoy,
        "ebitda_yoy_pct": ebitda_yoy,
        "pat_yoy_pct": pat_yoy,
        "margin_change_pp": margin_change,
        "earnings_tests": tests,
        "earnings_anchor": anchor,
        "quality_warning_nonoperating": (
            nonoperating_share is not None and nonoperating_share >= 0.30
        ),
        "nonoperating_share_of_pbt": nonoperating_share,
    }


def integrated_prior_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    result: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        qe = parse_integrated_quarter_end(row.get("qe_Date"))
        url = valid_xbrl_url(row.get("xbrl"))
        if not symbol or not qe or not url:
            continue
        result[(symbol, basis_of(row))].append(row)
    for group in result.values():
        group.sort(key=lambda item: str(item.get("broadcast_Date") or ""))
    return result


def current_broadcast(row: dict[str, Any]) -> datetime:
    return base.parse_broadcast(str(row["broadcast_Date"]))


def integrated_prior(
    index: dict[tuple[str, str], list[dict[str, Any]]],
    current: dict[str, Any],
) -> dict[str, Any] | None:
    symbol = str(current.get("symbol") or "").strip().upper()
    current_qe = parse_integrated_quarter_end(current.get("qe_Date"))
    if not symbol or not current_qe:
        return None
    target = previous_year_day(current_qe)
    cutoff = current_broadcast(current)
    candidates = []
    for row in index.get((symbol, basis_of(current)), []):
        qe = parse_integrated_quarter_end(row.get("qe_Date"))
        if not qe or abs((qe - target).days) > 7:
            continue
        try:
            published = current_broadcast(row)
        except (KeyError, ValueError):
            continue
        if published >= cutoff:
            continue
        candidates.append((published, row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def legacy_rows_for_symbol(
    client: NSEClient,
    symbol: str,
    cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    if symbol in cache:
        return cache[symbol]
    payload, _ = client._json_get_with_raw(
        LEGACY_FINANCIALS,
        params={"index": "equities", "period": "Quarterly", "symbol": symbol},
    )
    rows = payload if isinstance(payload, list) else []
    cache[symbol] = [row for row in rows if isinstance(row, dict)]
    time.sleep(0.03)
    return cache[symbol]


def parse_legacy_broadcast(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d-%b-%Y %H:%M:%S")
    except ValueError:
        return None


def legacy_prior(
    client: NSEClient,
    current: dict[str, Any],
    cache: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    symbol = str(current.get("symbol") or "").strip().upper()
    current_qe = parse_integrated_quarter_end(current.get("qe_Date"))
    if not symbol or not current_qe:
        return None
    target = previous_year_day(current_qe)
    cutoff = current_broadcast(current)
    desired_basis = basis_of(current)
    candidates = []
    for row in legacy_rows_for_symbol(client, symbol, cache):
        qe = parse_legacy_quarter_end(row.get("toDate"))
        if not qe or abs((qe - target).days) > 7:
            continue
        if basis_of(row) != desired_basis:
            continue
        url = valid_xbrl_url(row.get("xbrl"))
        published = parse_legacy_broadcast(row.get("broadCastDate"))
        if not url or not published or published >= cutoff:
            continue
        candidates.append((published, row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def prior_filing(
    client: NSEClient,
    prior_index: dict[tuple[str, str], list[dict[str, Any]]],
    current: dict[str, Any],
    legacy_cache: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str | None]:
    row = integrated_prior(prior_index, current)
    if row is not None:
        return row, "INTEGRATED"
    row = legacy_prior(client, current, legacy_cache)
    if row is not None:
        return row, "LEGACY"
    return None, None


def event_pre_index(rows: list[dict[str, Any]], decision_idx: int, broadcast: datetime) -> int | None:
    decision_date = rows[decision_idx]["date"]
    if broadcast.date() == decision_date and broadcast.time() > datetime.strptime(
        "15:30:00", "%H:%M:%S"
    ).time():
        return decision_idx
    return decision_idx - 1 if decision_idx >= 1 else None


def missed_reason(record: dict[str, Any]) -> str | None:
    if not record["reference_outcome"]["explosive_20d"]:
        return None
    if not record["pre_momentum_eligible"]:
        return "PRE_MOMENTUM_RULE"
    if not record["earnings_anchor"]:
        return "NO_EARNINGS_INFLECTION"
    if record.get("h004_trigger_outcome") is None:
        return "NO_STAGE2_TRIGGER"
    return None


def summarize_v2(records: list[dict[str, Any]], coverage: dict[str, int]) -> dict[str, Any]:
    primary = [row for row in records if row["primary_universe"]]
    future = [row for row in primary if row["reference_outcome"]["explosive_20d"]]
    stage1 = [row for row in primary if row["stage1_eligible"]]
    stage2 = [row for row in stage1 if row.get("h004_trigger_outcome") is not None]
    hits = [row for row in stage2 if row["h004_trigger_outcome"]["explosive_20d"]]
    stage1_future = [row for row in future if row["stage1_eligible"]]
    stage2_future = [row for row in future if row.get("h004_trigger_outcome") is not None]
    baseline = [row for row in primary if row.get("baseline_trigger_outcome") is not None]
    baseline_hits = [row for row in baseline if row["baseline_trigger_outcome"]["explosive_20d"]]
    baseline_future = [row for row in future if row.get("baseline_trigger_outcome") is not None]
    strict_stage2 = [row for row in stage2 if not row["quality_warning_nonoperating"]]
    strict_hits = [row for row in strict_stage2 if row["h004_trigger_outcome"]["explosive_20d"]]
    leads = [row["h004_trigger_outcome"]["lead_sessions_to_25pct"] for row in hits]
    leads = [value for value in leads if value is not None]
    miss_counts: dict[str, int] = defaultdict(int)
    for row in future:
        reason = missed_reason(row)
        if reason:
            miss_counts[reason] += 1

    quarter_stats: dict[str, Any] = {}
    for quarter in sorted({row["quarter"] for row in primary}):
        qrows = [row for row in primary if row["quarter"] == quarter]
        qfuture = [row for row in qrows if row["reference_outcome"]["explosive_20d"]]
        qstage2 = [row for row in qrows if row.get("h004_trigger_outcome") is not None]
        qhits = [row for row in qstage2 if row["h004_trigger_outcome"]["explosive_20d"]]
        quarter_stats[quarter] = {
            "events": len(qrows),
            "future_explosive": len(qfuture),
            "stage2_signals": len(qstage2),
            "stage2_hits": len(qhits),
            "stage2_precision": len(qhits) / len(qstage2) if qstage2 else None,
            "stage2_recall": (
                len([row for row in qfuture if row.get("h004_trigger_outcome") is not None])
                / len(qfuture)
                if qfuture
                else None
            ),
        }

    return {
        "schema_version": 2,
        "experiment": "H004-HR002-EARNINGS-SUBENGINE-V2",
        "status": "HISTORICAL_RECONSTRUCTION_NOT_OUT_OF_SAMPLE",
        "live_capital_allowed": False,
        "stage1_valid_sessions": STAGE1_VALID_SESSIONS,
        "coverage": coverage,
        "counts": {
            "primary_evaluable_events": len(primary),
            "future_explosive_result_events": len(future),
            "stage1_signals": len(stage1),
            "stage2_signals": len(stage2),
            "stage2_hits": len(hits),
            "strict_quality_stage2_signals": len(strict_stage2),
            "strict_quality_stage2_hits": len(strict_hits),
            "result_event_tape_baseline_signals": len(baseline),
            "result_event_tape_baseline_hits": len(baseline_hits),
        },
        "metrics": {
            "stage1_recall_of_future_explosive_result_events": (
                len(stage1_future) / len(future) if future else None
            ),
            "stage2_recall_of_future_explosive_result_events": (
                len(stage2_future) / len(future) if future else None
            ),
            "stage2_precision": len(hits) / len(stage2) if stage2 else None,
            "strict_quality_stage2_precision": (
                len(strict_hits) / len(strict_stage2) if strict_stage2 else None
            ),
            "result_event_tape_baseline_recall": (
                len(baseline_future) / len(future) if future else None
            ),
            "result_event_tape_baseline_precision": (
                len(baseline_hits) / len(baseline) if baseline else None
            ),
            "median_lead_sessions_to_25pct": statistics.median(leads) if leads else None,
            "median_stage2_max_20d_return_pct": (
                statistics.median(row["h004_trigger_outcome"]["max_20d_return_pct"] for row in stage2)
                if stage2
                else None
            ),
            "median_stage2_close_20d_return_pct": (
                statistics.median(row["h004_trigger_outcome"]["close_20d_return_pct"] for row in stage2)
                if stage2
                else None
            ),
        },
        "miss_taxonomy": dict(sorted(miss_counts.items())),
        "by_calendar_quarter": quarter_stats,
    }


def main() -> None:
    args = parse_args()
    event_start = date.fromisoformat(args.event_start)
    event_end = date.fromisoformat(args.event_end)
    price_start = date.fromisoformat(args.price_start)
    price_end = date.fromisoformat(args.price_end)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions, prices = base.load_prices(price_start, price_end)
    print(f"prices sessions={len(sessions)} symbols={len(prices)}")

    client = NSEClient(timeout=20, attempts=4)
    all_integrated = base.fetch_filings(client, date(2025, 3, 1), event_end)
    current_filings = base.dedupe_filings(
        [
            row
            for row in all_integrated
            if event_start <= current_broadcast(row).date() <= event_end
        ]
    )
    priors = integrated_prior_index(all_integrated)
    legacy_cache: dict[str, list[dict[str, Any]]] = {}
    print(f"current result events={len(current_filings)}")

    coverage = defaultdict(int)
    records: list[dict[str, Any]] = []
    for number, filing in enumerate(current_filings, 1):
        coverage["current_filings"] += 1
        symbol = str(filing.get("symbol") or "").strip().upper()
        rows = prices.get(symbol)
        if not rows:
            coverage["missing_price_symbol"] += 1
            continue
        try:
            broadcast = current_broadcast(filing)
        except (KeyError, ValueError):
            coverage["invalid_broadcast"] += 1
            continue
        decision = base.decision_session(sessions, broadcast)
        if not decision:
            coverage["missing_decision_session"] += 1
            continue
        decision_idx = base.row_index(rows, decision)
        if decision_idx is None:
            coverage["missing_symbol_on_decision_session"] += 1
            continue
        pre_idx = event_pre_index(rows, decision_idx, broadcast)
        if pre_idx is None:
            coverage["missing_pre_event_session"] += 1
            continue
        pre = base.pre_event_features(rows, pre_idx)
        if pre is None:
            coverage["insufficient_price_history"] += 1
            continue
        if pre["median_20d_traded_value_inr"] < DISCOVERY_TURNOVER:
            coverage["below_discovery_liquidity"] += 1
            continue
        reference = base.event_reference_outcome(rows, decision_idx)
        if reference is None:
            coverage["insufficient_forward_price_history"] += 1
            continue
        coverage["market_evaluable_events"] += 1

        current_url = valid_xbrl_url(filing.get("xbrl"))
        if not current_url:
            coverage["missing_current_xbrl"] += 1
            continue
        try:
            current_raw = base.get_bytes(current_url)
        except RuntimeError:
            current_raw = None
        if not current_raw:
            coverage["current_xbrl_fetch_failure"] += 1
            continue
        current_metrics = xbrl_period_metrics(current_raw)
        if current_metrics is None:
            coverage["current_xbrl_not_quarterly_or_unparseable"] += 1
            continue

        try:
            prior_row, prior_source = prior_filing(client, priors, filing, legacy_cache)
        except Exception:
            prior_row, prior_source = None, None
        if prior_row is None:
            coverage["missing_prior_year_filing"] += 1
            continue
        prior_url = valid_xbrl_url(prior_row.get("xbrl"))
        if not prior_url:
            coverage["missing_prior_xbrl"] += 1
            continue
        try:
            prior_raw = base.get_bytes(prior_url)
        except RuntimeError:
            prior_raw = None
        if not prior_raw:
            coverage["prior_xbrl_fetch_failure"] += 1
            continue
        prior_metrics = xbrl_period_metrics(prior_raw)
        if prior_metrics is None:
            coverage["prior_xbrl_not_quarterly_or_unparseable"] += 1
            continue
        if abs(
            (date.fromisoformat(current_metrics["period_end"]) - previous_year_day(
                date.fromisoformat(prior_metrics["period_end"])
            )).days
        ) > 7:
            coverage["prior_period_mismatch"] += 1
            continue

        comparison = compare_periods(current_metrics, prior_metrics)
        pre_momentum = (
            pre["prior_5d_return_pct"] < 10.0
            and pre["prior_20d_return_pct"] < 20.0
            and pre["prior_1d_return_pct"] < 8.0
        )
        primary_universe = pre["median_20d_traded_value_inr"] >= PRIMARY_TURNOVER
        earnings_anchor = bool(comparison["earnings_anchor"])
        stage1 = pre_momentum and earnings_anchor

        baseline_idx, baseline_conditions = base.tape_trigger(rows, decision_idx)
        baseline_outcome = (
            base.outcome_from_entry(rows, baseline_idx + 1) if baseline_idx is not None else None
        )
        hidx = None
        hconditions: list[str] = []
        houtcome = None
        if stage1:
            hidx, hconditions = base.tape_trigger(rows, decision_idx)
            if hidx is not None:
                houtcome = base.outcome_from_entry(rows, hidx + 1)

        record = {
            "symbol": symbol,
            "company": filing.get("cmName") or filing.get("smName"),
            "basis": filing.get("consolidated"),
            "quarter_end": filing.get("qe_Date"),
            "broadcast": filing.get("broadcast_Date"),
            "decision_date": decision.isoformat(),
            "pre_event_reference_date": rows[pre_idx]["date"].isoformat(),
            "quarter": base.quarter_key(decision),
            "primary_universe": primary_universe,
            "median_20d_traded_value_inr": pre["median_20d_traded_value_inr"],
            "prior_1d_return_pct": pre["prior_1d_return_pct"],
            "prior_5d_return_pct": pre["prior_5d_return_pct"],
            "prior_20d_return_pct": pre["prior_20d_return_pct"],
            "pre_momentum_eligible": pre_momentum,
            "earnings_anchor": earnings_anchor,
            "stage1_eligible": stage1,
            "quality_warning_nonoperating": comparison["quality_warning_nonoperating"],
            "nonoperating_share_of_pbt": comparison["nonoperating_share_of_pbt"],
            "revenue_yoy_pct": comparison["revenue_yoy_pct"],
            "ebitda_yoy_pct": comparison["ebitda_yoy_pct"],
            "pat_yoy_pct": comparison["pat_yoy_pct"],
            "margin_change_pp": comparison["margin_change_pp"],
            "quarterly_pat_crore": current_metrics["pat_crore"],
            "current_period": current_metrics,
            "prior_period": prior_metrics,
            "prior_source": prior_source,
            "current_xbrl_url": current_url,
            "prior_xbrl_url": prior_url,
            "reference_outcome": reference,
            "baseline_trigger_date": (
                rows[baseline_idx]["date"].isoformat() if baseline_idx is not None else None
            ),
            "baseline_trigger_conditions": baseline_conditions,
            "baseline_trigger_outcome": baseline_outcome,
            "h004_trigger_date": rows[hidx]["date"].isoformat() if hidx is not None else None,
            "h004_trigger_conditions": hconditions,
            "h004_trigger_outcome": houtcome,
        }
        record["miss_reason_if_future_explosive"] = missed_reason(record)
        records.append(record)
        coverage["financially_evaluable_events"] += 1
        if number % 250 == 0:
            print(
                f"event progress={number}/{len(current_filings)} records={len(records)} "
                f"legacy_symbols={len(legacy_cache)}"
            )

    summary = summarize_v2(records, dict(sorted(coverage.items())))
    summary["event_window"] = {"start": event_start.isoformat(), "end": event_end.isoformat()}
    summary["price_window"] = {"start": price_start.isoformat(), "end": price_end.isoformat()}
    summary["data_contract"] = {
        "current_financials": "original NSE Integrated Filing Financials XBRL",
        "prior_financials": "same-basis same-quarter original NSE Integrated or legacy XBRL",
        "market_data": "official NSE UDiFF daily bhavcopy",
        "xbrl_units": "actual INR, normalized only for display PAT crore",
        "pre_event_price_policy": (
            "last close observable before filing; intraday filings use prior-session close proxy"
        ),
    }

    primary_records = [row for row in records if row["primary_universe"]]
    discovery_records = [row for row in records if not row["primary_universe"]]
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out_dir / "events.json").write_text(
        json.dumps(primary_records, indent=2, sort_keys=True) + "\n"
    )
    (out_dir / "discovery-events.json").write_text(
        json.dumps(discovery_records, indent=2, sort_keys=True) + "\n"
    )
    report = [
        "# H004-HR002 earnings subengine replay v2",
        "",
        "Status: **historical reconstruction, not out-of-sample validation**",
        "",
        "V1 was discarded before interpretation because its parser assumed the prior-year comparison was embedded in the current XBRL and misread display rounding as storage units. V2 compares two original NSE XBRL filings and treats XBRL numeric values as actual INR.",
        "",
        "This is the earnings-inflection subengine only. Corporate-catalyst and turnaround-only anchors, delivery-volume confirmation, sector-relative confirmation, a full-market momentum baseline, and Nifty 500 excess-return evaluation remain outside this subreplay.",
        "",
        "```json",
        json.dumps(summary, indent=2, sort_keys=True),
        "```",
        "",
        "The full H004 promotion gate remains closed unless the complete historical reconstruction and frozen prospective cohorts satisfy the predeclared requirements.",
    ]
    (out_dir / "RESULTS.md").write_text("\n".join(report) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
