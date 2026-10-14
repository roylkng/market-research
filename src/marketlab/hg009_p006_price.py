"""HG009-P006 frozen H1/H5 *unadjusted price-only* diagnostic.

This uses future original NSE price-source observations without modifying any
pre-entry cohort, and refuses missing intermediate NSE trading sessions.
It is not an equity total return, investor fill, causal alpha or advice.
"""

from __future__ import annotations

import copy
import math
import statistics
from datetime import UTC, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.calendar_snapshot import CalendarSnapshot
from marketlab.hg009_daily import (
    RECORD_ID as DAILY_RECORD_ID,
    validate_hg009_daily_snapshot,
)
from marketlab.hg009_p004_clock import (
    FIRST_ENTRY,
    PROTOCOL_ID,
    validate_hg009_outcome_clock,
)

EVAL_ID = "HG009-P006-CAUSAL-ORIGINAL-PRICE-DIAGNOSTIC-v1"
HORIZONS = (1, 5)
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
OBSERVED_STATE = "ORIGINAL_NSE_EQ_OHLC_OBSERVED_NOT_FILL"


def _utc(value: object, *, label: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise AlphaContractError(f"HG009 P006 {label} not ISO datetime") from exc
    if stamp.tzinfo is None:
        raise AlphaContractError(f"HG009 P006 {label} missing offset")
    return stamp.astimezone(UTC)


def _positive(value: Any, *, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise AlphaContractError(f"HG009 P006 invalid original {label}")
    return float(value)


def _identities(selected: dict, controls: dict) -> dict[str, dict[tuple[str, str], None]]:
    memberships = {
        "SELECTED": selected["selected"],
        "ONE_LANE": controls["controls"]["ONE_LANE"],
        "ZERO_LANE": controls["controls"]["ZERO_LANE"],
    }
    expected = {}
    total = set()
    for arm in ARMS:
        rows = memberships[arm]
        if len(rows) != 100:
            raise AlphaContractError(f"HG009 P006 {arm} lacks 100 frozen identities")
        pairs = {(x["symbol"], x["isin"]) for x in rows}
        if len(pairs) != 100 or total & pairs:
            raise AlphaContractError("HG009 P006 duplicate selected/control ISIN")
        expected[arm] = {key: None for key in pairs}
        total.update(pairs)
    if len(total) != 300:
        raise AlphaContractError("HG009 P006 frozen source identities missing")
    return expected


def _source_rows(
    *,
    packet: dict[str, Any],
    expected: dict[str, dict[tuple[str, str], None]],
) -> dict[tuple[str, str], dict[str, Any]]:
    validate_hg009_daily_snapshot(packet)
    if packet.get("record_id") != DAILY_RECORD_ID:
        raise AlphaContractError("HG009 P006 does not accept non-original source")
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    observed_by_arm = {arm: 0 for arm in ARMS}
    for row in packet["source_identity_rows"]:
        arm = row.get("arm")
        key = (row.get("symbol"), row.get("frozen_isin"))
        if arm not in expected or key not in expected[arm] or key in lookup:
            raise AlphaContractError("HG009 P006 original source membership/ISIN drift")
        if row.get("actual_trade_fill") is not False:
            raise AlphaContractError("HG009 P006 original OHLC is not executed fill")
        if row.get("corporate_action_adjusted") is not False:
            raise AlphaContractError("HG009 P006 source silently corporate-adjusted")
        if row.get("dividend_adjusted") is not False:
            raise AlphaContractError("HG009 P006 source silently dividend-adjusted")
        if row.get("exchange_series") != "EQ":
            raise AlphaContractError("HG009 P006 source is not NSE EQ")
        state = row.get("state")
        price = row.get("ohlcv")
        if state == OBSERVED_STATE:
            if not isinstance(price, dict):
                raise AlphaContractError("HG009 P006 observed stock lacks OHLC")
            op = _positive(price.get("open_inr"), label="EQ open")
            close = _positive(price.get("close_inr"), label="EQ close")
            low = _positive(price.get("low_inr"), label="EQ low")
            high = _positive(price.get("high_inr"), label="EQ high")
            if low > min(op, close) or high < max(op, close):
                raise AlphaContractError("HG009 P006 invalid NSE bar extrema")
            observed_by_arm[arm] += 1
        elif price is not None:
            raise AlphaContractError("HG009 P006 missing identity assigned OHLC")
        elif not isinstance(state, str) or not state:
            raise AlphaContractError("HG009 P006 missing source identity state")
        lookup[key] = row
    if len(lookup) != 300:
        raise AlphaContractError("HG009 P006 original 300 slots not preserved")
    for arm in ARMS:
        counts = packet["arm_coverage"].get(arm)
        if (
            not isinstance(counts, dict)
            or counts.get("declared") != 100
            or counts.get("observed_official_eq") != observed_by_arm[arm]
            or counts.get("missing_or_changed_identity") != (
                100 - observed_by_arm[arm]
            )
        ):
            raise AlphaContractError("HG009 P006 original 100-name coverage mismatch")
    return lookup


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "mean_price_change_pct_if_observed": None,
            "median_price_change_pct_if_observed": None,
            "minimum_price_change_pct_if_observed": None,
            "maximum_price_change_pct_if_observed": None,
        }
    prices = sorted(values)
    return {
        "mean_price_change_pct_if_observed": round(
            statistics.fmean(prices) * 100, 6
        ),
        "median_price_change_pct_if_observed": round(
            statistics.median(prices) * 100, 6
        ),
        "minimum_price_change_pct_if_observed": round(prices[0] * 100, 6),
        "maximum_price_change_pct_if_observed": round(prices[-1] * 100, 6),
    }


def build_hg009_price_only_diagnostic(
    *,
    horizon_sessions: int,
    protocol: dict[str, Any],
    calendar: CalendarSnapshot,
    original: dict[str, Any],
    selected: dict[str, Any],
    controls: dict[str, Any],
    market_snapshots: list[dict[str, Any]],
    evaluated_at_utc: str,
) -> dict[str, Any]:
    validate_hg009_outcome_clock(
        protocol,
        calendar=calendar,
        original=original,
        selected=selected,
        controls=controls,
    )
    if horizon_sessions not in HORIZONS:
        raise AlphaContractError(
            "HG009 P006 H20/H60 not cleared by original calendar"
        )
    plan = protocol["planned_horizon_status"][str(horizon_sessions)]
    if plan["state"] != "FROZEN_TRADING_DAY_SEQUENCE_READY_TO_COLLECT_SOURCE":
        raise AlphaContractError("HG009 P006 future calendar/horizon is blocked")
    dates = plan["date_scoped_holding_sessions"]
    if (
        not isinstance(dates, list)
        or len(dates) != horizon_sessions
        or dates[0] != FIRST_ENTRY
        or plan["official_exit_session"] != dates[-1]
    ):
        raise AlphaContractError("HG009 P006 future NSE holding-window altered")
    if len(market_snapshots) != horizon_sessions:
        raise AlphaContractError(
            "HG009 P006 missing original intermediate NSE source session"
        )
    observed_dates = [packet.get("date_ist") for packet in market_snapshots]
    if observed_dates != dates or len(set(observed_dates)) != len(dates):
        raise AlphaContractError(
            "HG009 P006 missing/shifted/duplicate NSE session, no substitution"
        )
    evaluated = _utc(evaluated_at_utc, label="evaluation")
    calendar_by_date = {s.session_date: s for s in calendar.sessions}
    if evaluated < _utc(
        calendar_by_date[dates[-1]].close_timestamp_utc, label="exit close"
    ):
        raise AlphaContractError("HG009 P006 evaluation before exit session close")

    expected = _identities(selected, controls)
    source_maps: list[dict[tuple[str, str], dict[str, Any]]] = []
    sources: list[dict[str, Any]] = []
    first_index_open = None
    last_index_close = None
    for day, packet in zip(dates, market_snapshots, strict=True):
        captured = _utc(packet["observed_recorded_at_utc"], label="market record")
        close = _utc(
            calendar_by_date[day].close_timestamp_utc,
            label="market session close",
        )
        if captured < close or captured > evaluated:
            raise AlphaContractError("HG009 P006 source record chronological conflict")
        if packet.get("exchange_session_close_utc") != close.isoformat():
            raise AlphaContractError("HG009 P006 market close differs from original")
        if packet.get("date_ist") != day:
            raise AlphaContractError("HG009 P006 original market source date mismatch")
        for original_field in (
            "h021_original_daily_packet_sha256",
            "original_market_source_sha256",
            "original_index_source_sha256",
        ):
            sha = packet.get(original_field)
            if (
                not isinstance(sha, str)
                or len(sha) != 64
                or any(c not in "0123456789abcdef" for c in sha)
            ):
                raise AlphaContractError("HG009 P006 missing original NSE source SHA")
        index = packet["benchmark"]
        if index.get("id") != "nifty_500":
            raise AlphaContractError("HG009 P006 index identity not Nifty 500")
        if index.get("basis") != "PRICE_INDEX_NOT_TOTAL_RETURN":
            raise AlphaContractError("HG009 P006 benchmark is not price index")
        op = _positive(index.get("open"), label="Nifty500 open")
        ix_close = _positive(index.get("close"), label="Nifty500 close")
        if first_index_open is None:
            first_index_open = op
        last_index_close = ix_close
        source_maps.append(_source_rows(packet=packet, expected=expected))
        sources.append({
            "date_ist": day,
            "original_daily_packet_sha256": packet["packet_sha256"],
            "original_H021_source_packet_sha256": packet[
                "h021_original_daily_packet_sha256"
            ],
            "NSE_cash_udiff_SHA256": packet["original_market_source_sha256"],
            "NSE_Nifty500_index_SHA256": packet["original_index_source_sha256"],
            "original_source_recorded_at_utc": packet[
                "observed_recorded_at_utc"
            ],
            "original_source_market_captured_at_utc": packet[
                "original_source_market_captured_at_utc"
            ],
            "original_source_index_captured_at_utc": packet[
                "original_source_index_captured_at_utc"
            ],
        })
    benchmark_price_change = (
        last_index_close / first_index_open - 1
    )
    output_rows = []
    arm_summaries = {}
    for arm in ARMS:
        returns = []
        missing = {}
        for symbol, isin in sorted(expected[arm]):
            key = (symbol, isin)
            holdings = [source[key] for source in source_maps]
            failures = [
                {
                    "session_date": day,
                    "source_state": bar["state"],
                }
                for day, bar in zip(dates, holdings, strict=True)
                if bar["state"] != OBSERVED_STATE
            ]
            if failures:
                change = None
                missing[f"{symbol}/{isin}"] = failures
                status = "INCOMPLETE_SOURCE_WINDOW_NO_PRICE_CHANGE"
            else:
                entry_open = holdings[0]["ohlcv"]["open_inr"]
                exit_close = holdings[-1]["ohlcv"]["close_inr"]
                change = round(exit_close / entry_open - 1, 12)
                returns.append(change)
                status = "ORIGINAL_UNADJUSTED_PRICE_CHANGE_ONLY"
            output_rows.append({
                "arm": arm,
                "symbol": symbol,
                "frozen_isin": isin,
                "holding_sessions": horizon_sessions,
                "source_complete_all_intermediate_dates": not failures,
                "state": status,
                "original_missing_source_receipts": failures,
                "unadjusted_gross_stock_price_change_fraction": change,
                "economic_total_return_calculated": False,
                "corporate_actions_resolved": False,
                "dividend_entitlement_adjusted": False,
                "actual_trade_executed": False,
            })
        summary = {
            "original_fixed_denominator": 100,
            "priced_observation_count": len(returns),
            "missing_or_changed_source_count": len(missing),
            "observed_share_percent": round(len(returns), 3),
            "missing_company_source_reasons": missing,
            **_stats(returns),
        }
        if len(returns) + len(missing) != 100:
            raise AlphaContractError("HG009 P006 missing original 100 count")
        arm_summaries[arm] = summary

    selected_stats = arm_summaries["SELECTED"]
    differences = {}
    for name in ("ONE_LANE", "ZERO_LANE"):
        control = arm_summaries[name]
        key = f"SELECTED_MINUS_{name}"
        a = selected_stats["mean_price_change_pct_if_observed"]
        b = control["mean_price_change_pct_if_observed"]
        c = selected_stats["median_price_change_pct_if_observed"]
        d = control["median_price_change_pct_if_observed"]
        differences[key] = {
            "mean_if_each_arm_observed_only_difference_pp": (
                None if a is None or b is None else round(a - b, 6)
            ),
            "median_if_each_arm_observed_only_difference_pp": (
                None if c is None or d is None else round(c - d, 6)
            ),
            "causal_or_investable_outperformance_established": False,
        }

    result = {
        "schema_version": 1,
        "evaluation_id": EVAL_ID,
        "classification": (
            "SOURCE_REPLAYED_UNADJUSTED_EQ_PRICE_CHANGES_NOT_ECONOMIC_RETURNS"
        ),
        "horizon_sessions": horizon_sessions,
        "first_entry_date": FIRST_ENTRY,
        "official_exit_date": dates[-1],
        "exact_frozen_holding_sessions": dates,
        "frozen_outcome_clock_sha256": protocol["protocol_sha256"],
        "frozen_original_market_calendar_sha256": calendar.sha256,
        "observed_at_utc": evaluated.isoformat(),
        "official_source_evidence": sources,
        "original_universe_size": 300,
        "original_denominator_per_arm": 100,
        "original_symbol_isin_rows": output_rows,
        "arm_descriptive_statistics": arm_summaries,
        "observed_priced_only_arm_differences": differences,
        "Nifty500_price_only_change_pct": round(
            100 * benchmark_price_change, 6
        ),
        "corporate_action_economic_total_returns_ready": False,
        "dividends_and_share_entitlements_adjusted": False,
        "share_unadjusted_source_price_ratio_can_be_misleading": True,
        "unobserved_issuers_count_as_zero_return": False,
        "missing_original_stock_identities_preserved_in_denominator": True,
        "sector_size_beta_neutral_or_causal_inference_available": False,
        "one_cross_section_demonstrates_replicable_alpha": False,
        "future_company_return_forecasts_fitted": False,
        "investment_recommendations_generated": False,
        "actual_fills_recorded": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["evaluation_sha256"] = digest(result)
    return result


def validate_hg009_price_only_diagnostic(
    artifact: dict[str, Any],
    *,
    horizon_sessions: int,
    protocol: dict[str, Any],
    calendar: CalendarSnapshot,
    original: dict[str, Any],
    selected: dict[str, Any],
    controls: dict[str, Any],
    market_snapshots: list[dict[str, Any]],
) -> None:
    unsigned = copy.deepcopy(artifact)
    stored = unsigned.pop("evaluation_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("HG009 P006 source report hash altered")
    reproduced = build_hg009_price_only_diagnostic(
        horizon_sessions=horizon_sessions,
        protocol=protocol,
        calendar=calendar,
        original=original,
        selected=selected,
        controls=controls,
        market_snapshots=market_snapshots,
        evaluated_at_utc=artifact["observed_at_utc"],
    )
    if reproduced != artifact:
        raise AlphaContractError("HG009 P006 original-source replay differs")
