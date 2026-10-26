"""OPEN008: capital-access sensitivity and original evidence immutability."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open008_justdial_cash_trap.py"
SPEC = importlib.util.spec_from_file_location("open008", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
INPUT = ROOT / "research/broad-discovery/OPEN008_JUSTDIAL_CASH_TRAP_INPUT_20261026.json"


@pytest.fixture
def packet():
    return json.loads(INPUT.read_text(encoding="utf-8"))


def test_source_anchoring_and_reproducible_cash_trap(packet):
    result = MODULE.evaluate(packet)
    assert result["source_market_cap_cr"] == 5943.2264
    assert result["illustrative_net_liquid_before_restrictions_cr"] == 5173.34
    assert result["annualized_selected_cash_not_owner_fcfe_cr"] == 190.68
    assert result["probability_weighted_equity_value"] is None
    assert result["forecast_return"] is None
    assert result["capital_authorized"] is False

    rows = {s["name"]: s for s in result["scenarios"]}
    expected = {
        "immediate_hypothetical_distribution": (6317.42, 6.30),
        "three_year_cash_retention": (5632.07, -5.24),
        "five_year_cash_retention": (5187.45, -12.72),
        "ten_year_cash_retention": (4160.56, -30.00),
        "five_year_growth_5pct": (5427.10, -8.68),
        "five_year_growth_5pct_higher_exit_multiple": (5703.28, -4.04),
        "five_year_lower_required_return": (5676.50, -4.49),
        "five_year_higher_portfolio_return": (6037.37, 1.58),
    }
    assert {k: (v["discounted_hypothetical_equity_value_cr"],
                v["relative_to_observed_market_cap_pct"])
            for k, v in rows.items()} == expected
    assert all(x["research_only_not_value_forecast"] for x in rows.values())
    assert all(x["capital_authorized"] is False for x in rows.values())


def test_original_registered_git_blob_sha_is_not_substituted(packet):
    changed = copy.deepcopy(packet)
    changed["source_baseline_git_blob_sha"] = "a" * 40
    with pytest.raises(ValueError, match="SHA mismatched"):
        MODULE.evaluate(changed)


def test_original_date_controller_or_dividend_note_not_mutable(packet):
    for field, bad in (
        ("date", "2026-10-15"),
        ("controlling_shareholder", "UNRELATED"),
        ("historical_dividends_since_fy2014_15", "DIVIDEND_2026"),
        ("reported_promoter_group_2026_sep_pct", 40.0),
    ):
        changed = copy.deepcopy(packet)
        changed[field] = bad
        with pytest.raises(ValueError):
            MODULE.evaluate(changed)


def test_no_live_capital_or_invented_probabilities(packet):
    for key, bad in (
        ("investment_approved", True),
        ("calibrated_scenario_probabilities", {"bear": 0.5}),
        ("source_raw_bytes_archived", True),
        ("target_price_recommendation", 6317.42),
        ("historical_h002_h003_hg009_retroactive_change", True),
    ):
        changed = copy.deepcopy(packet)
        changed["promotion_prohibited"][key] = bad
        with pytest.raises(ValueError, match="false original custody"):
            MODULE.evaluate(changed)


@pytest.mark.parametrize(("field", "value"), [
    ("years_without_common_shareholder_distribution", -1),
    ("years_without_common_shareholder_distribution", 11),
    ("illustrative_net_treasury_yield", float("nan")),
    ("illustrative_equity_hurdle", 0),
    ("illustrative_cash_generation_growth", 0.5),
    ("terminal_franchise_cash_multiple", 0.5),
])
def test_scenarios_fail_closed(packet, field, value):
    changed = copy.deepcopy(packet)
    changed["scenarios"][0][field] = value
    with pytest.raises((ValueError, TypeError)):
        MODULE.evaluate(changed)


def test_published_cfo_is_not_claimed_as_owner_distribution(packet):
    result = MODULE.evaluate(packet)
    assert result["decision"] == "CASH_TRAP_MAY_ERASE_APPARENT_DISCOUNT_NO_BUY"
    assert result["annualized_selected_cash_not_owner_fcfe_cr"] == 190.68
    assert result["scenarios"][0]["hypothetical_no_distribution_years"] == 0


def test_no_probability_weighting_or_expected_returns(packet):
    result = MODULE.evaluate(packet)
    assert all(
        "assumed_shareholder_discount_pct" in row
        and "relative_to_observed_market_cap_pct" in row
        for row in result["scenarios"]
    )
    assert "expected_annual_return" not in result
