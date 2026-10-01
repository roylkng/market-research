import numpy as np
import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001 import FACTOR_NAMES
from marketlab.rm001_v2 import FACTOR_NAMES_V2
from marketlab.rm001_v2_p001 import (
    _control_positions,
    run_rm001_v2_p001,
)


def _risk_state(*, v2: bool):
    factors = FACTOR_NAMES_V2 if v2 else FACTOR_NAMES
    rows = []
    for index, size in enumerate((-0.5, 0.5)):
        exposures = {
            factor: (
                1.0
                if factor == "MARKET_COMMON"
                else size
                if factor == "SIZE"
                else 0.1 * (index + 1)
            )
            for factor in factors
        }
        rows.append(
            {
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "exposures": exposures,
                "idiosyncratic_variance_daily": (
                    0.000009 if v2 else 0.00001
                ),
                "idiosyncratic_status": "OBSERVED",
            }
        )
    covariance = np.diag([0.000001] * len(factors)).tolist()
    state = {
        "schema_version": 1,
        "model_id": (
            "RM001-v2-DEVELOPMENT"
            if v2
            else "RM001-v1-DEVELOPMENT"
        ),
        "as_of_session": "2026-08-31",
        "factor_names": list(factors),
        "factor_covariance_daily": covariance,
        "idiosyncratic_fallback_p75": 0.00001,
        "rows": rows,
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _sealed_i002():
    artifact = {
        "schema_version": 1,
        "study_id": "PO001-I002-v1",
        "decision_session": "2026-08-31",
        "realized_outcome_opened": False,
        "portfolios": {
            "equal_weight_top_decile": {
                "positions": [
                    {
                        "symbol": "S0",
                        "isin": "INE000000000",
                        "weight": 0.5,
                        "expected_excess_return": 0.01,
                    },
                    {
                        "symbol": "S1",
                        "isin": "INE000000001",
                        "weight": 0.5,
                        "expected_excess_return": 0.009,
                    },
                ]
            },
            "positive_alpha_proportional_top_decile": {
                "positions": [
                    {
                        "symbol": "S0",
                        "isin": "INE000000000",
                        "weight": 0.4,
                        "expected_excess_return": 0.01,
                    },
                    {
                        "symbol": "S1",
                        "isin": "INE000000001",
                        "weight": 0.6,
                        "expected_excess_return": 0.009,
                    },
                ]
            },
            "full_po001_observable_cost_floor": {
                "holding_count": 2,
                "optimizer_artifact_sha256": "x" * 64,
            },
        },
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def test_p001_uses_only_exact_preserved_i002_position_vectors():
    report = run_rm001_v2_p001(
        v1_risk_state=_risk_state(v2=False),
        v2_risk_state=_risk_state(v2=True),
        sealed_i002_artifact=_sealed_i002(),
    )
    assert report["schema_version"] == 2
    attribution = report["sealed_i002_preserved_portfolio_risk"]
    assert set(attribution) == {
        "equal_weight_top_decile",
        "positive_alpha_proportional_top_decile",
    }
    assert attribution["equal_weight_top_decile"]["position_count"] == 2
    assert "SIZE" in attribution["equal_weight_top_decile"]["v2"][
        "portfolio_factor_exposures"
    ]
    assert report["control_resolution"]["unavailable_control"] == (
        "full_po001_observable_cost_floor"
    )


def test_p001_refuses_compact_optimizer_summary_as_exact_positions():
    artifact = _sealed_i002()
    with pytest.raises(AlphaContractError, match="positions missing"):
        _control_positions(
            artifact,
            portfolio_key="full_po001_observable_cost_floor",
        )
