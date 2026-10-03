from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest

RADAR_ID = "RR001-v1"
CLASSIFICATION = "RESEARCH_PRIORITY_ONLY_NO_EXPECTED_RETURN"
SHORTLIST_SIZE = 15
SECTOR_CAP_PER_SHORTLIST = 2


def _finite_or_none(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _rank_percentiles(
    values: dict[str, float | None],
    *,
    higher_is_better: bool = True,
) -> dict[str, float | None]:
    valid = [(symbol, value) for symbol, value in values.items() if value is not None]
    valid.sort(key=lambda item: (float(item[1]), item[0]))
    result: dict[str, float | None] = {symbol: None for symbol in values}
    count = len(valid)
    if count == 0:
        return result
    if count == 1:
        result[valid[0][0]] = 0.5
        return result

    index = 0
    while index < count:
        end = index + 1
        value = valid[index][1]
        while end < count and valid[end][1] == value:
            end += 1
        average_position = (index + end - 1) / 2.0
        percentile = average_position / (count - 1)
        if not higher_is_better:
            percentile = 1.0 - percentile
        for position in range(index, end):
            result[valid[position][0]] = percentile
        index = end
    return result


def _score(
    symbols: list[str],
    components: list[dict[str, float | None]],
) -> dict[str, float]:
    if not components:
        raise ValueError("RR001 score requires components")
    scores: dict[str, float] = {}
    denominator = float(len(components))
    for symbol in symbols:
        total = sum(
            float(component[symbol])
            for component in components
            if component.get(symbol) is not None
        )
        scores[symbol] = 100.0 * total / denominator
    return scores


def _exact_row(
    session: dict[str, Any],
    *,
    symbol: str,
    isin: str,
) -> dict[str, Any] | None:
    matches = [
        row
        for row in session.get("equities", [])
        if str(row.get("symbol") or "") == symbol
        and str(row.get("isin") or "") == isin
    ]
    if len(matches) > 1:
        raise AlphaContractError(
            f"RR001 duplicate identity in session: {symbol}/{isin}"
        )
    return matches[0] if matches else None


def _strict_window(
    sessions: list[dict[str, Any]],
    *,
    symbol: str,
    isin: str,
    length: int,
) -> list[dict[str, Any]] | None:
    if len(sessions) < length:
        return None
    rows = [
        _exact_row(session, symbol=symbol, isin=isin)
        for session in sessions[-length:]
    ]
    return None if any(row is None for row in rows) else list(rows)  # type: ignore[arg-type]


def _benchmark_return(
    sessions: list[dict[str, Any]],
    *,
    sessions_back: int,
) -> float | None:
    if len(sessions) < sessions_back + 1:
        return None
    start = _finite_or_none(sessions[-(sessions_back + 1)]["benchmark"].get("close_price"))
    end = _finite_or_none(sessions[-1]["benchmark"].get("close_price"))
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1.0


def _stock_return(rows: list[dict[str, Any]] | None) -> float | None:
    if not rows:
        return None
    start = _finite_or_none(rows[0].get("close_price"))
    end = _finite_or_none(rows[-1].get("close_price"))
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1.0


def _distance_from_high(rows: list[dict[str, Any]] | None) -> float | None:
    if not rows:
        return None
    current = _finite_or_none(rows[-1].get("close_price"))
    highs = [_finite_or_none(row.get("high_price")) for row in rows]
    if current is None or any(value is None for value in highs):
        return None
    trailing_high = max(float(value) for value in highs if value is not None)
    return current / trailing_high - 1.0 if trailing_high > 0 else None


def _turnover_surprise(rows: list[dict[str, Any]] | None) -> float | None:
    if rows is None or len(rows) < 21:
        return None
    current = _finite_or_none(rows[-1].get("turnover_inr"))
    prior = [_finite_or_none(row.get("turnover_inr")) for row in rows[-21:-1]]
    if current is None or any(value is None for value in prior):
        return None
    median = statistics.median(float(value) for value in prior if value is not None)
    return current / median if median > 0 else None


def _sector_balanced(
    records: list[dict[str, Any]],
    *,
    limit: int = SHORTLIST_SIZE,
    sector_cap: int = SECTOR_CAP_PER_SHORTLIST,
) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    selected = []
    for record in records:
        industry = str(record["industry"])
        if counts[industry] >= sector_cap:
            continue
        selected.append(record)
        counts[industry] += 1
        if len(selected) >= limit:
            break
    return selected


def _context_map(h022_signal_ledger: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not h022_signal_ledger:
        return {}
    rows = h022_signal_ledger.get("records", [])
    if not isinstance(rows, list):
        raise AlphaContractError("RR001 H022 records must be a list")
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        latest[symbol] = {
            "primary_signal": _finite_or_none(row.get("primary_signal")),
            "signal_status": row.get("signal_status"),
            "signal_frozen_at_utc": row.get("signal_frozen_at_utc"),
        }
    return latest


def build_research_priority_radar(
    *,
    universe: dict[str, Any],
    consensus_snapshot: dict[str, Any],
    market_panel: dict[str, Any],
    consensus_payload_sha256: str,
    h022_signal_ledger: dict[str, Any] | None = None,
    h023_event_count: int = 0,
    h024_primary_event_count: int = 0,
) -> dict[str, Any]:
    if universe.get("selection_size") != 100:
        raise AlphaContractError("RR001 requires frozen 100-name U001")
    members = universe.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise AlphaContractError("RR001 U001 member count must equal 100")
    if consensus_snapshot.get("outcomes_opened") is not False:
        raise AlphaContractError("RR001 consensus input must have unopened outcomes")
    if consensus_snapshot.get("universe_git_blob_sha") != "8026e81faee3e913d2fba1dba72d60603b69fa07":
        raise AlphaContractError("RR001 consensus input differs from frozen U001")

    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or len(sessions) < 61:
        raise AlphaContractError("RR001 requires at least 61 official NSE sessions")
    session_dates = [str(row.get("session_date") or "") for row in sessions]
    if session_dates != sorted(session_dates) or len(session_dates) != len(set(session_dates)):
        raise AlphaContractError("RR001 market sessions are not canonical")
    as_of_session = session_dates[-1]
    capture_date = str(consensus_snapshot.get("capture_date_ist") or "")
    if not capture_date or capture_date > as_of_session:
        raise AlphaContractError("RR001 consensus capture occurs after market as-of session")

    consensus_rows = consensus_snapshot.get("observations")
    if not isinstance(consensus_rows, list):
        raise AlphaContractError("RR001 consensus observations missing")
    consensus_by_symbol = {
        str(row["symbol"]): row
        for row in consensus_rows
        if isinstance(row, dict) and row.get("symbol")
    }
    universe_symbols = [str(row["symbol"]) for row in members]
    if set(consensus_by_symbol) != set(universe_symbols):
        raise AlphaContractError("RR001 consensus symbol set differs from frozen U001")

    benchmark_20 = _benchmark_return(sessions, sessions_back=20)
    benchmark_60 = _benchmark_return(sessions, sessions_back=60)
    if benchmark_20 is None or benchmark_60 is None:
        raise AlphaContractError("RR001 benchmark history is incomplete")

    raw: dict[str, dict[str, Any]] = {}
    h022_context = _context_map(h022_signal_ledger)
    for member in members:
        symbol = str(member["symbol"])
        isin = str(member["isin"])
        current = _exact_row(sessions[-1], symbol=symbol, isin=isin)
        window21 = _strict_window(
            sessions, symbol=symbol, isin=isin, length=21
        )
        window61 = _strict_window(
            sessions, symbol=symbol, isin=isin, length=61
        )
        current_close = (
            _finite_or_none(current.get("close_price"))
            if current is not None
            else None
        )
        stock_20 = _stock_return(window21)
        stock_60 = _stock_return(window61)
        consensus = consensus_by_symbol[symbol]
        target = _finite_or_none(consensus.get("target_price_inr"))
        target_upside = (
            target / current_close - 1.0
            if target is not None
            and current_close is not None
            and current_close > 0
            else None
        )
        analyst_count = consensus.get("analyst_count")
        reliable_consensus = (
            isinstance(analyst_count, int)
            and not isinstance(analyst_count, bool)
            and analyst_count >= 5
        )

        raw[symbol] = {
            "symbol": symbol,
            "isin": isin,
            "company_name": member["company_name"],
            "industry": member["constituent_industry"],
            "universe_rank": member["rank"],
            "ffmc": member["ffmc"],
            "current_close": current_close,
            "relative_momentum_20": (
                stock_20 - benchmark_20 if stock_20 is not None else None
            ),
            "relative_momentum_60": (
                stock_60 - benchmark_60 if stock_60 is not None else None
            ),
            "distance_from_high_20": _distance_from_high(
                window21[-20:] if window21 else None
            ),
            "turnover_surprise_20": _turnover_surprise(window21),
            "revenue_growth_forecast_pct": _finite_or_none(
                consensus.get("revenue_growth_forecast_pct")
            ) if reliable_consensus else None,
            "profit_growth_estimate_pct": _finite_or_none(
                consensus.get("profit_growth_estimate_pct")
            ) if reliable_consensus else None,
            "consensus_target_upside": (
                target_upside if reliable_consensus else None
            ),
            "analyst_count": analyst_count,
            "consensus_primary_reliable": reliable_consensus,
            "consensus_data_state": consensus.get("data_state"),
            "h022_context": h022_context.get(symbol),
        }

    symbols = sorted(raw)
    short_rel20 = _rank_percentiles(
        {symbol: raw[symbol]["relative_momentum_20"] for symbol in symbols}
    )
    short_high20 = _rank_percentiles(
        {symbol: raw[symbol]["distance_from_high_20"] for symbol in symbols}
    )
    short_turnover = _rank_percentiles(
        {symbol: raw[symbol]["turnover_surprise_20"] for symbol in symbols}
    )

    mid_rel60 = _rank_percentiles(
        {symbol: raw[symbol]["relative_momentum_60"] for symbol in symbols}
    )
    growth_revenue = _rank_percentiles(
        {symbol: raw[symbol]["revenue_growth_forecast_pct"] for symbol in symbols}
    )
    growth_profit = _rank_percentiles(
        {symbol: raw[symbol]["profit_growth_estimate_pct"] for symbol in symbols}
    )
    target_upside = _rank_percentiles(
        {symbol: raw[symbol]["consensus_target_upside"] for symbol in symbols}
    )

    short_score = _score(
        symbols,
        [short_rel20, short_high20, short_turnover],
    )
    mid_score = _score(
        symbols,
        [mid_rel60, growth_revenue, growth_profit, target_upside],
    )
    long_score = _score(
        symbols,
        [growth_revenue, growth_profit, target_upside],
    )

    records = []
    for symbol in symbols:
        row = raw[symbol]
        record = {
            **row,
            "components": {
                "short": {
                    "relative_momentum_20_percentile": short_rel20[symbol],
                    "distance_from_high_20_percentile": short_high20[symbol],
                    "turnover_surprise_20_percentile": short_turnover[symbol],
                },
                "mid": {
                    "relative_momentum_60_percentile": mid_rel60[symbol],
                    "revenue_growth_percentile": growth_revenue[symbol],
                    "profit_growth_percentile": growth_profit[symbol],
                    "target_upside_percentile": target_upside[symbol],
                },
                "long": {
                    "revenue_growth_percentile": growth_revenue[symbol],
                    "profit_growth_percentile": growth_profit[symbol],
                    "target_upside_percentile": target_upside[symbol],
                },
            },
            "research_priority_score": {
                "short": short_score[symbol],
                "mid": mid_score[symbol],
                "long": long_score[symbol],
            },
        }
        records.append(record)

    def ranked(horizon: str) -> list[dict[str, Any]]:
        rows = sorted(
            records,
            key=lambda row: (
                -float(row["research_priority_score"][horizon]),
                int(row["universe_rank"]),
                str(row["symbol"]),
            ),
        )
        return [
            {
                "rank": rank,
                "symbol": row["symbol"],
                "company_name": row["company_name"],
                "industry": row["industry"],
                "priority_score": row["research_priority_score"][horizon],
                "universe_rank": row["universe_rank"],
                "relative_momentum_20": row["relative_momentum_20"],
                "relative_momentum_60": row["relative_momentum_60"],
                "revenue_growth_forecast_pct": row[
                    "revenue_growth_forecast_pct"
                ],
                "profit_growth_estimate_pct": row[
                    "profit_growth_estimate_pct"
                ],
                "consensus_target_upside": row["consensus_target_upside"],
                "analyst_count": row["analyst_count"],
                "h022_context": row["h022_context"],
            }
            for rank, row in enumerate(rows, start=1)
        ]

    ranked_views = {
        horizon: ranked(horizon)
        for horizon in ("short", "mid", "long")
    }
    shortlists = {
        horizon: _sector_balanced(ranked_views[horizon])
        for horizon in ("short", "mid", "long")
    }

    report: dict[str, Any] = {
        "schema_version": 1,
        "radar_id": RADAR_ID,
        "classification": CLASSIFICATION,
        "as_of_market_session": as_of_session,
        "market_panel_sha256": market_panel["panel_sha256"],
        "market_session_count": len(sessions),
        "market_source_start": session_dates[0],
        "market_source_end": session_dates[-1],
        "benchmark_20_return": benchmark_20,
        "benchmark_60_return": benchmark_60,
        "universe_id": universe["cohort_id"],
        "universe_sha256": universe["sha256"],
        "universe_member_count": len(members),
        "consensus_capture_id": consensus_snapshot["logical_capture_id"],
        "consensus_capture_date": capture_date,
        "consensus_payload_sha256": consensus_payload_sha256,
        "consensus_source_version": consensus_snapshot["source_version"],
        "h022_signal_ledger_sha256": (
            h022_signal_ledger.get("ledger_sha256")
            if h022_signal_ledger
            else None
        ),
        "h023_event_count": int(h023_event_count),
        "h024_primary_event_count": int(h024_primary_event_count),
        "score_contract": {
            "short": [
                "EQUAL_WEIGHT_PERCENTILE:20D_STOCK_MINUS_NIFTY500_RETURN",
                "EQUAL_WEIGHT_PERCENTILE:DISTANCE_FROM_20D_HIGH",
                "EQUAL_WEIGHT_PERCENTILE:CURRENT_TURNOVER_VS_PRIOR20_MEDIAN",
            ],
            "mid": [
                "EQUAL_WEIGHT_PERCENTILE:60D_STOCK_MINUS_NIFTY500_RETURN",
                "EQUAL_WEIGHT_PERCENTILE:CURRENT_FORWARD_REVENUE_GROWTH",
                "EQUAL_WEIGHT_PERCENTILE:CURRENT_FORWARD_PROFIT_GROWTH",
                "EQUAL_WEIGHT_PERCENTILE:CONSENSUS_TARGET_UPSIDE",
            ],
            "long": [
                "EQUAL_WEIGHT_PERCENTILE:CURRENT_FORWARD_REVENUE_GROWTH",
                "EQUAL_WEIGHT_PERCENTILE:CURRENT_FORWARD_PROFIT_GROWTH",
                "EQUAL_WEIGHT_PERCENTILE:CONSENSUS_TARGET_UPSIDE",
            ],
            "missing_component_policy": "ZERO_CONTRIBUTION_NO_IMPUTATION",
            "consensus_reliability_gate": "ANALYST_COUNT_AT_LEAST_5",
            "weights_tuned_on_return_outcomes": False,
        },
        "shortlist_contract": {
            "size": SHORTLIST_SIZE,
            "maximum_names_per_constituent_industry": SECTOR_CAP_PER_SHORTLIST,
            "purpose": "DEEP_RESEARCH_QUEUE_NOT_PORTFOLIO_SELECTION",
        },
        "shortlists": shortlists,
        "top_25_raw": {
            horizon: ranked_views[horizon][:25]
            for horizon in ("short", "mid", "long")
        },
        "company_records": records,
        "outcomes_opened": False,
        "validated_expected_return_claim_allowed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    report["radar_sha256"] = digest(report)
    return report


def render_radar_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# RR001 Research Priority Radar — {report['as_of_market_session']}",
        "",
        "Research prioritization only. This is not a return forecast, buy list, or PF001 eligibility decision.",
        "",
        "## Frozen inputs",
        "",
        f"- U001: {report['universe_member_count']} non-financial Nifty 200 names",
        f"- market through: {report['as_of_market_session']}",
        f"- consensus capture: {report['consensus_capture_id']}",
        "- H022/H023/H024 are context only and do not change the score.",
        "",
    ]
    titles = {
        "short": "Short-horizon research queue",
        "mid": "Mid-horizon research queue",
        "long": "Long-horizon research queue",
    }
    for horizon in ("short", "mid", "long"):
        lines.extend(
            [
                f"## {titles[horizon]}",
                "",
                "| # | Symbol | Industry | Priority | 20D rel | 60D rel | Rev g. | Profit g. | Target upside |",
                "|---:|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for idx, row in enumerate(report["shortlists"][horizon], start=1):
            def pct(value: object) -> str:
                if value is None:
                    return "—"
                return f"{float(value) * 100:.1f}%"

            def pp(value: object) -> str:
                if value is None:
                    return "—"
                return f"{float(value):.1f}%"

            lines.append(
                "| "
                + " | ".join(
                    [
                        str(idx),
                        str(row["symbol"]),
                        str(row["industry"]),
                        f"{float(row['priority_score']):.1f}",
                        pct(row["relative_momentum_20"]),
                        pct(row["relative_momentum_60"]),
                        pp(row["revenue_growth_forecast_pct"]),
                        pp(row["profit_growth_estimate_pct"]),
                        pct(row["consensus_target_upside"]),
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "",
            "- Scores are equal-weight percentile heuristics frozen before this output was opened.",
            "- Missing consensus components contribute zero rather than being imputed.",
            "- Analyst count must be at least 5 for consensus-derived components.",
            "- Sector balancing caps each shortlist at two names per frozen constituent industry.",
            "- A name on this radar still requires a sealed Analyst Decision Object before PF001 can act.",
            "- If RR001 is ever tested as a return-predictive rule, that must be a new preregistered outcome-bearing trial and enter RTA001 first.",
            "",
        ]
    )
    return "\n".join(lines)
