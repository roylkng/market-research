from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.fundamental_quality_score import (
    EXPECTED_PANEL_SHA256,
    EXPECTED_UNIVERSE_SHA256,
    build_quality_score,
)


def _record(index: int) -> dict:
    value = float(index + 1)
    return {
        "symbol": f"S{index:03d}",
        "all_core_metrics_complete": True,
        "target_facts": {
            "profit_after_tax": 100.0,
            "total_equity": 100.0,
            "revenue": 1000.0,
            "total_assets": 500.0,
            "current_liabilities": 100.0,
        },
        "baseline_facts": {
            "total_assets": 480.0,
            "current_liabilities": 100.0,
        },
        "metrics": {
            "roce_proxy": value,
            "cfo_to_pat": value,
            "cfo_minus_ppe_to_pat": value,
            "accruals_to_avg_assets": -value,
            "net_borrowings_to_equity": -value,
            "ppe_capex_to_revenue": value / 1000.0,
        },
        "issuer_identity_continuity": "SAME_ISIN",
        "record_sha256": f"record-{index:03d}",
    }


def _panel() -> dict:
    records = [_record(index) for index in range(88)]
    records[84]["target_facts"]["profit_after_tax"] = 0.0
    records[85]["target_facts"]["profit_after_tax"] = -1.0
    records[86]["target_facts"]["total_equity"] = 0.0
    records[87]["target_facts"]["total_equity"] = -1.0

    failures = [
        {
            "symbol": f"F{index:03d}",
            "stage": "PAIR_SELECTION",
            "reason": "TEST_SOURCE_UNAVAILABLE",
        }
        for index in range(12)
    ]
    return {
        "diagnostic_id": "FQ001-D001-P2-v1",
        "panel_sha256": EXPECTED_PANEL_SHA256,
        "universe_sha256": EXPECTED_UNIVERSE_SHA256,
        "records": records,
        "failures": failures,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_frozen_quality_score_has_84_scored_rows_and_four_prerequisite_failures() -> None:
    result = build_quality_score(_panel())

    assert result["scored_count"] == 84
    assert result["quality_prerequisite_failed_count"] == 4
    assert result["source_unavailable_count"] == 12
    assert result["top_quality_quartile_count"] == 21

    assert result["scored"][0]["symbol"] == "S083"
    assert result["scored"][0]["quality_rank"] == 1
    assert result["scored"][0]["quality_score"] == pytest.approx(99.4047619047619)
    assert result["scored"][-1]["symbol"] == "S000"
    assert result["scored"][-1]["quality_score"] == pytest.approx(0.5952380952380952)

    failed = {row["symbol"]: row for row in result["quality_prerequisite_failed"]}
    assert "PAT_NONPOSITIVE" in failed["S084"]["reason_codes"]
    assert "PAT_NONPOSITIVE" in failed["S085"]["reason_codes"]
    assert "EQUITY_NONPOSITIVE" in failed["S086"]["reason_codes"]
    assert "EQUITY_NONPOSITIVE" in failed["S087"]["reason_codes"]

    assert result["return_outcomes_opened"] is False
    assert result["model_fitted"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False


def test_ppe_capex_is_context_only_not_a_score_pillar() -> None:
    panel = _panel()
    result = build_quality_score(panel)
    row = next(row for row in result["scored"] if row["symbol"] == "S010")

    assert "ppe_capex_to_revenue" not in row["pillars"]
    assert row["ppe_capex_to_revenue_context"] == pytest.approx(0.011)
    assert result["score_rule"]["ppe_capex_to_revenue_role"] == "CONTEXT_ONLY_NOT_SCORED"


def test_quality_score_refuses_any_other_source_panel_sha() -> None:
    panel = _panel()
    panel["panel_sha256"] = "wrong"

    with pytest.raises(AlphaContractError, match="source panel SHA mismatch"):
        build_quality_score(panel)
