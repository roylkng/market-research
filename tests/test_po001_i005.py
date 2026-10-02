import copy

import pytest

from marketlab.alpha import digest
from marketlab.po001_i005 import (
    _evaluate_under_risk,
    run_po001_i005,
)


def _risk(model_id, factors):
    rows = [
        {
            "symbol": "A",
            "isin": "INE000000001",
            "exposures": {
                factor: (
                    1.0
                    if factor == "MARKET_COMMON"
                    else (0.2 if index == 0 else -0.2)
                )
                for factor in factors
            },
            "idiosyncratic_variance_daily": 0.00001,
            "idiosyncratic_status": "OBSERVED",
        }
        for index in range(1)
    ]
    rows.append(
        {
            "symbol": "B",
            "isin": "INE000000002",
            "exposures": {
                factor: (
                    1.0
                    if factor == "MARKET_COMMON"
                    else -0.2
                )
                for factor in factors
            },
            "idiosyncratic_variance_daily": 0.00002,
            "idiosyncratic_status": "OBSERVED",
        }
    )
    covariance = [
        [
            0.0001 if i == j else 0.0
            for j in range(len(factors))
        ]
        for i in range(len(factors))
    ]
    state = {
        "schema_version": 1,
        "model_id": model_id,
        "as_of_session": "2026-08-31",
        "factor_names": factors,
        "factor_covariance_daily": covariance,
        "rows": rows,
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _optimizer_artifact(weights, *, artifact_id):
    rows = []
    for symbol, isin, weight in (
        ("A", "INE000000001", weights[0]),
        ("B", "INE000000002", weights[1]),
    ):
        rows.append(
            {
                "symbol": symbol,
                "isin": isin,
                "expected_excess_return": 0.01,
                "current_weight": 0.0,
                "max_weight": 1.0,
                "buy_cost_bps": 10.0,
                "sell_cost_bps": 12.0,
                "adv20_inr": 100_000_000.0,
                "daily_volatility_decimal": 0.02,
                "effective_max_weight": 1.0,
                "target_weight": weight,
            }
        )
    artifact = {
        "schema_version": 1,
        "optimizer_id": "PO001-v4-DEVELOPMENT",
        "rows": rows,
        "expected_excess_return": 0.01,
        "total_transaction_cost_fraction": 0.001,
        "artifact_label": artifact_id,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def _s001_report(control, treatment, control_risk, treatment_risk):
    report = {
        "schema_version": 1,
        "study_id": "PO001-S001-v1",
        "realized_outcome_opened": False,
        "alpha_model_sha256": "m" * 64,
        "control_risk_state_sha256": control_risk["state_sha256"],
        "treatment_risk_state_sha256": treatment_risk["state_sha256"],
        "common_identity_count": 2,
        "execution_contract": {},
        "control_rm001_v1": {"artifact": control},
        "treatment_rm001_v3": {"artifact": treatment},
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def test_i005_cross_risk_evaluation_uses_common_risk_map():
    risk = _risk("RM001-v1-DEVELOPMENT", ["MARKET_COMMON"])
    artifact = _optimizer_artifact((0.6, 0.4), artifact_id="x")
    observed = _evaluate_under_risk(
        artifact,
        risk_state=risk,
        identities=[
            ("A", "INE000000001"),
            ("B", "INE000000002"),
        ],
        factor_names=("MARKET_COMMON",),
    )
    expected_factor = 0.0001
    expected_idio = 0.6**2 * 0.00001 + 0.4**2 * 0.00002
    assert observed["factor_variance_daily"] == pytest.approx(
        expected_factor
    )
    assert observed["idiosyncratic_variance_daily"] == pytest.approx(
        expected_idio
    )
    assert observed["total_variance_daily"] == pytest.approx(
        expected_factor + expected_idio
    )


def test_i005_material_classification_is_frozen_before_inspection(monkeypatch):
    control_risk = _risk("RM001-v1-DEVELOPMENT", ["MARKET_COMMON"])
    treatment_risk = _risk(
        "RM001-v3-DEVELOPMENT",
        ["MARKET_COMMON", "SIZE"],
    )
    control = _optimizer_artifact((0.60, 0.40), artifact_id="control")
    treatment = _optimizer_artifact((0.55, 0.45), artifact_id="treatment")
    report = _s001_report(
        control,
        treatment,
        control_risk,
        treatment_risk,
    )

    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_S001_REPORT_SHA256",
        report["report_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_CONTROL_ARTIFACT_SHA256",
        control["artifact_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_TREATMENT_ARTIFACT_SHA256",
        treatment["artifact_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_CONTROL_RISK_SHA256",
        control_risk["state_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_TREATMENT_RISK_SHA256",
        treatment_risk["state_sha256"],
    )

    def fake_eval(artifact, *, risk_state, identities, factor_names):
        is_treatment = artifact["artifact_label"] == "treatment"
        is_v3 = risk_state["model_id"] == "RM001-v3-DEVELOPMENT"
        if is_v3:
            utility = 0.006 if is_treatment else 0.005
        else:
            utility = 0.006 if not is_treatment else 0.005
        return {
            "factor_names": list(factor_names),
            "factor_variance_daily": 0.0001,
            "idiosyncratic_variance_daily": 0.00002,
            "total_variance_daily": 0.00012,
            "annualized_volatility": 0.17,
            "risk_penalty": 0.003,
            "expected_5d_excess_return": 0.01,
            "total_transaction_cost_fraction": 0.001,
            "utility": utility,
            "portfolio_factor_exposures": {},
        }

    monkeypatch.setattr(
        "marketlab.po001_i005._evaluate_under_risk",
        fake_eval,
    )
    result = run_po001_i005(
        s001_report=report,
        control_risk_state=control_risk,
        treatment_risk_state=treatment_risk,
    )
    assert result["status"] == "MATERIAL_RISK_MODEL_PORTFOLIO_EFFECT"
    assert result["materiality_flags"]["reallocation_material"] is True
    assert result["weight_changes"]["weight_l1_change"] == pytest.approx(
        0.10
    )
    assert result["rm001_v1_common_map"][
        "control_optimality_sanity_passed"
    ] is True
    assert result["rm001_v3_common_map"][
        "treatment_optimality_sanity_passed"
    ] is True


def test_i005_sanity_failure_overrides_materiality(monkeypatch):
    control_risk = _risk("RM001-v1-DEVELOPMENT", ["MARKET_COMMON"])
    treatment_risk = _risk(
        "RM001-v3-DEVELOPMENT",
        ["MARKET_COMMON", "SIZE"],
    )
    control = _optimizer_artifact((0.60, 0.40), artifact_id="control")
    treatment = _optimizer_artifact((0.55, 0.45), artifact_id="treatment")
    report = _s001_report(
        control,
        treatment,
        control_risk,
        treatment_risk,
    )
    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_S001_REPORT_SHA256",
        report["report_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_CONTROL_ARTIFACT_SHA256",
        control["artifact_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_TREATMENT_ARTIFACT_SHA256",
        treatment["artifact_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_CONTROL_RISK_SHA256",
        control_risk["state_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i005.EXPECTED_TREATMENT_RISK_SHA256",
        treatment_risk["state_sha256"],
    )

    def bad_eval(artifact, *, risk_state, identities, factor_names):
        # Treatment is incorrectly better under v1 and worse under v3.
        is_treatment = artifact["artifact_label"] == "treatment"
        is_v3 = risk_state["model_id"] == "RM001-v3-DEVELOPMENT"
        utility = (
            0.004
            if (is_v3 and is_treatment)
            else 0.006
            if (is_v3 and not is_treatment)
            else 0.007
            if is_treatment
            else 0.005
        )
        return {
            "factor_names": list(factor_names),
            "factor_variance_daily": 0.0001,
            "idiosyncratic_variance_daily": 0.00002,
            "total_variance_daily": 0.00012,
            "annualized_volatility": 0.17,
            "risk_penalty": 0.003,
            "expected_5d_excess_return": 0.01,
            "total_transaction_cost_fraction": 0.001,
            "utility": utility,
            "portfolio_factor_exposures": {},
        }

    monkeypatch.setattr(
        "marketlab.po001_i005._evaluate_under_risk",
        bad_eval,
    )
    result = run_po001_i005(
        s001_report=report,
        control_risk_state=control_risk,
        treatment_risk_state=treatment_risk,
    )
    assert result["status"] == "IMPLEMENTATION_SANITY_CHECK_FAILED"
