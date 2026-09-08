from marketlab.h004 import evaluate_h004_row


def base_row() -> dict[str, object]:
    return {
        "median_20d_traded_value_inr": 50_000_000,
        "prior_5d_return_pct": 1.0,
        "prior_20d_return_pct": 5.0,
        "prior_1d_return_pct": 0.5,
        "revenue_yoy_pct": 30.0,
        "operating_profit_yoy_pct": 50.0,
        "pat_yoy_pct": 80.0,
        "margin_change_pp": 2.0,
        "quarterly_pat_inr_crore": 20.0,
        "catalyst_grade": 0,
        "event_age_sessions": 5,
        "event_to_decision_return_pct": 2.0,
        "sector_context_positive": True,
        "valuation_asymmetry_positive": True,
        "balance_sheet_capacity_positive": True,
        "trigger_1d_return_pct": 3.0,
        "trigger_volume_vs_20d_median": 2.5,
        "trigger_delivery_vs_20d_median": 1.0,
        "trigger_sector_relative_return_pp": 1.0,
        "trigger_close_within_5pct_60d_high": False,
        "trigger_prior_5d_return_pct": 8.0,
    }


def test_strong_earnings_inflection_enters_watchlist_without_momentum():
    result = evaluate_h004_row(base_row())
    assert result.stage1_eligible is True
    assert result.primary_universe is True
    assert "EARNINGS_INFLECTION" in result.anchors
    assert result.expectation_gap is True
    assert result.stage2_trigger is True


def test_obvious_prior_momentum_blocks_stage1_even_with_strong_results():
    row = base_row()
    row["prior_5d_return_pct"] = 12.0
    result = evaluate_h004_row(row)
    assert result.pre_momentum_eligible is False
    assert result.stage1_eligible is False
    assert result.stage2_trigger is False


def test_one_off_pat_invalidates_earnings_anchor():
    row = base_row()
    row["deconsolidation_gain_primary_driver"] = True
    result = evaluate_h004_row(row)
    assert "EARNINGS_INFLECTION" not in result.anchors
    assert "EARNINGS_ANCHOR_INVALIDATED_BY_ONE_OFF" in result.quality_warnings
    assert result.stage1_eligible is False


def test_material_corporate_catalyst_can_qualify_despite_one_off_earnings():
    row = base_row()
    row["deconsolidation_gain_primary_driver"] = True
    row["catalyst_grade"] = 4
    result = evaluate_h004_row(row)
    assert "EARNINGS_INFLECTION" not in result.anchors
    assert "CORPORATE_CATALYST" in result.anchors
    assert result.stage1_eligible is True


def test_tiny_profit_is_discovery_only_for_earnings_anchor():
    row = base_row()
    row["quarterly_pat_inr_crore"] = 0.5
    result = evaluate_h004_row(row)
    assert result.speculative_base_effect is True
    assert "EARNINGS_INFLECTION" not in result.anchors
    assert result.stage1_eligible is False


def test_tiny_profit_can_still_be_discovery_catalyst_signal():
    row = base_row()
    row["median_20d_traded_value_inr"] = 5_000_000
    row["quarterly_pat_inr_crore"] = 0.5
    row["catalyst_grade"] = 3
    result = evaluate_h004_row(row)
    assert result.primary_universe is False
    assert result.discovery_universe is True
    assert result.stage1_eligible is True
    assert "SPECULATIVE_BASE_EFFECT" in result.quality_warnings


def test_upper_circuit_without_realistic_entry_is_not_executable():
    row = base_row()
    row["first_trigger_is_upper_circuit"] = True
    row["trigger_volume_vs_20d_median"] = 10.0
    result = evaluate_h004_row(row)
    assert result.stage1_eligible is True
    assert result.not_executable is True
    assert result.stage2_trigger is False


def test_governance_guardrail_hard_rejects_candidate():
    row = base_row()
    row["rising_promoter_pledge"] = True
    result = evaluate_h004_row(row)
    assert result.stage1_eligible is False
    assert "RISING_PROMOTER_PLEDGE" in result.hard_reject_reasons
