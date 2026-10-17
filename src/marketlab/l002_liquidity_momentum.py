"""L002: frozen-H004-independent liquidity-conditioned momentum diagnostic.

This computes ONLY as-of descriptive features, never an alpha signal,
selection threshold, fabricated fill, backtest return or investment rank.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import isfinite
from statistics import median

FORM_WINDOW = 252
RECENT_SKIP = 21
LIQ_WINDOW = 20
PRIMARY_ADV_INR = 20_000_000
DISCOVERY_ADV_INR = 2_500_000


@dataclass(frozen=True)
class AsOfBar:
    symbol: str
    isin: str
    session: str
    adjusted_close_inr: float
    traded_value_inr: float
    source_first_seen_utc: str
    source_digest: str
    adjustment_status: str


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _utc(value: str) -> datetime | None:
    try:
        value_dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return value_dt if value_dt.tzinfo is not None and value_dt.utcoffset() == timedelta(0) else None


def calculate_asof_momentum(
    bars: list[AsOfBar], *, symbol: str, isin: str,
    decision_cutoff_utc: str, universe_known_at_utc: str,
) -> dict:
    """252-session formation, skip most recent 21, segment by ADV20.

    Requires a pre-cutoff, ISIN-stable price panel and adjusted price basis.
    The supplied source SHA and adjustment status are ASSERTIONS, not a full
    original-NSE-binary verifier. Consequently output is diagnostics only.
    """
    base = {"symbol": symbol, "isin": isin, "investment_authorized": False}
    cutoff = _utc(decision_cutoff_utc)
    cohort = _utc(universe_known_at_utc)
    if cutoff is None or cohort is None or cohort > cutoff:
        return {**base, "status": "ABSTAIN", "reason": "universe_or_decision_clock_invalid"}
    if len(bars) < FORM_WINDOW:
        return {**base, "status": "ABSTAIN", "reason": "insufficient_complete_history"}
    ordered = sorted(bars, key=lambda row: row.session)
    sessions = [row.session for row in ordered]
    if len(set(sessions)) != len(sessions):
        return {**base, "status": "ABSTAIN", "reason": "duplicate_sessions"}
    if any(_date(day) is None for day in sessions):
        return {**base, "status": "ABSTAIN", "reason": "invalid_session_calendar"}
    for row in ordered:
        time = _utc(row.source_first_seen_utc)
        if (
            row.symbol != symbol or row.isin != isin
            or time is None or time > cutoff
            or _date(row.session) > cutoff.date()
        ):
            return {**base, "status": "ABSTAIN", "reason": "identity_or_future_data"}
        if (
            not isfinite(row.adjusted_close_inr) or row.adjusted_close_inr <= 0
            or not isfinite(row.traded_value_inr) or row.traded_value_inr < 0
        ):
            return {**base, "status": "ABSTAIN", "reason": "invalid_market_data"}
        if (
            len(row.source_digest) != 64
            or any(char not in "0123456789abcdef" for char in row.source_digest)
            or row.adjustment_status != "PIT_CORPORATE_ACTIONS_RECONCILED"
        ):
            return {**base, "status": "ABSTAIN", "reason": "price_source_or_actions_unreconciled"}

    panel = ordered[-FORM_WINDOW:]
    # t-252 to t-21, avoiding the recent one-month reversal interval.
    start = panel[0]
    end = panel[-(RECENT_SKIP + 1)]
    momentum = end.adjusted_close_inr / start.adjusted_close_inr - 1
    adv = median(row.traded_value_inr for row in ordered[-LIQ_WINDOW:])
    tier = (
        "PRIMARY_LIQUID"
        if adv >= PRIMARY_ADV_INR
        else "DISCOVERY"
        if adv >= DISCOVERY_ADV_INR
        else "BELOW_DISCOVERY_THRESHOLD"
    )
    return {
        **base,
        "status": "NON_CANONICAL_PIT_MOMENTUM_DIAGNOSTIC",
        "formation_window_sessions": FORM_WINDOW,
        "recent_skip_sessions": RECENT_SKIP,
        "momentum_12minus1_fraction": round(momentum, 10),
        "median_traded_value_20_inr": round(adv, 2),
        "liquidity_tier": tier,
        "usable_as_h004_derived_signal": False,
        "standalone_alpha_statistically_validated": False,
        "source_original_bytes_verified_by_code": False,
        "source_hashes_are_upstream_assertions": True,
    }
