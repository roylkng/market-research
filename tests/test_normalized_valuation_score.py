from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.normalized_valuation_score import build_normalized_valuation_score


def _record(symbol: str, history: list[float], current: float | None) -> dict:
    return {
        "symbol": symbol,
        "accounting_basis": "Consolidated",
        "record_sha256": f"sha-{symbol}",
        "historical_pe_count": len(history),
        "current_trailing_pe": current,
        "annual_observations": [
            {"period_end": f"20{23 + i}-03-31", "trailing_pe": value}
            for i, value in enumerate(history)
        ],
    }


def _panel() -> dict:
    records = []
    for idx in range(69):
        symbol = f"S{idx:02d}"
        history = [10.0, 12.0, 14.0, 16.0]
        current = 8.0 + idx * 0.2
        records.append(_record(symbol, history, current))
    for idx in range(21):
        records.append(_record(f"P{idx:02d}", [10.0, 12.0, 14.0], 11.0))
    failures = [
        {"symbol": f"F{idx:02d}", "stage": "ANNUAL_SELECTION", "reason": "missing"}
        for idx in range(10)
    ]
    return {
        "diagnostic_id": "NV001-D001-P1-v1",
        "panel_sha256": (
            "3dbe5b914a532bb028ad38c6b6eec9762ef47f31ccc85289d1d1f9b69b251400"
        ),
        "universe_sha256": (
            "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
        ),
        "records": records,
        "failures": failures,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_lower_current_to_history_multiple_gets_higher_score() -> None:
    result = build_normalized_valuation_score(_panel())
    rows = {row["symbol"]: row for row in result["rows"]}

    assert result["scored_count"] == 69
    assert result["insufficient_complete_history_count"] == 21
    assert result["source_unavailable_count"] == 10
    assert rows["S00"]["normalized_valuation_score"] > rows["S68"][
        "normalized_valuation_score"
    ]
    assert rows["S00"]["current_to_history_median"] == pytest.approx(8.0 / 13.0)
    assert rows["S00"]["discount_to_history_median_pct"] > 0
    assert rows["S00"]["valuation_rank"] == 1


def test_top_quartile_is_research_context_only() -> None:
    result = build_normalized_valuation_score(_panel())
    assert result["top_valuation_quartile_count"] >= 18
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
    assert all(row["portfolio_eligibility_allowed"] is False for row in result["rows"])


def test_source_hash_mismatch_fails_closed() -> None:
    panel = _panel()
    panel["panel_sha256"] = "wrong"
    with pytest.raises(AlphaContractError, match="source panel SHA mismatch"):
        build_normalized_valuation_score(panel)


def test_current_pe_must_be_positive_and_complete_history_required() -> None:
    panel = _panel()
    panel["records"][0]["current_trailing_pe"] = None
    with pytest.raises(AlphaContractError, match="expected 69 eligible"):
        build_normalized_valuation_score(panel)
