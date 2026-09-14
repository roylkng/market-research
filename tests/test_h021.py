from __future__ import annotations

import copy

import pytest

from marketlab.h021 import (
    compare_snapshots,
    select_primary_top_decile,
    select_prior_snapshot,
    validate_snapshot,
)


def _snapshot(day: str) -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "capture_date_ist": day,
        "captured_at_utc": f"{day}T12:00:00+00:00",
        "source_version": "source-v1",
        "universe_path": "research/prospective/universes/u001.json",
        "universe_git_blob_sha": "abc123",
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "observations": [
            {
                "symbol": "AAA",
                "fiscal_period": "FY27",
                "period_ending": "2027-03-31",
                "consensus_eps": 10.0,
                "eps_currency": "INR",
                "revenue_growth_forecast_pct": 12.0,
                "profit_growth_estimate_pct": 15.0,
                "analyst_count": 5,
                "target_price_inr": 100.0,
                "source_observed_market_date": day,
                "source_url": "https://stockanalysis.com/aaa",
                "source_status": "TEST",
            }
        ],
    }


def test_validate_snapshot_accepts_valid_capture() -> None:
    assert validate_snapshot(_snapshot("2026-09-11")) == []


def test_validate_snapshot_rejects_invalid_period_ending_when_present() -> None:
    snapshot = _snapshot("2026-09-11")
    snapshot["observations"][0]["period_ending"] = "31-03-2027"
    assert any("period_ending" in error for error in validate_snapshot(snapshot))


def test_validate_snapshot_rejects_invalid_eps_currency_when_present() -> None:
    snapshot = _snapshot("2026-09-11")
    snapshot["observations"][0]["eps_currency"] = "inr"
    assert any("eps_currency" in error for error in validate_snapshot(snapshot))


def test_validate_snapshot_allows_missing_optional_semantics_for_legacy_rows() -> None:
    snapshot = _snapshot("2026-09-11")
    del snapshot["observations"][0]["period_ending"]
    del snapshot["observations"][0]["eps_currency"]
    assert validate_snapshot(snapshot) == []


def test_validate_snapshot_rejects_future_source_date() -> None:
    snapshot = _snapshot("2026-09-11")
    snapshot["observations"][0]["source_observed_market_date"] = "2026-09-12"
    assert any("after capture date" in error for error in validate_snapshot(snapshot))


def test_validate_snapshot_rejects_duplicate_symbol_period() -> None:
    snapshot = _snapshot("2026-09-11")
    snapshot["observations"].append(copy.deepcopy(snapshot["observations"][0]))
    assert any("duplicate observation key" in error for error in validate_snapshot(snapshot))


def test_validate_snapshot_rejects_duplicate_symbol_across_periods() -> None:
    snapshot = _snapshot("2026-09-11")
    duplicate = copy.deepcopy(snapshot["observations"][0])
    duplicate["fiscal_period"] = "FY28"
    snapshot["observations"].append(duplicate)
    assert any(
        "duplicate observation symbol" in error for error in validate_snapshot(snapshot)
    )


def test_validate_snapshot_requires_timestamp() -> None:
    snapshot = _snapshot("2026-09-11")
    del snapshot["captured_at_utc"]
    assert any("captured_at_utc" in error for error in validate_snapshot(snapshot))


def test_compare_snapshots_computes_revision_without_price_inputs() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["observations"][0]["consensus_eps"] = 11.0
    current["observations"][0]["revenue_growth_forecast_pct"] = 14.5
    current["observations"][0]["profit_growth_estimate_pct"] = 19.0
    current["observations"][0]["target_price_inr"] = 106.0

    result = compare_snapshots(prior, current)[0]

    assert result.capture_interval_days == 30
    assert result.period_ending_prior == "2027-03-31"
    assert result.period_ending_current == "2027-03-31"
    assert result.eps_currency_prior == "INR"
    assert result.eps_currency_current == "INR"
    assert result.eps_revision_pct == pytest.approx(10.0)
    assert result.revenue_growth_forecast_change_pp == pytest.approx(2.5)
    assert result.profit_growth_estimate_change_pp == pytest.approx(4.0)
    assert result.target_price_revision_pct == pytest.approx(6.0)
    assert result.period_compatible
    assert result.eps_currency_compatible
    assert result.source_compatible
    assert result.primary_coverage
    assert result.primary_signal_available
    assert result.primary_signal_reason == "ELIGIBLE"


def test_compare_snapshots_keeps_primary_signal_unavailable_when_eps_missing() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    prior["observations"][0]["consensus_eps"] = None
    current["observations"][0]["consensus_eps"] = None
    prior["observations"][0]["period_ending"] = None
    current["observations"][0]["period_ending"] = None
    prior["observations"][0]["eps_currency"] = None
    current["observations"][0]["eps_currency"] = None

    result = compare_snapshots(prior, current)[0]

    assert result.eps_revision_pct is None
    assert not result.primary_signal_available
    assert result.primary_signal_reason == "EPS_REVISION_UNAVAILABLE"


def test_compare_snapshots_rejects_nonforward_capture_order() -> None:
    with pytest.raises(ValueError, match="current capture date must be later"):
        compare_snapshots(_snapshot("2026-09-11"), _snapshot("2026-09-11"))


@pytest.mark.parametrize("current_day", ["2026-10-08", "2026-10-17"])
def test_compare_snapshots_rejects_out_of_window_interval(current_day: str) -> None:
    with pytest.raises(ValueError, match="between 28 and 35 days"):
        compare_snapshots(_snapshot("2026-09-11"), _snapshot(current_day))


def test_compare_snapshots_requires_matching_source_version() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["source_version"] = "source-v2"

    with pytest.raises(ValueError, match="matching source_version"):
        compare_snapshots(prior, current)


def test_compare_snapshots_requires_matching_frozen_symbol_set() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["observations"][0]["symbol"] = "BBB"

    with pytest.raises(ValueError, match="identical frozen symbol sets"):
        compare_snapshots(prior, current)


def test_compare_snapshots_marks_low_coverage_as_ineligible() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["observations"][0]["consensus_eps"] = 11.0
    current["observations"][0]["analyst_count"] = 4

    result = compare_snapshots(prior, current)[0]

    assert result.eps_revision_pct == pytest.approx(10.0)
    assert not result.primary_coverage
    assert not result.primary_signal_available
    assert result.primary_signal_reason == "ANALYST_COVERAGE_LT_5"


def test_compare_snapshots_retains_fiscal_period_mismatch_as_no_signal() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["observations"][0]["fiscal_period"] = "FY28"

    result = compare_snapshots(prior, current)[0]

    assert result.fiscal_period == "FY28"
    assert result.eps_revision_pct is None
    assert not result.primary_signal_available
    assert result.primary_signal_reason == "FISCAL_PERIOD_MISMATCH"


def test_compare_snapshots_rejects_period_end_mismatch() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["observations"][0]["consensus_eps"] = 11.0
    current["observations"][0]["period_ending"] = "2027-06-30"

    result = compare_snapshots(prior, current)[0]

    assert not result.period_compatible
    assert result.eps_revision_pct is None
    assert result.revenue_growth_forecast_change_pp is None
    assert not result.primary_signal_available
    assert result.primary_signal_reason == "PERIOD_END_MISMATCH"


def test_compare_snapshots_rejects_missing_period_end_for_numeric_eps() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["observations"][0]["consensus_eps"] = 11.0
    current["observations"][0]["period_ending"] = None

    result = compare_snapshots(prior, current)[0]

    assert result.eps_revision_pct is None
    assert result.primary_signal_reason == "PERIOD_END_UNAVAILABLE"


def test_compare_snapshots_rejects_eps_currency_mismatch() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["observations"][0]["consensus_eps"] = 11.0
    current["observations"][0]["eps_currency"] = "USD"

    result = compare_snapshots(prior, current)[0]

    assert not result.eps_currency_compatible
    assert result.eps_revision_pct is None
    assert not result.primary_signal_available
    assert result.primary_signal_reason == "EPS_CURRENCY_MISMATCH"


def test_compare_snapshots_rejects_missing_eps_currency_for_numeric_eps() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["observations"][0]["consensus_eps"] = 11.0
    current["observations"][0]["eps_currency"] = None

    result = compare_snapshots(prior, current)[0]

    assert result.eps_revision_pct is None
    assert result.primary_signal_reason == "EPS_CURRENCY_UNAVAILABLE"


def test_compare_snapshots_rejects_cross_provider_eps_change() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    current["observations"][0]["consensus_eps"] = 11.0
    current["observations"][0]["source_url"] = "https://trendlyne.com/aaa"

    result = compare_snapshots(prior, current)[0]

    assert result.eps_revision_pct is None
    assert not result.source_compatible
    assert not result.primary_signal_available
    assert result.primary_signal_reason == "EPS_SOURCE_CHANGED"


def test_select_primary_top_decile_is_tie_inclusive() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    prior["observations"] = []
    current["observations"] = []
    for index in range(20):
        symbol = f"S{index:02d}"
        before = copy.deepcopy(_snapshot("2026-09-11")["observations"][0])
        after = copy.deepcopy(_snapshot("2026-10-11")["observations"][0])
        before["symbol"] = symbol
        after["symbol"] = symbol
        before["consensus_eps"] = 10.0
        after["consensus_eps"] = 11.0 if index < 3 else 10.0
        prior["observations"].append(before)
        current["observations"].append(after)

    revisions = compare_snapshots(prior, current)
    selected = select_primary_top_decile(revisions)

    assert [row.symbol for row in selected] == ["S00", "S01", "S02"]


def test_select_prior_snapshot_uses_nearest_to_30_days_and_earlier_tie() -> None:
    current = _snapshot("2026-10-12")
    earlier = _snapshot("2026-09-11")
    later = _snapshot("2026-09-13")
    too_recent = _snapshot("2026-09-20")

    selected = select_prior_snapshot(current, [later, too_recent, earlier])

    assert selected["capture_date_ist"] == "2026-09-11"
