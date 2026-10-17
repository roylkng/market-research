"""No future data or H004 retuning in the L002 feature diagnostic."""

from dataclasses import replace
from datetime import date, timedelta

from marketlab.l002_liquidity_momentum import (
    AsOfBar,
    calculate_asof_momentum,
)


def bars(*, adv=25_000_000, growth=0.001):
    start = date(2025, 1, 1)
    return [
        AsOfBar(
            symbol="TEST", isin="INE000000001",
            session=(start + timedelta(days=i)).isoformat(),
            adjusted_close_inr=100.0 * (1 + growth) ** i,
            traded_value_inr=adv,
            source_first_seen_utc="2026-01-01T00:00:00Z",
            source_digest="a" * 64,
            adjustment_status="PIT_CORPORATE_ACTIONS_RECONCILED",
        )
        for i in range(252)
    ]


def run(rows):
    return calculate_asof_momentum(
        rows, symbol="TEST", isin="INE000000001",
        decision_cutoff_utc="2026-10-17T10:00:00Z",
        universe_known_at_utc="2026-01-01T00:00:00Z",
    )


def test_positive_momentum_and_liquidity():
    result = run(bars())
    assert result["status"] == "NON_CANONICAL_PIT_MOMENTUM_DIAGNOSTIC"
    assert result["momentum_12minus1_fraction"] > 0
    assert result["liquidity_tier"] == "PRIMARY_LIQUID"
    assert result["standalone_alpha_statistically_validated"] is False
    assert result["usable_as_h004_derived_signal"] is False


def test_median_liquidity_tiers():
    assert run(bars(adv=3_000_000))["liquidity_tier"] == "DISCOVERY"
    assert run(bars(adv=500_000))["liquidity_tier"] == "BELOW_DISCOVERY_THRESHOLD"


def test_recent_runup_does_not_enter_12minus1():
    rows = bars()
    last = rows[-1]
    changed = rows[:-1] + [replace(last, adjusted_close_inr=last.adjusted_close_inr * 3)]
    assert run(changed)["momentum_12minus1_fraction"] == run(rows)["momentum_12minus1_fraction"]


def test_future_information_rejected():
    rows = bars()
    rows[-1] = replace(rows[-1], source_first_seen_utc="2026-10-18T11:00:00Z")
    assert run(rows)["status"] == "ABSTAIN"


def test_wrong_identity_rejected():
    rows = bars()
    rows[20] = replace(rows[20], isin="INEDIFFERENT")
    assert run(rows)["status"] == "ABSTAIN"


def test_unreconciled_split_rejected():
    rows = bars()
    rows[20] = replace(rows[20], adjustment_status="UNKNOWN")
    assert run(rows)["status"] == "ABSTAIN"


def test_short_history_abstains():
    assert run(bars()[:251])["reason"] == "insufficient_complete_history"


def test_duplicate_session_rejected():
    rows = bars()
    rows[1] = replace(rows[1], session=rows[0].session)
    assert run(rows)["status"] == "ABSTAIN"


def test_missing_volume_is_invalid():
    rows = bars()
    rows[-1] = replace(rows[-1], traded_value_inr=float("nan"))
    assert run(rows)["status"] == "ABSTAIN"


def test_after_cutoff_universe_cannot_score():
    result = calculate_asof_momentum(
        bars(), symbol="TEST", isin="INE000000001",
        decision_cutoff_utc="2026-10-17T10:00:00Z",
        universe_known_at_utc="2026-10-18T00:00:00Z",
    )
    assert result["status"] == "ABSTAIN"


def test_negative_momentum_preserved():
    assert run(bars(growth=-0.001))["momentum_12minus1_fraction"] < 0
