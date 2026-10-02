from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_regime import REGIME_VARIABLES, build_rg001_panel


def _market_panel(count=65):
    start = date(2026, 1, 1)
    closes = {"A": 100.0, "B": 150.0}
    benchmark = 20_000.0
    sessions = []
    for index in range(count):
        day = (start + timedelta(days=index)).isoformat()
        benchmark *= 1.0 + 0.0005 * ((index % 5) - 1)
        equities = []
        for offset, symbol in enumerate(("A", "B")):
            prior = closes[symbol]
            change = 0.001 if symbol == "A" else (-0.0005 if index % 2 else 0.0015)
            closes[symbol] *= 1.0 + change
            equities.append(
                {
                    "session_date": day,
                    "symbol": symbol,
                    "isin": f"INE{offset + 1:09d}",
                    "open_price": prior,
                    "high_price": max(prior, closes[symbol]) * 1.01,
                    "low_price": min(prior, closes[symbol]) * 0.99,
                    "close_price": closes[symbol],
                    "previous_close": prior,
                    "volume": 100_000.0,
                    "turnover_inr": 30_000_000.0 + index * 100_000 + offset,
                    "trade_count": 1_000.0,
                }
            )
        sessions.append(
            {
                "session_date": day,
                "udiff_sha256": f"{index + 1:064x}",
                "benchmark_sha256": f"{index + 1001:064x}",
                "equities": equities,
                "benchmark": {
                    "benchmark_id": "nifty_500",
                    "index_name": "Nifty 500",
                    "session_date": day,
                    "open_price": benchmark,
                    "close_price": benchmark,
                },
            }
        )
    panel = {
        "schema_version": 1,
        "panel_id": "AE001-HISTORICAL-MARKET-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "historical_archives_captured_prospectively": False,
        "start_date": sessions[0]["session_date"],
        "end_date": sessions[-1]["session_date"],
        "probed_calendar_day_count": count,
        "session_count": count,
        "sessions": sessions,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def test_rg001_builds_session_level_context_after_sixty_prior_sessions():
    panel = build_rg001_panel(_market_panel())
    assert panel["state_count"] == 5
    assert panel["variable_names"] == list(REGIME_VARIABLES)
    assert panel["stock_level_alpha"] is False
    assert panel["direct_cross_sectional_feature_use"] is False
    assert panel["outcomes_attached"] is False
    latest = panel["rows"][-1]
    assert latest["eligible_equity_count"] == 2
    assert 0.0 <= latest["values"]["breadth_advancer_fraction_1"] <= 1.0
    assert 0.0 <= latest["values"]["breadth_positive_momentum20_fraction"] <= 1.0
    assert latest["values"]["breadth_return_dispersion_1"] >= 0.0
    assert len(panel["panel_sha256"]) == 64


def test_rg001_is_deterministic():
    first = build_rg001_panel(_market_panel())
    second = build_rg001_panel(_market_panel())
    assert first == second


def test_rg001_rejects_market_panel_hash_tamper():
    panel = _market_panel()
    panel["sessions"][0]["benchmark"]["close_price"] += 1.0
    with pytest.raises(AlphaContractError, match="hash mismatch"):
        build_rg001_panel(panel)


def test_rg001_excludes_gapped_identity_from_breadth():
    panel = _market_panel(count=65)
    panel["sessions"][30]["equities"] = [
        row
        for row in panel["sessions"][30]["equities"]
        if row["symbol"] != "A"
    ]
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    panel["panel_sha256"] = digest(unsigned)

    result = build_rg001_panel(panel)
    assert result["rows"][-1]["eligible_equity_count"] == 1


def test_rg001_requires_at_least_sixty_prior_sessions():
    with pytest.raises(AlphaContractError, match="at least 61"):
        build_rg001_panel(_market_panel(count=60))
