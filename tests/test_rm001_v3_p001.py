import numpy as np
import pytest

from marketlab.alpha import digest
from marketlab.rm001_v2 import FACTOR_NAMES_V2
from marketlab.rm001_v3 import FACTOR_NAMES_V3, STAT_FACTOR_NAMES
from marketlab.rm001_v3_p001 import run_rm001_v3_p001


def _v2_state(count=500):
    rows = []
    for index in range(count):
        rows.append(
            {
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    factor: (
                        1.0
                        if factor == "MARKET_COMMON"
                        else ((index % 101) / 50.0 - 1.0) * 0.2
                    )
                    for factor in FACTOR_NAMES_V2
                },
                "idiosyncratic_variance_daily": 0.0004 + index * 1e-8,
                "idiosyncratic_status": "OBSERVED",
            }
        )
    covariance = np.diag(
        [0.00002, 0.00001, 0.000008, 0.000009, 0.000004, 0.000006]
    ).tolist()
    state = {
        "schema_version": 1,
        "model_id": "RM001-v2-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": list(FACTOR_NAMES_V2),
        "factor_covariance_daily": covariance,
        "exposure_panel_sha256": "e" * 64,
        "factor_history_sha256": "h" * 64,
        "security_count": len(rows),
        "rows": rows,
        "size_contract": {},
        "deferred_factors": {
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN"
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _v2_history(v2_state):
    history = {
        "schema_version": 1,
        "model_id": "RM001-v2-DEVELOPMENT",
        "factor_names": list(FACTOR_NAMES_V2),
        "exposure_panel_sha256": v2_state["exposure_panel_sha256"],
        "factor_return_count": 130,
        "residual_count": 0,
        "factor_returns": [],
        "residuals": [],
        "live_capital_allowed": False,
    }
    history["history_sha256"] = digest(history)
    return history


def _v3_state(v2_state, v2_history):
    rows = []
    for index, parent in enumerate(v2_state["rows"]):
        exposures = dict(parent["exposures"])
        for pc_index, factor in enumerate(STAT_FACTOR_NAMES):
            exposures[factor] = ((index + pc_index) % 31) / 100.0 - 0.15
        rows.append(
            {
                "symbol": parent["symbol"],
                "isin": parent["isin"],
                "exposures": exposures,
                "idiosyncratic_variance_daily": (
                    parent["idiosyncratic_variance_daily"] * 0.75
                ),
                "idiosyncratic_status": parent["idiosyncratic_status"],
                "statistical_status": "STAT_COMPLETE_120",
            }
        )

    diagonal = [
        0.00002,
        0.00001,
        0.000008,
        0.000009,
        0.000004,
        0.000006,
        0.000003,
        0.0000025,
        0.000002,
        0.0000015,
        0.000001,
    ]
    covariance = np.diag(diagonal).tolist()
    state = {
        "schema_version": 1,
        "model_id": "RM001-v3-DEVELOPMENT",
        "parent_model_id": "RM001-v2-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": list(FACTOR_NAMES_V3),
        "named_factor_names": list(FACTOR_NAMES_V2),
        "statistical_factor_names": list(STAT_FACTOR_NAMES),
        "statistical_window": 120,
        "statistical_first_realized_session": "2026-03-01",
        "statistical_last_realized_session": "2026-08-31",
        "statistical_component_count": 5,
        "minimum_complete_current_identities": 500,
        "complete_statistical_identity_count": len(rows),
        "fallback_identity_count": 0,
        "singular_values": [3.0, 2.5, 2.0, 1.5, 1.0],
        "adjacent_singular_relative_gaps": [
            1 / 6,
            0.2,
            0.25,
            1 / 3,
        ],
        "minimum_singular_relative_gap": 1e-8,
        "statistical_explained_variance_ratio": [
            0.20,
            0.15,
            0.10,
            0.07,
            0.05,
        ],
        "statistical_sign_anchors": [
            {
                "factor": factor,
                "symbol": "S000",
                "isin": "INE000000000",
                "anchor_loading_before_sign_fix": 0.1,
                "sign_flipped": False,
                "anchor_loading_after_sign_fix": 0.1,
            }
            for factor in STAT_FACTOR_NAMES
        ],
        "statistical_basis_window": 120,
        "risk_estimation_window": 60,
        "factor_covariance_window": 60,
        "factor_covariance_first_realized_session": "2026-07-01",
        "factor_covariance_last_realized_session": "2026-08-31",
        "idiosyncratic_window": 60,
        "factor_covariance_daily": covariance,
        "security_count": len(rows),
        "rows": rows,
        "parent_v2_risk_state_sha256": v2_state["state_sha256"],
        "parent_v2_factor_history_sha256": v2_history["history_sha256"],
        "exposure_panel_sha256": v2_state["exposure_panel_sha256"],
        "deferred_factors": {
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN"
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _sealed_i002():
    positions = [
        {
            "symbol": f"S{index:03d}",
            "isin": f"INE{index:09d}",
            "target_weight": 0.05,
            "expected_excess_return": 0.01,
        }
        for index in range(20)
    ]
    portfolios = {}
    for key in (
        "equal_weight_top_decile",
        "positive_alpha_proportional_top_decile",
        "risk_aware_zero_cost",
        "full_po001_observable_cost_floor",
    ):
        portfolios[key] = {
            "positions": positions,
        }
    artifact = {
        "schema_version": 1,
        "study_id": "PO001-I002-v1",
        "decision_session": "2026-08-31",
        "realized_outcome_opened": False,
        "portfolios": portfolios,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def test_v3_p001_attributes_exact_same_i002_portfolios():
    v2 = _v2_state()
    history = _v2_history(v2)
    v3 = _v3_state(v2, history)
    report = run_rm001_v3_p001(
        v2_risk_state=v2,
        v2_factor_history=history,
        v3_risk_state=v3,
        sealed_i002_artifact=_sealed_i002(),
    )

    assert report["identity"]["identity_sets_equal"] is True
    assert report["identity"]["complete_statistical_identity_count"] == 500
    assert report["idiosyncratic"]["median_variance_delta"] < 0
    assert report["idiosyncratic"]["identity_count_lower_in_v3"] == 500
    assert set(report["sealed_i002_portfolio_risk"]) == {
        "equal_weight_top_decile",
        "positive_alpha_proportional_top_decile",
    }
    assert report["control_resolution"]["protocol_amendment"] == (
        "RM001-v3-P001-P2"
    )
    assert report["control_resolution"][
        "exact_preserved_portfolios_used"
    ] == [
        "equal_weight_top_decile",
        "positive_alpha_proportional_top_decile",
    ]
    assert set(report["control_resolution"]["unavailable_portfolios"]) == {
        "risk_aware_zero_cost",
        "full_po001_observable_cost_floor",
    }
    full = report["sealed_i002_portfolio_risk"][
        "equal_weight_top_decile"
    ]
    assert set(full["statistical_factor_exposures"]) == set(
        STAT_FACTOR_NAMES
    )
    assert full["v3_factor_contribution_sum_daily"] == pytest.approx(
        full["v3"]["factor_variance_daily"]
    )
    assert report["interpretation_limits"]["return_outcome_opened"] is False
    assert report["interpretation_limits"]["portfolio_reoptimized"] is False
    assert len(report["report_sha256"]) == 64
