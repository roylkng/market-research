from datetime import date, timedelta
import math

import numpy as np
import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_v2 import FACTOR_NAMES_V2
from marketlab.rm001_v3 import (
    _relative_gaps,
    build_rm001_v3_risk_state,
    portfolio_risk_v3,
)


def _parent_artifacts(*, identity_count=12, missing_identity=None):
    start = date(2026, 1, 1)
    session_count = 130
    sessions = [
        (start + timedelta(days=index)).isoformat()
        for index in range(session_count)
    ]
    exposure_panel_sha = "e" * 64

    factor_returns = []
    residuals = []
    for t, session in enumerate(sessions):
        factors = {
            "MARKET_COMMON": 0.0007 * ((t % 7) - 3),
            "BETA60_RELATIVE": 0.0003 * ((t % 5) - 2),
            "MOMENTUM20": 0.0004 * ((t % 9) - 4),
            "VOLATILITY60": -0.0002 * ((t % 11) - 5),
            "LIQUIDITY": 0.00015 * ((t % 4) - 1.5),
            "SIZE": 0.00025 * ((t % 6) - 2.5),
        }
        factor_returns.append(
            {
                "exposure_session": session,
                "realized_session": session,
                "factor_returns": factors,
                "observation_count": identity_count,
            }
        )
        f1 = 0.006 * math.sin(t / 7.0)
        f2 = 0.003 * math.cos(t / 11.0)
        for i in range(identity_count):
            if missing_identity == i and t == session_count - 25:
                continue
            load1 = (i + 1) / identity_count
            load2 = ((i % 4) - 1.5) / 3.0
            noise = 0.00008 * (((t + i) % 5) - 2)
            residual = load1 * f1 + load2 * f2 + noise
            residuals.append(
                {
                    "exposure_session": session,
                    "realized_session": session,
                    "symbol": f"S{i:03d}",
                    "isin": f"INE{i:09d}",
                    "residual_return": residual,
                }
            )

    history = {
        "schema_version": 1,
        "model_id": "RM001-v2-DEVELOPMENT",
        "factor_names": list(FACTOR_NAMES_V2),
        "exposure_panel_sha256": exposure_panel_sha,
        "factor_return_count": len(factor_returns),
        "residual_count": len(residuals),
        "factor_returns": factor_returns,
        "residuals": residuals,
        "live_capital_allowed": False,
    }
    history["history_sha256"] = digest(history)

    rows = []
    for i in range(identity_count):
        rows.append(
            {
                "symbol": f"S{i:03d}",
                "isin": f"INE{i:09d}",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": (i - identity_count / 2) / identity_count,
                    "MOMENTUM20": ((i * 3) % identity_count) / identity_count - 0.5,
                    "VOLATILITY60": ((i * 5) % identity_count) / identity_count - 0.5,
                    "LIQUIDITY": ((i * 7) % identity_count) / identity_count - 0.5,
                    "SIZE": 2.0 * i / max(1, identity_count - 1) - 1.0,
                },
                "idiosyncratic_variance_daily": 0.001 + i * 1e-5,
                "idiosyncratic_status": "OBSERVED",
            }
        )
    risk = {
        "schema_version": 1,
        "model_id": "RM001-v2-DEVELOPMENT",
        "as_of_session": sessions[-1],
        "factor_names": list(FACTOR_NAMES_V2),
        "exposure_panel_sha256": exposure_panel_sha,
        "factor_history_sha256": history["history_sha256"],
        "factor_covariance_daily": np.eye(len(FACTOR_NAMES_V2)).tolist(),
        "rows": rows,
        "security_count": len(rows),
        "live_capital_allowed": False,
    }
    risk["state_sha256"] = digest(risk)
    return risk, history


def test_v3_extracts_deterministic_statistical_components():
    risk, history = _parent_artifacts()
    state = build_rm001_v3_risk_state(
        v2_risk_state=risk,
        v2_factor_history=history,
        statistical_window=120,
        component_count=2,
        minimum_complete_current_identities=8,
        minimum_singular_relative_gap=1e-10,
    )
    assert state["model_id"] == "RM001-v3-DEVELOPMENT"
    assert state["complete_statistical_identity_count"] == 12
    assert state["fallback_identity_count"] == 0
    assert state["statistical_factor_names"] == ["STAT_PC01", "STAT_PC02"]
    assert len(state["factor_names"]) == len(FACTOR_NAMES_V2) + 2
    assert len(state["factor_covariance_daily"]) == len(FACTOR_NAMES_V2) + 2
    assert all(
        anchor["anchor_loading_after_sign_fix"] >= 0
        for anchor in state["statistical_sign_anchors"]
    )
    assert sum(state["statistical_explained_variance_ratio"]) > 0.90
    parent_by_id = {
        (row["symbol"], row["isin"]): row
        for row in risk["rows"]
    }
    for row in state["rows"]:
        identity = (row["symbol"], row["isin"])
        assert row["statistical_status"] == "STAT_COMPLETE_120"
        assert row["idiosyncratic_variance_daily"] < parent_by_id[identity][
            "idiosyncratic_variance_daily"
        ]
    assert len(state["state_sha256"]) == 64


def test_v3_incomplete_history_preserves_v2_idio_and_zero_stat_exposure():
    risk, history = _parent_artifacts(missing_identity=3)
    state = build_rm001_v3_risk_state(
        v2_risk_state=risk,
        v2_factor_history=history,
        statistical_window=120,
        component_count=2,
        minimum_complete_current_identities=8,
        minimum_singular_relative_gap=1e-10,
    )
    assert state["complete_statistical_identity_count"] == 11
    assert state["fallback_identity_count"] == 1
    parent = next(row for row in risk["rows"] if row["symbol"] == "S003")
    fallback = next(row for row in state["rows"] if row["symbol"] == "S003")
    assert fallback["statistical_status"] == "V2_FALLBACK_NO_COMPLETE_STAT_HISTORY"
    assert fallback["exposures"]["STAT_PC01"] == pytest.approx(0.0)
    assert fallback["exposures"]["STAT_PC02"] == pytest.approx(0.0)
    assert fallback["idiosyncratic_variance_daily"] == pytest.approx(
        parent["idiosyncratic_variance_daily"]
    )


def test_v3_fails_closed_when_complete_history_universe_too_small():
    risk, history = _parent_artifacts(identity_count=6, missing_identity=0)
    with pytest.raises(AlphaContractError, match="universe is too small"):
        build_rm001_v3_risk_state(
            v2_risk_state=risk,
            v2_factor_history=history,
            statistical_window=120,
            component_count=2,
            minimum_complete_current_identities=6,
            minimum_singular_relative_gap=1e-10,
        )


def test_relative_gap_detects_degenerate_components():
    gaps = _relative_gaps(np.asarray([2.0, 2.0, 1.0]), 2)
    assert gaps == [pytest.approx(0.0)]


def test_portfolio_risk_v3_matches_direct_matrix_algebra():
    risk, history = _parent_artifacts()
    state = build_rm001_v3_risk_state(
        v2_risk_state=risk,
        v2_factor_history=history,
        statistical_window=120,
        component_count=2,
        minimum_complete_current_identities=8,
        minimum_singular_relative_gap=1e-10,
    )
    positions = [
        {"symbol": "S000", "isin": "INE000000000", "weight": 0.4},
        {"symbol": "S001", "isin": "INE000000001", "weight": 0.5},
    ]
    report = portfolio_risk_v3(state, positions=positions)

    by_id = {
        (row["symbol"], row["isin"]): row
        for row in state["rows"]
    }
    factor_names = state["factor_names"]
    weights = np.asarray([0.4, 0.5])
    exposure_matrix = np.asarray(
        [
            [by_id[("S000", "INE000000000")]["exposures"][f] for f in factor_names],
            [by_id[("S001", "INE000000001")]["exposures"][f] for f in factor_names],
        ],
        dtype=float,
    )
    factor_exposure = weights @ exposure_matrix
    covariance = np.asarray(state["factor_covariance_daily"], dtype=float)
    expected_factor = float(factor_exposure @ covariance @ factor_exposure)
    idio = np.asarray(
        [
            by_id[("S000", "INE000000000")]["idiosyncratic_variance_daily"],
            by_id[("S001", "INE000000001")]["idiosyncratic_variance_daily"],
        ],
        dtype=float,
    )
    expected_idio = float(np.sum((weights**2) * idio))
    assert report["factor_variance_daily"] == pytest.approx(expected_factor)
    assert report["idiosyncratic_variance_daily"] == pytest.approx(expected_idio)
    assert report["total_variance_daily"] == pytest.approx(
        expected_factor + expected_idio
    )
