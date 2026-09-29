import pytest

from marketlab.tc001_t003 import build_t003_tc001_report


def _source():
    return {
        "analysis_id": "AE001-T003-TC001-v1",
        "source_run_id": 1,
        "source_report_sha256": "a" * 64,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "horizon_sessions": 5,
        "base": {
            "mean_top_decile_excess": 0.004,
            "average_top_decile_selection_churn": 0.30,
        },
        "augmented": {
            "mean_top_decile_excess": 0.006,
            "average_top_decile_selection_churn": 0.40,
        },
        "paired_augmented_minus_base": {},
        "cost_interpretation": {
            "long_short_spread_costed_by_tc001_v1": False,
        },
        "illustrative_execution_scenarios": {
            "BASE": {
                "half_spread_bps_each_side": 3.0,
                "daily_volatility_decimal": 0.02,
                "participation_rate": 0.005,
                "impact_coefficient": 0.5,
            }
        },
    }


def test_t003_cost_overlay_uses_same_clock_for_5d_cohort_net():
    report = build_t003_tc001_report(_source())
    surface = report["observable_cost_floor"]
    rt = surface["equal_notional_round_trip_bps"]
    base = surface["cohort_5d"]["base"]
    augmented = surface["cohort_5d"]["augmented"]

    assert base["net_5d_excess_after_full_round_trip_bps"] == pytest.approx(
        40.0 - rt
    )
    assert augmented[
        "net_5d_excess_after_full_round_trip_bps"
    ] == pytest.approx(60.0 - rt)
    assert surface["cohort_5d"][
        "augmented_minus_base_net_5d_excess_bps"
    ] == pytest.approx(20.0)


def test_daily_churn_cost_is_not_netted_into_5d_forward_label():
    report = build_t003_tc001_report(_source())
    pressure = report["observable_cost_floor"][
        "daily_selection_turnover_pressure"
    ]
    assert pressure["may_be_subtracted_from_5d_forward_label"] is False
    assert report["interpretation_limits"]["mixed_clock_netting_prohibited"] is True
    assert report["interpretation_limits"][
        "net_rolling_portfolio_pnl_estimated"
    ] is False
