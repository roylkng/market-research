import copy

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.po001_i004 import (
    CONTROL_SCALAR_TOLERANCE,
    FROZEN_CONTROL,
    _validate_control_reproduction,
    run_po001_i004,
)


def _risk(model_id: str, sha: str, factor_names: list[str]):
    rows = [
        {
            "symbol": f"S{index:03d}",
            "isin": f"INE{index:09d}",
            "exposures": {
                factor: (
                    1.0 if factor == "MARKET_COMMON" else 0.01 * index
                )
                for factor in factor_names
            },
            "idiosyncratic_variance_daily": 0.0001,
            "idiosyncratic_status": "OBSERVED",
        }
        for index in range(500)
    ]
    state = {
        "schema_version": 1,
        "model_id": model_id,
        "as_of_session": "2026-08-31",
        "factor_names": factor_names,
        "factor_covariance_daily": [
            [
                0.00001 if i == j else 0.0
                for j in range(len(factor_names))
            ]
            for i in range(len(factor_names))
        ],
        "rows": rows,
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _feature_panel():
    rows = [
        {
            "feature_session": "2026-08-31",
            "symbol": f"S{index:03d}",
            "isin": f"INE{index:09d}",
            "values": {"x": index / 500.0},
        }
        for index in range(500)
    ]
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-I004",
        "transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "rows": rows,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = (
        "47ee538af6cfca16405632ce6396571455a548687b4ceabfd7999040a86f8b44"
    )
    return panel


def _optimizer_artifact(risk_state, *, treatment=False):
    factor_names = list(risk_state["factor_names"])
    holding_count = 48 if treatment else 47
    expected = (
        FROZEN_CONTROL["expected_5d_excess_return"]
        + (0.0002 if treatment else 0.0)
    )
    volatility = (
        FROZEN_CONTROL["annualized_volatility"]
        + (0.005 if treatment else 0.0)
    )
    weights = [1.0 / holding_count] * holding_count
    rows = []
    for index in range(500):
        weight = weights[index] if index < holding_count else 0.0
        rows.append(
            {
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
                "target_weight": weight,
                "expected_excess_return": 0.01,
            }
        )
    total_variance = volatility**2 / 252.0
    artifact = {
        "schema_version": 1,
        "optimizer_id": "PO001-v3-DEVELOPMENT",
        "factor_names": factor_names,
        "rows": rows,
        "invested_weight": 1.0,
        "cash_weight": 0.0,
        "expected_excess_return": expected,
        "factor_variance_daily": total_variance * 0.6,
        "idiosyncratic_variance_daily": total_variance * 0.4,
        "total_variance_daily": total_variance,
        "risk_penalty": 0.001,
        "immediate_observable_cost_fraction": 0.001,
        "immediate_impact_cost_fraction": (
            FROZEN_CONTROL["immediate_impact_cost_fraction"]
        ),
        "terminal_observable_cost_fraction": 0.001,
        "terminal_impact_cost_fraction": (
            FROZEN_CONTROL["terminal_impact_cost_fraction"]
        ),
        "total_transaction_cost_fraction": (
            FROZEN_CONTROL["total_transaction_cost_fraction"]
        ),
        "maximum_observed_participation": (
            FROZEN_CONTROL["maximum_observed_participation"]
        ),
        "objective_utility": (
            FROZEN_CONTROL["objective_utility"]
            + (0.0001 if treatment else 0.0)
        ),
        "portfolio_factor_exposures": {
            factor: 0.1 for factor in factor_names
        },
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def test_i004_changes_only_risk_state(monkeypatch):
    control = _risk(
        "RM001-v1-DEVELOPMENT",
        "unused",
        [
            "MARKET_COMMON",
            "BETA60_RELATIVE",
            "MOMENTUM20",
            "VOLATILITY60",
            "LIQUIDITY",
        ],
    )
    treatment = _risk(
        "RM001-v3-DEVELOPMENT",
        "unused",
        [
            "MARKET_COMMON",
            "BETA60_RELATIVE",
            "MOMENTUM20",
            "VOLATILITY60",
            "LIQUIDITY",
            "SIZE",
            "STAT_PC01",
            "STAT_PC02",
            "STAT_PC03",
            "STAT_PC04",
            "STAT_PC05",
        ],
    )
    monkeypatch.setattr(
        "marketlab.po001_i004.EXPECTED_CONTROL_RISK_SHA256",
        control["state_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i004.EXPECTED_TREATMENT_RISK_SHA256",
        treatment["state_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i004._validate_pinned_alpha_model",
        lambda model: None,
    )
    monkeypatch.setattr(
        "marketlab.po001_i004.FROZEN_COMMON_IDENTITY_COUNT",
        500,
    )
    monkeypatch.setattr(
        "marketlab.po001_i004._validate_i004_feature_panel",
        lambda panel: {
            "economic_equivalence_passed": True,
            "row_projection_sha256": "r" * 64,
        },
    )
    monkeypatch.setattr(
        "marketlab.po001_i004._score_model",
        lambda model, rows: [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "prediction": 0.01 + index * 1e-6,
            }
            for index, row in enumerate(rows)
        ],
    )
    monkeypatch.setattr(
        "marketlab.po001_i004._execution_inputs",
        lambda **kwargs: {
            (f"S{index:03d}", f"INE{index:09d}"): {
                "adv20_inr": 100_000_000.0,
                "daily_volatility_decimal": 0.02,
            }
            for index in range(500)
        },
    )
    monkeypatch.setattr(
        "marketlab.po001_i004.observable_side_cost",
        lambda **kwargs: {"total_bps": 10.0},
    )

    calls = []

    def fake_optimize(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        is_treatment = kwargs["risk_state"]["model_id"] == "RM001-v3-DEVELOPMENT"
        return _optimizer_artifact(
            kwargs["risk_state"],
            treatment=is_treatment,
        )

    monkeypatch.setattr(
        "marketlab.po001_i004.optimize_portfolio_v3",
        fake_optimize,
    )

    artifact = run_po001_i004(
        delivery_feature_panel=_feature_panel(),
        market_panel={"sessions": []},
        pinned_alpha_model={"model_sha256": "m" * 64},
        control_risk_state=control,
        treatment_risk_state=treatment,
    )

    assert len(calls) == 2
    left = {k: v for k, v in calls[0].items() if k != "risk_state"}
    right = {k: v for k, v in calls[1].items() if k != "risk_state"}
    assert left == right
    assert artifact["control_reproduction_passed"] is True
    assert artifact["treatment_minus_control"]["holding_count"] == 1
    assert artifact["interpretation_limits"]["only_changed_input"] == "RISK_STATE"
    assert artifact["realized_outcome_opened"] is False


def test_i004_control_gate_fails_on_scalar_drift():
    summary = {
        **FROZEN_CONTROL,
        "expected_5d_excess_return": (
            FROZEN_CONTROL["expected_5d_excess_return"]
            + 2.0 * CONTROL_SCALAR_TOLERANCE
        ),
    }
    with pytest.raises(AlphaContractError, match="expected_5d_excess_return"):
        _validate_control_reproduction(summary)
