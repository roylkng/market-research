"""Verify GESHIP P001's dated, non-investable asset-value stress contract."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/geship_p001_nav_stress.py"
SPEC = importlib.util.spec_from_file_location("geship_p001_nav_stress", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
INPUT = (
    REPO / "research/company-intelligence/geship-p001-nav-stress-input-20261025.json"
)


@pytest.fixture
def evidence():
    return json.loads(INPUT.read_text(encoding="utf-8"))


def test_reproduces_source_constrained_bridge(evidence):
    result = MODULE.evaluate(evidence)
    assert result["original_june_denominator_crore_shares"] == 14.277
    assert result["june_net_cash_per_share"] == 564.26
    assert result["residual_noncash_component_per_share"] == 1321.74
    assert result["reported_nav_discount_pct"] == 20.65
    assert result["break_even_residual_haircut_with_cash_unchanged_pct"] == 28.37
    assert result["conditional_research_watch_level_inr"] == 1233.84
    assert result["watch_level_is_trade_instruction"] is False
    assert result["capital_authorized"] is False


def test_return_sensitivity_is_not_promoted_to_forecast(evidence):
    scenarios = {r["name"]: r for r in MODULE.evaluate(evidence)["scenarios"]}
    assert 1050 < scenarios["shipping_cycle_bear"]["hypothetical_market_price"] < 1080
    assert scenarios["shipping_cycle_bear"]["price_change_vs_dated_close_pct"] < -28
    assert scenarios["defensive_repricing"]["price_change_vs_dated_close_pct"] < 0
    assert all(r["interpretation"] == "SENSITIVITY_NOT_FORECAST" for r in scenarios.values())


@pytest.mark.parametrize("key,value", [
    ("price_per_share_inr", 0),
    ("price_per_share_inr", float("nan")),
    ("face_value_inr", 0),
    ("paid_up_share_capital_lakh_inr", -1),
    ("reported_consolidated_net_cash_crore", -20),
    ("reported_consolidated_nav_per_share_inr", -1),
    ("q1_fy27_interim_dividend_inr", -1),
])
def test_bad_values_fail_closed(evidence, key, value):
    attempt = copy.deepcopy(evidence)
    attempt["inputs"][key] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(attempt)


def test_no_tampering_with_research_only_status(evidence):
    attempt = copy.deepcopy(evidence)
    attempt["purpose"] = "LIVE_BUY"
    with pytest.raises(ValueError, match="prospective signal"):
        MODULE.evaluate(attempt)
    attempt = copy.deepcopy(evidence)
    attempt["result_status"] = "APPROVED_BUY"
    with pytest.raises(ValueError, match="forbidden"):
        MODULE.evaluate(attempt)


def test_no_backdated_quote(evidence):
    attempt = copy.deepcopy(evidence)
    attempt["inputs"]["price_date"] = "2026-06-29"
    with pytest.raises(ValueError, match="chronology"):
        MODULE.evaluate(attempt)


@pytest.mark.parametrize("field,value", [
    ("residual_noncash_haircut", 1.1),
    ("net_cash_haircut", -0.1),
    ("exit_price_to_stressed_nav", 0),
])
def test_scenario_assumptions_fail_closed(evidence, field, value):
    attempt = copy.deepcopy(evidence)
    attempt["stress_scenarios"][0][field] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(attempt)


def test_watch_margin_validation(evidence):
    attempt = copy.deepcopy(evidence)
    attempt["watch_haircuts"]["margin_of_safety_fraction"] = -0.5
    with pytest.raises(ValueError, match="watch"):
        MODULE.evaluate(attempt)
