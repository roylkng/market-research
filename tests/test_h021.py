from __future__ import annotations

import copy

import pytest

from marketlab.h021 import compare_snapshots, validate_snapshot


def _snapshot(day: str) -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "capture_date_ist": day,
        "captured_at_utc": f"{day}T12:00:00+00:00",
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "observations": [
            {
                "symbol": "AAA",
                "fiscal_period": "FY27",
                "consensus_eps": 10.0,
                "revenue_growth_forecast_pct": 12.0,
                "profit_growth_estimate_pct": 15.0,
                "analyst_count": 5,
                "target_price_inr": 100.0,
                "source_observed_market_date": day,
                "source_url": "https://example.com/aaa",
                "source_status": "TEST",
            }
        ],
    }


def test_validate_snapshot_accepts_valid_capture() -> None:
    assert validate_snapshot(_snapshot("2026-09-11")) == []


def test_validate_snapshot_rejects_future_source_date() -> None:
    snapshot = _snapshot("2026-09-11")
    snapshot["observations"][0]["source_observed_market_date"] = "2026-09-12"
    assert any("after capture date" in error for error in validate_snapshot(snapshot))


def test_validate_snapshot_rejects_duplicate_symbol_period() -> None:
    snapshot = _snapshot("2026-09-11")
    snapshot["observations"].append(copy.deepcopy(snapshot["observations"][0]))
    assert any("duplicate observation key" in error for error in validate_snapshot(snapshot))


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

    assert result.eps_revision_pct == pytest.approx(10.0)
    assert result.revenue_growth_forecast_change_pp == pytest.approx(2.5)
    assert result.profit_growth_estimate_change_pp == pytest.approx(4.0)
    assert result.target_price_revision_pct == pytest.approx(6.0)
    assert result.primary_signal_available


def test_compare_snapshots_keeps_primary_signal_unavailable_when_eps_missing() -> None:
    prior = _snapshot("2026-09-11")
    current = _snapshot("2026-10-11")
    prior["observations"][0]["consensus_eps"] = None
    current["observations"][0]["consensus_eps"] = None

    result = compare_snapshots(prior, current)[0]

    assert result.eps_revision_pct is None
    assert not result.primary_signal_available


def test_compare_snapshots_rejects_nonforward_capture_order() -> None:
    with pytest.raises(ValueError, match="current capture date must be later"):
        compare_snapshots(_snapshot("2026-09-11"), _snapshot("2026-09-11"))
