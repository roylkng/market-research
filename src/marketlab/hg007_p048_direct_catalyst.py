"""HG007 P048: immutable-source direct-catalyst research triage.

This is a review work queue for the frozen 28-case universe, NOT stock
selection, a return forecast, a position recommendation or fill capacity.
No present-day quote is projected backwards to an earlier event.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.alpha import digest
from marketlab.hg007_oct13_28_snapshot import validate_oct13_market_snapshot

AUDIT_ID = "HG007-P048-2026-10-14-DIRECT-CATALYST-EVIDENCE-TRIAGE-v1"
REVIEW_DATE = "2026-10-14"
PRICE_SESSION = "2026-10-13"
SOURCE_FILES = {
    "P043_20_SESSION_LIQUIDITY": (
        "research/hg007/hg007-p043-28-case-liquidity-risk-v1.json",
        "47c9402585b084d239f556689c68d5fc83e07a05",
    ),
    "P046_LATEST_CATALYST_STAGE": (
        "research/hg007/hg007-p046-28-case-vibhav-conversion-stage-v1.json",
        "5a2ff4ad542d39a4d75c0cd2d2ab14072d270d40",
    ),
    "P047_OFFICIAL_OCT13_MARKET": (
        "research/hg007/hg007-p047-oct13-28-official-nse-source-v1.json",
        "5e495c980985e0c42c112868cb04bfffb27807dd",
    ),
}
LANES = (
    "SOURCE_ECONOMIC_BRIDGE",
    "CATALYST_ORIGIN_AND_PAYOUT_RECONSTRUCTION",
    "LOW_LIQUIDITY_ORIGINAL_EVENT_RECONSTRUCTION",
)
ECONOMIC_SOURCE_STATES = frozenset({
    "SENSITIVITY_READY_GROSS_EV_ONLY",
    "PAYOFF_FRAMEWORK_BLOCKED_SOURCE_PARTIAL",
    "SENSITIVITY_READY",
})
BANDS = (
    ("MEDIAN_DAILY_VALUE_BELOW_0_1_CR", 0.1),
    ("MEDIAN_DAILY_VALUE_0_1_TO_BELOW_1_CR", 1.0),
    ("MEDIAN_DAILY_VALUE_1_TO_BELOW_10_CR", 10.0),
    ("MEDIAN_DAILY_VALUE_AT_LEAST_10_CR", math.inf),
)


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_frozen_sources(
    root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    packets: dict[str, dict[str, Any]] = {}
    receipts: dict[str, dict[str, str]] = {}
    for name, (path, expected_blob_sha) in SOURCE_FILES.items():
        raw = (root / path).read_bytes()
        if _blob(raw) != expected_blob_sha:
            raise ValueError(f"{name}: original frozen Git blob changed")
        packet = json.loads(raw)
        if not isinstance(packet, dict):
            raise TypeError(f"{name}: expected original JSON object")
        packets[name] = packet
        receipts[name] = {
            "path": path,
            "git_blob_sha": expected_blob_sha,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return packets, receipts


def _by_symbol(rows: object, *, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) != 28:
        raise ValueError(f"{label}: original 28-company list is incomplete")
    if any(not isinstance(row, dict) for row in rows):
        raise TypeError(f"{label}: every company record must be an object")
    symbols = [row.get("symbol") for row in rows]
    if any(not isinstance(s, str) or not s for s in symbols):
        raise ValueError(f"{label}: missing original NSE symbol")
    if len(set(symbols)) != 28:
        raise ValueError(f"{label}: duplicate original company")
    return {str(row["symbol"]): row for row in rows}


def _positive(value: object, label: str) -> float:
    if type(value) not in (float, int):
        raise ValueError(f"{label}: number missing")
    amount = float(value)
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError(f"{label}: positive finite amount required")
    return amount


def _band(median_crore: float) -> str:
    return next(label for label, upper in BANDS if median_crore < upper)


def _lane(*, source_state: str, median_crore: float) -> str:
    if median_crore < 1.0:
        return LANES[2]
    if source_state in ECONOMIC_SOURCE_STATES:
        return LANES[0]
    return LANES[1]


def build_direct_catalyst_triage(
    p043: dict[str, Any],
    p046: dict[str, Any],
    p047: dict[str, Any],
    *,
    source_receipts: dict[str, dict[str, str]],
) -> dict[str, Any]:
    validate_oct13_market_snapshot(p047)
    if (
        p043.get("overlay_id")
        != "HG007-P043-28-CASE-ORIGINAL-EQ-LIQUIDITY-OVERLAY-v1"
        or p043.get("original_hg002_selected_count_preserved") != 28
        or p043.get("original_case_economics_prices_and_selection_unmodified") is not True
        or p043.get("investment_recommendations_generated") is not False
        or p043.get("portfolio_eligibility_allowed") is not False
        or p043.get("live_capital_allowed") is not False
    ):
        raise ValueError("HG007 P043 liquidity source or frozen cohort changed")
    if (
        p046.get("review_id")
        != "HG007-P046-INOXGREEN-2026-10-09-VEPL-CONVERSION-STATE-v1"
        or p046.get("original_28_company_selection_changed") is not False
        or p046.get("company_completion_probabilities_published") != 0
        or p046.get("expected_returns_calculated") is not False
        or p046.get("portfolio_eligibility_allowed") is not False
        or p046.get("live_capital_allowed") is not False
    ):
        raise ValueError("HG007 P046 later catalyst or share-basis source changed")
    if (
        p047.get("market_session_ist") != PRICE_SESSION
        or p047.get("total_original_cases") != 28
        or p047.get("official_valid_EQ_company_count") != 27
        or p047.get("non_EQ_series_company_count") != 1
        or p047.get("original_28_company_source_selection_preserved") is not True
        or p047.get("stock_selection_or_research_priority_changed") is not False
    ):
        raise ValueError("HG007 P047 first source prices or original 28 changed")

    liquidity = _by_symbol(p043.get("company_cases"), label="P043 liquidity")
    stages = _by_symbol(
        p046.get("casework_with_current_vepl_milestone"),
        label="P046 stages",
    )
    prices = _by_symbol(
        p047.get("company_source_observations"),
        label="P047 original NSE cash observations",
    )
    if set(liquidity) != set(stages) or set(stages) != set(prices):
        raise ValueError("HG007 P048 28-company identity mismatch between sources")
    selected = sorted(
        name for name, row in prices.items()
        if row.get("frozen_transaction_stage") == "ACTIVE_DIRECT_CATALYST"
    )
    if len(selected) != 7:
        raise ValueError("HG007 P048 original active-direct-catalyst count changed")
    cases: list[dict[str, Any]] = []
    for symbol in selected:
        liquidity_row = liquidity[symbol]
        stage_row = stages[symbol]
        market = prices[symbol]
        historical = liquidity_row.get("historical_eq_source_readiness")
        if not isinstance(historical, dict):
            raise ValueError(f"{symbol}: original twenty-session context absent")
        if (
            market.get("source_series_state")
            != "OFFICIAL_EQ_PRICE_VOLUME_OBSERVED_NOT_FILL"
            or market.get("historical_original_source_EQ_sessions") != 20
            or historical.get("state") != "COMPLETE_20_EQ_SESSIONS_HISTORICAL_ONLY"
            or historical.get("source_eq_session_count") != 20
            or historical.get("source_eq_isin") != market.get("frozen_isin")
            or stage_row.get("hg003_thread_state") != "ACTIVE_DIRECT_CATALYST"
            or liquidity_row.get("hg003_thread_state") != "ACTIVE_DIRECT_CATALYST"
        ):
            raise ValueError(f"{symbol}: direct-catalyst EQ/ISIN/stage source drift")
        if (
            liquidity_row.get("stock_expected_returns_calculated") is not False
            or liquidity_row.get("stock_valuation_ready") is not False
            or liquidity_row.get("case_specific_probability_published") is not False
            or liquidity_row.get("portfolio_eligibility_allowed") is not False
            or stage_row.get("portfolio_eligibility_allowed") is not False
            or market.get("portfolio_position_created") is not False
            or market.get("equity_expected_return_computed") is not False
            or market.get("actual_trade_execution_confirmed") is not False
        ):
            raise ValueError(f"{symbol}: no unsupported valuation or alpha promotion")
        median = _positive(
            historical.get("median_daily_cash_market_value_traded_inr_crore"),
            f"{symbol} prior-20 NSE median traded value",
        )
        market_median = _positive(
            market.get("original_twenty_day_EQ_median_value_inr_crore_if_complete"),
            f"{symbol} market-linked historical median",
        )
        if not math.isclose(median, market_median, rel_tol=0, abs_tol=1e-9):
            raise ValueError(f"{symbol}: NSE 20-session liquidity mismatch")
        band = _band(median)
        if historical.get("historical_median_value_band") != band:
            raise ValueError(f"{symbol}: frozen liquidity-band contract differs")
        day_value = _positive(
            market.get("reported_EQ_traded_value_inr_crore"),
            f"{symbol} 13 Oct turnover",
        )
        close = _positive(
            market.get("reported_EQ_close_inr"),
            f"{symbol} 13 Oct official EQ close",
        )
        docs = liquidity_row.get("next_source_documents_to_acquire_not_asserted_as_facts")
        if (
            not isinstance(docs, list)
            or not docs
            or any(not isinstance(x, str) or not x for x in docs)
        ):
            raise ValueError(f"{symbol}: primary original document blockers absent")
        sensitivity = str(liquidity_row["economic_sensitivity_state"])
        if sensitivity != market.get("economic_sensitivity_state"):
            raise ValueError(f"{symbol}: historical economic stage differs")
        lane = _lane(source_state=sensitivity, median_crore=median)
        cases.append({
            "symbol": symbol,
            "isin": market["frozen_isin"],
            "latest_stage": "ACTIVE_DIRECT_CATALYST",
            "research_lane": lane,
            "official_cash_session": PRICE_SESSION,
            "official_equity_close_inr_not_current": close,
            "official_cash_turnover_inr_crore_one_day": day_value,
            "original_prior20_EQ_median_turnover_inr_crore": median,
            "historical_turnover_band": band,
            "turnover_13_oct_to_prior20_median_ratio_not_alpha": (
                day_value / median
            ),
            "economics_evidence_state": sensitivity,
            "source_acquisition_route": liquidity_row["evidence_acquisition_route"],
            "missing_original_document_gates": docs,
            "missing_original_document_gate_count": len(docs),
            "needs_actual_bid_ask_depth_and_execution_evidence": True,
            "current_fully_diluted_shares_verified": False,
            "expected_return": None,
            "company_specific_completion_probability": None,
            "risk_adjusted_fair_value_inr": None,
            "capital_deployment_eligible": False,
            "historical_turnover_is_executable_capacity": False,
        })

    grouped = {}
    for lane in LANES:
        lane_rows = [x for x in cases if x["research_lane"] == lane]
        # This sorts primary-document review work, never expected stock returns.
        lane_rows.sort(
            key=lambda row: (
                -row["original_prior20_EQ_median_turnover_inr_crore"],
                row["symbol"],
            )
        )
        grouped[lane] = [row["symbol"] for row in lane_rows]

    result: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": (
            "DOCUMENT_ACQUISITION_SEQUENCE_NOT_STOCK_RETURN_RANKING"
        ),
        "review_as_of_ist": REVIEW_DATE,
        "latest_official_price_session_ist": PRICE_SESSION,
        "original_frozen_cohort_count": 28,
        "active_direct_catalyst_count": len(cases),
        "eligible_for_investment_count": 0,
        "individual_probability_estimate_count": 0,
        "company_fair_value_estimate_count": 0,
        "source_receipts": source_receipts,
        "review_lanes": grouped,
        "review_lane_counts": {
            lane: len(grouped[lane]) for lane in LANES
        },
        "very_thin_prior20_turnover_below_0_1_crore_symbols": [
            c["symbol"] for c in cases
            if c["original_prior20_EQ_median_turnover_inr_crore"] < 0.1
        ],
        "turnover_below_one_crore_symbols": [
            c["symbol"] for c in cases
            if c["original_prior20_EQ_median_turnover_inr_crore"] < 1.0
        ],
        "cases": cases,
        "original_hg002_company_selection_changed": False,
        "frozen_stage_reclassified": False,
        "latest_oct13_price_is_current_oct14_quote": False,
        "source_document_gaps_falsely_treated_as_fact": False,
        "catalyst_presence_means_positive_future_return": False,
        "historical_liquidity_is_tradable_order_capacity": False,
        "future_price_or_market_relative_return_calculated": False,
        "investment_recommendations_generated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = digest(result)
    return result


def validate_direct_catalyst_triage(packet: dict[str, Any]) -> None:
    if packet.get("audit_id") != AUDIT_ID:
        raise ValueError("P048 triage audit identity mismatch")
    unsigned = dict(packet)
    sig = unsigned.pop("packet_sha256", None)
    if sig != digest(unsigned):
        raise ValueError("P048 triage packet SHA changed")
    if (
        packet.get("original_frozen_cohort_count") != 28
        or packet.get("active_direct_catalyst_count") != 7
        or len(packet.get("cases") or []) != 7
        or sum(packet.get("review_lane_counts", {}).values()) != 7
    ):
        raise ValueError("P048 active catalyst cohort changed")
    if set(packet["review_lanes"]) != set(LANES):
        raise ValueError("P048 review lane contract changed")
    for key in (
        "original_hg002_company_selection_changed",
        "frozen_stage_reclassified",
        "latest_oct13_price_is_current_oct14_quote",
        "source_document_gaps_falsely_treated_as_fact",
        "catalyst_presence_means_positive_future_return",
        "historical_liquidity_is_tradable_order_capacity",
        "future_price_or_market_relative_return_calculated",
        "investment_recommendations_generated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(key) is not False:
            raise ValueError(f"P048 cannot authorize {key}")
    names = [row["symbol"] for row in packet["cases"]]
    if len(names) != len(set(names)) or names != sorted(names):
        raise ValueError("P048 duplicate or reordered active company")
    for row in packet["cases"]:
        if (
            row.get("expected_return") is not None
            or row.get("company_specific_completion_probability") is not None
            or row.get("risk_adjusted_fair_value_inr") is not None
            or row.get("capital_deployment_eligible") is not False
            or row.get("historical_turnover_is_executable_capacity") is not False
        ):
            raise ValueError("P048 cannot transform source research into a trade")


def materialize_direct_catalyst_triage(root: Path) -> dict[str, Any]:
    data, receipts = load_frozen_sources(root)
    result = build_direct_catalyst_triage(
        data["P043_20_SESSION_LIQUIDITY"],
        data["P046_LATEST_CATALYST_STAGE"],
        data["P047_OFFICIAL_OCT13_MARKET"],
        source_receipts=receipts,
    )
    validate_direct_catalyst_triage(result)
    return result
