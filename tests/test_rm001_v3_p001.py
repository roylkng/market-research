import numpy as np
import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_v2 import FACTOR_NAMES_V2
from marketlab.rm001_v3 import STAT_FACTOR_NAMES
from marketlab.rm001_v3_p001 import run_rm001_v3_p001


def _v2_state():
    rows = []
    for index in range(3):
        rows.append(
            {
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": 0.1 * index,
                    "MOMENTUM20": -0.2 + 0.2 * index,
                    "VOLATILITY60": 0.3 - 0.1 * index,
                    "LIQUIDITY": -0.1 + 0.1 * index,
                    "SIZE": -1.0 + index,
                },
                "idiosyncratic_variance_daily": 0.0004 + index * 0.0001,
                "idiosyncratic_status": "OBSERVED",
            }
        )
    state = {
        "schema_version": 1,
        "model_id": "RM001-v2-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": list(FACTOR_NAMES_V2),
        "factor_covariance_window": 60,
        "factor_covariance_first_realized_session": "2026-06-08",
        "factor_covariance_last_realized_session": "2026-08-31",
        "factor_covariance_daily": (
            np.eye(len(FACTOR_NAMES_V2)) * 0.00001
        ).tolist(),
        "exposure_panel_sha256": "e" * 64,
        "factor_history_sha256": "h" * 64,
        "security_count": 3,
        "rows": rows,
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _v3_state(v2):
    factors = [*FACTOR_NAMES_V2, *STAT_FACTOR_NAMES]
    rows = []
    for index, parent in enumerate(v2["rows"]):
        exposures = dict(parent["exposures"])
        if index < 2:
            for pc_index, factor in enumerate(STAT_FACTOR_NAMES):
                exposures[factor] = (index + 1) * (pc_index + 1) * 0.01
            idio = parent["idiosyncratic_variance_daily"] * 0.5
            stat_status = "STAT_COMPLETE_120"
        else:
            for factor in STAT_FACTOR_NAMES:
                exposures[factor] = 0.0
            idio = parent["idiosyncratic_variance_daily"]
            stat_status = "V2_FALLBACK_NO_COMPLETE_STAT_HISTORY"
        rows.append(
            {
                "symbol": parent["symbol"],
                "isin": parent["isin"],
                "exposures": exposures,
                "idiosyncratic_variance_daily": idio,
                "idiosyncratic_status": parent["idiosyncratic_status"],
                "statistical_status": stat_status,
            }
        )
    covariance = np.eye(len(factors)) * 0.00001
    state = {
        "schema_version": 1,
        "model_id": "RM001-v3-DEVELOPMENT",
        "parent_model_id": "RM001-v2-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": factors,
        "named_factor_names": list(FACTOR_NAMES_V2),
        "statistical_factor_names": list(STAT_FACTOR_NAMES),
        "statistical_basis_window": 120,
        "risk_estimation_window": 60,
        "factor_covariance_window": 60,
        "factor_covariance_first_realized_session": "2026-06-08",
        "factor_covariance_last_realized_session": "2026-08-31",
        "idiosyncratic_window": 60,
        "statistical_component_count": 5,
        "complete_statistical_identity_count": 2,
        "fallback_identity_count": 1,
        "singular_values": [2.0, 1.5, 1.0, 0.7, 0.4],
        "adjacent_singular_relative_gaps": [
            0.25,
            1 / 3,
            0.3,
            3 / 7,
        ],
        "statistical_explained_variance_ratio": [
            0.30,
            0.20,
            0.10,
            0.05,
            0.02,
        ],
        "statistical_sign_anchors": [],
        "factor_covariance_daily": covariance.tolist(),
        "security_count": 3,
        "rows": rows,
        "parent_v2_risk_state_sha256": v2["state_sha256"],
        "parent_v2_factor_history_sha256": "h" * 64,
        "exposure_panel_sha256": v2["exposure_panel_sha256"],
        "deferred_factors": {
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN"
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _i002_artifact():
    def positions(weights):
        return [
            {
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "weight": weight,
                "expected_excess_return": 0.01 - index * 0.001,
            }
            for index, weight in enumerate(weights)
            if weight > 0
        ]

    artifact = {
        "schema_version": 1,
        "study_id": "PO001-I002-v1",
        "decision_session": "2026-08-31",
        "realized_outcome_opened": False,
        "portfolios": {
            "equal_weight_top_decile": {
                "positions": positions([0.5, 0.5, 0.0]),
            },
            "positive_alpha_proportional_top_decile": {
                "positions": positions([0.6, 0.4, 0.0]),
            },
        },
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def test_p001_preserves_identity_and_named_exposures(monkeypatch):
    v2 = _v2_state()
    v3 = _v3_state(v2)
    monkeypatch.setattr(
        "marketlab.rm001_v3_p001.MIN_COMPLETE_STATISTICAL_IDENTITIES",
        2,
    )
    report = run_rm001_v3_p001(
        v2_risk_state=v2,
        v3_risk_state=v3,
        sealed_i002_artifact=_i002_artifact(),
    )
    assert report["treatment_isolation"][
        "named_covariance_max_abs_diff"
    ] == pytest.approx(0.0)
    assert report["identity"]["exact_identity_set_match"] is True
    assert report["identity"]["complete_statistical_identity_count"] == 2
    assert report["identity"]["fallback_identity_count"] == 1
    assert report["statistical_basis"][
        "cumulative_explained_variance_ratio"
    ] == pytest.approx(0.67)
    assert report["complete_identity_idiosyncratic"][
        "v3_median_variance"
    ] < report["complete_identity_idiosyncratic"]["v2_median_variance"]
    for portfolio in report["sealed_i002_portfolio_risk"].values():
        assert max(
            abs(value)
            for value in portfolio[
                "named_factor_exposure_delta"
            ].values()
        ) <= 1e-12
        assert set(
            portfolio["statistical_factor_exposures"]
        ) == set(STAT_FACTOR_NAMES)
    assert report["interpretation_limits"]["alpha_outcome_opened"] is False
    assert report["interpretation_limits"][
        "oos_risk_calibration_required_next"
    ] is True
    assert len(report["report_sha256"]) == 64


def test_p001_rejects_fallback_idio_change(monkeypatch):
    v2 = _v2_state()
    v3 = _v3_state(v2)
    v3["rows"][2]["idiosyncratic_variance_daily"] += 1e-6
    unsigned = dict(v3)
    unsigned.pop("state_sha256", None)
    v3["state_sha256"] = digest(unsigned)
    monkeypatch.setattr(
        "marketlab.rm001_v3_p001.MIN_COMPLETE_STATISTICAL_IDENTITIES",
        2,
    )
    with pytest.raises(AlphaContractError, match="fallback identity changed"):
        run_rm001_v3_p001(
            v2_risk_state=v2,
            v3_risk_state=v3,
            sealed_i002_artifact=_i002_artifact(),
        )


def test_p001_rejects_named_factor_exposure_drift(monkeypatch):
    v2 = _v2_state()
    v3 = _v3_state(v2)
    v3["rows"][0]["exposures"]["SIZE"] += 1e-6
    unsigned = dict(v3)
    unsigned.pop("state_sha256", None)
    v3["state_sha256"] = digest(unsigned)
    monkeypatch.setattr(
        "marketlab.rm001_v3_p001.MIN_COMPLETE_STATISTICAL_IDENTITIES",
        2,
    )
    with pytest.raises(AlphaContractError, match="named exposure changed"):
        run_rm001_v3_p001(
            v2_risk_state=v2,
            v3_risk_state=v3,
            sealed_i002_artifact=_i002_artifact(),
        )
