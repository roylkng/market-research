"""L001: point-in-time, long-horizon owner-value research contracts.

These functions are arithmetic and input admission checks, not forecasts,
audited truth, completed backtests, investable valuations or live advice.
The 1/2/3-year sleeve is separate from frozen HG009/H-series/AE001 decisions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from math import isfinite

HORIZONS = (252, 504, 756)

# Reject accounting proxies that are not distributable owner cash.
BASES = {
    "price": "NSE_UNADJUSTED_PRICE",
    "diluted_shares": "FULLY_DILUTED_PARENT_EQUITY",
    "owner_cash": "PARENT_DISTRIBUTABLE_CASH_AFTER_REINVESTMENT",
    "excess_cash": "PARENT_ACCESSIBLE_SURPLUS_NOT_IN_OPERATIONS",
    "net_claims": "UNDUPLICATED_PARENT_CLAIMS",
    "nopat_prior": "RECONCILED_CONSOLIDATED_NOPAT",
    "nopat_current": "RECONCILED_CONSOLIDATED_NOPAT",
    "capital_prior": "RECONCILED_INVESTED_CAPITAL",
    "capital_current": "RECONCILED_INVESTED_CAPITAL",
}
REQUIRED = frozenset(BASES)


@dataclass(frozen=True)
class ValueFact:
    role: str
    symbol: str
    isin: str
    value_cr: float
    accounting_basis: str
    original_bytes: bytes
    sha256_digest: str
    published_at_utc: str
    first_seen_at_utc: str
    reviewer_status: str


@dataclass(frozen=True)
class ReturnObservation:
    """Synthetic/arithmetic contract; source settlement is external.

    Shares_per_initial_share handles splits/bonus/mergers; dividends and any
    settlement cash are measured per one original share, in INR.
    """
    symbol: str
    isin: str
    horizon_sessions: int
    elapsed_verified_sessions: int
    entry_price_inr: float | None
    exit_price_inr: float | None
    shares_per_initial_share: float | None
    distributions_per_initial_share_inr: float | None
    settlement_per_initial_share_inr: float | None
    benchmark_tr_entry_open: float | None
    benchmark_tr_exit_close: float | None
    corporate_action_status: str
    exit_status: str
    entry_tradable: bool
    roundtrip_cost_fraction: float
    calendar_receipt_sha256: str | None


def _time(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo is not None and dt.utcoffset() == timedelta(0) else None


def _number(value: object, *, positive: bool = False) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and (not positive or value > 0)
    )


def _abstain(symbol: str, *reasons: str) -> dict:
    return {
        "status": "ABSTAIN",
        "symbol": symbol,
        "reasons": sorted(set(reasons)),
        "investment_authorized": False,
    }


def _discounted_fcfe(
    baseline: float, growth: float, discount: float, multiple: float, years: int,
) -> float:
    total = sum(
        baseline * (1 + growth) ** year / (1 + discount) ** year
        for year in range(1, years + 1)
    )
    return total + (
        baseline * (1 + growth) ** years * multiple / (1 + discount) ** years
    )


def reverse_value_creation_hurdle(
    *, symbol: str, isin: str, decision_cutoff_utc: str,
    facts: Mapping[str, ValueFact], annual_discount: float,
    terminal_owner_cash_multiple: float, years: int = 3,
) -> dict:
    """Solve price-implied *cash-growth hurdle*, not future cash growth.

    Must not treat an issuer-defined net-cash KPI as parent-accessible surplus,
    or CFO-minus-PPE as distributable FCFE. Published values remain reviewer
    assertions until original accounting reconciliation is independently proven.
    """
    cutoff = _time(decision_cutoff_utc)
    if cutoff is None or not symbol or not isin:
        return _abstain(symbol, "valid_identity_and_exact_utc_cutoff_required")
    reasons: list[str] = []
    if set(facts) != REQUIRED:
        reasons.append("exact_economic_roles_required")
    for role in sorted(REQUIRED):
        item = facts.get(role)
        if item is None:
            reasons.append(f"{role}_missing")
            continue
        if item.role != role or item.symbol != symbol or item.isin != isin:
            reasons.append(f"{role}_identity_mismatch")
        if item.accounting_basis != BASES[role]:
            reasons.append(f"{role}_accounting_basis_unreconciled")
        if not _number(item.value_cr):
            reasons.append(f"{role}_invalid_numeric_value")
        if (
            not isinstance(item.original_bytes, bytes)
            or not item.original_bytes
            or sha256(item.original_bytes).hexdigest() != item.sha256_digest
        ):
            reasons.append(f"{role}_bytes_not_authenticated")
        published, seen = _time(item.published_at_utc), _time(item.first_seen_at_utc)
        if published is None or seen is None or not published <= seen <= cutoff:
            reasons.append(f"{role}_publication_or_capture_after_cutoff")
        if item.reviewer_status != "INDEPENDENTLY_REVIEWED":
            reasons.append(f"{role}_independent_review_missing")

    if (
        not _number(annual_discount)
        or not _number(terminal_owner_cash_multiple, positive=True)
        or annual_discount < 0
        or not isinstance(years, int)
        or isinstance(years, bool)
        or years not in (1, 2, 3)
    ):
        reasons.append("invalid_horizon_discount_or_multiple")
    if reasons:
        return _abstain(symbol, *reasons)

    values = {role: facts[role].value_cr for role in REQUIRED}
    if any(
        values[role] <= 0 for role in ("price", "diluted_shares", "owner_cash")
    ):
        return _abstain(symbol, "positive_price_shares_and_owner_cash_required")
    if values["excess_cash"] < 0 or values["net_claims"] < 0:
        return _abstain(symbol, "surplus_or_claims_negative")
    cap = values["price"] * values["diluted_shares"]
    operating_value = cap - values["excess_cash"] + values["net_claims"]
    if operating_value <= 0:
        return _abstain(symbol, "positive_operating_equity_value_required")
    delta_capital = values["capital_current"] - values["capital_prior"]
    delta_nopat = values["nopat_current"] - values["nopat_prior"]
    if delta_capital <= 0:
        return _abstain(symbol, "positive_net_incremental_capital_required")
    incremental_roic = delta_nopat / delta_capital

    lower, upper = -0.95, 2.0
    f_lower = _discounted_fcfe(
        values["owner_cash"], lower, annual_discount, terminal_owner_cash_multiple, years,
    )
    f_upper = _discounted_fcfe(
        values["owner_cash"], upper, annual_discount, terminal_owner_cash_multiple, years,
    )
    if not f_lower <= operating_value <= f_upper:
        return _abstain(symbol, "reverse_growth_outside_predefined_bounds")
    for _ in range(96):
        mid = (lower + upper) / 2
        value = _discounted_fcfe(
            values["owner_cash"], mid, annual_discount, terminal_owner_cash_multiple, years,
        )
        if value < operating_value:
            lower = mid
        else:
            upper = mid
    growth = (lower + upper) / 2
    return {
        "status": "REVERSE_HURDLE_MATH_ONLY",
        "symbol": symbol,
        "isin": isin,
        "years": years,
        "historical_fully_diluted_cap_cr": round(cap, 6),
        "net_operating_equity_target_cr": round(operating_value, 6),
        "annual_owner_cash_growth_hurdle": round(growth, 8),
        "incremental_nopat_on_net_invested_capital": round(incremental_roic, 8),
        "source_bytes_integrity_checked": True,
        "accounting_truth_certified_by_code": False,
        "source_reviewer_status_is_an_assertion": True,
        "scenario_return_probability": None,
        "investment_authorized": False,
    }


def long_horizon_return_label(row: ReturnObservation) -> dict:
    """Arithmetic-only label from already observed, fully reconciled input.

    A long-horizon label cannot be produced from incomplete sessions,
    ambiguous corporate actions, untradeable entries or missing exits.
    """
    base = {"symbol": row.symbol, "isin": row.isin,
            "horizon_sessions": row.horizon_sessions, "investment_authorized": False}
    if row.horizon_sessions not in HORIZONS:
        return {**base, "status": "ABSTAIN", "reason": "invalid_long_horizon"}
    if row.elapsed_verified_sessions < row.horizon_sessions:
        return {**base, "status": "NOT_MATURE", "reason": "forward_sessions_incomplete"}
    if row.elapsed_verified_sessions != row.horizon_sessions:
        return {**base, "status": "ABSTAIN", "reason": "exit_session_misaligned"}
    if not row.calendar_receipt_sha256 or len(row.calendar_receipt_sha256) != 64:
        return {**base, "status": "ABSTAIN", "reason": "calendar_source_unverified"}
    if row.corporate_action_status != "FULLY_RECONCILED":
        return {**base, "status": "ABSTAIN", "reason": "actions_or_rights_unresolved"}
    if not row.entry_tradable:
        return {**base, "status": "NOT_EXECUTABLE", "reason": "entry_untradeable"}
    if row.exit_status not in {"ACTIVE", "SETTLED_DELISTING"}:
        return {**base, "status": "ABSTAIN", "reason": "exit_or_delisting_unresolved"}
    numeric = (
        row.entry_price_inr, row.shares_per_initial_share,
        row.distributions_per_initial_share_inr, row.benchmark_tr_entry_open,
        row.benchmark_tr_exit_close, row.roundtrip_cost_fraction,
    )
    if any(not _number(x) for x in numeric):
        return {**base, "status": "ABSTAIN", "reason": "missing_total_return_inputs"}
    assert row.entry_price_inr is not None
    assert row.shares_per_initial_share is not None
    assert row.distributions_per_initial_share_inr is not None
    assert row.benchmark_tr_entry_open is not None
    assert row.benchmark_tr_exit_close is not None
    if (
        row.entry_price_inr <= 0 or row.shares_per_initial_share <= 0
        or row.benchmark_tr_entry_open <= 0 or row.benchmark_tr_exit_close <= 0
        or row.distributions_per_initial_share_inr < 0
        or not 0 <= row.roundtrip_cost_fraction < 1
    ):
        return {**base, "status": "ABSTAIN", "reason": "invalid_total_return_inputs"}
    if row.exit_status == "ACTIVE":
        if not _number(row.exit_price_inr, positive=True) or row.settlement_per_initial_share_inr is not None:
            return {**base, "status": "ABSTAIN", "reason": "active_exit_price_missing_or_duplicate"}
        value = row.shares_per_initial_share * row.exit_price_inr
    else:
        if row.exit_price_inr is not None or not _number(row.settlement_per_initial_share_inr):
            return {**base, "status": "ABSTAIN", "reason": "delisting_settlement_missing_or_duplicate"}
        value = row.settlement_per_initial_share_inr
    gross_stock = (value + row.distributions_per_initial_share_inr) / row.entry_price_inr - 1
    # Conservative simple round-trip cost stress, not a broker-fill simulation.
    net_stock = gross_stock - row.roundtrip_cost_fraction
    benchmark = row.benchmark_tr_exit_close / row.benchmark_tr_entry_open - 1
    return {
        **base,
        "status": "TOTAL_RETURN_MATH_ONLY",
        "gross_stock_total_return": round(gross_stock, 8),
        "net_stock_return_cost_stress": round(net_stock, 8),
        "benchmark_total_return": round(benchmark, 8),
        "net_excess_return_cost_stress": round(net_stock - benchmark, 8),
        "source_receipts_content_verified_by_code": False,
        "label_may_join_frozen_prospective_outcomes": False,
    }
