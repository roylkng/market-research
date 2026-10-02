import copy

from marketlab.po001_s001 import evaluate_po001_s001_reports


def _artifact(*, shift=0.0):
    rows = [
        {
            "symbol": "A",
            "isin": "INE000000001",
            "target_weight": 0.6 + shift,
        },
        {
            "symbol": "B",
            "isin": "INE000000002",
            "target_weight": 0.4 - shift,
        },
    ]
    return {
        "artifact_sha256": "a" * 64,
        "rows": rows,
        "expected_excess_return": 0.01,
        "total_variance_daily": 0.0001,
        "risk_penalty": 0.002,
        "total_transaction_cost_fraction": 0.001,
        "objective_utility": 0.007,
        "solver": {
            "kkt": {
                "maximum_coordinate_kkt_violation": 1e-12,
            }
        },
    }


def _report(*, shift=0.0):
    control = _artifact(shift=shift)
    treatment = _artifact(shift=shift)
    return {
        "study_id": "PO001-S001-v1",
        "realized_outcome_opened": False,
        "alpha_model_sha256": "m" * 64,
        "control_risk_state_sha256": "c" * 64,
        "treatment_risk_state_sha256": "t" * 64,
        "common_identity_count": 2,
        "execution_contract": {"x": 1},
        "report_sha256": "r" * 64,
        "control_rm001_v1": {
            "artifact": control,
        },
        "treatment_rm001_v3": {
            "artifact": treatment,
        },
    }


def test_s001_evaluator_passes_identical_replicas():
    reports = [_report(), _report(), _report()]
    result = evaluate_po001_s001_reports(reports)
    assert result["status"] == "NUMERICAL_STABILITY_ESTABLISHED"
    assert result["control_rm001_v1"]["weight_stability_passed"] is True
    assert result["treatment_rm001_v3"]["kkt_passed"] is True
    assert result["promotion"]["rm001_v3_portfolio_revisit_allowed"] is True


def test_s001_evaluator_fails_weight_instability():
    reports = [_report(), _report(), _report(shift=2e-6)]
    result = evaluate_po001_s001_reports(reports)
    assert result["status"] == "PO001_V4_NUMERICAL_STABILITY_NOT_ESTABLISHED"
    assert result["control_rm001_v1"]["weight_stability_passed"] is False
    assert result["promotion"]["rm001_v3_portfolio_revisit_allowed"] is False


def test_s001_evaluator_fails_scalar_instability():
    reports = [_report(), _report(), _report()]
    reports[2] = copy.deepcopy(reports[2])
    reports[2]["treatment_rm001_v3"]["artifact"][
        "objective_utility"
    ] += 1e-6
    result = evaluate_po001_s001_reports(reports)
    assert result["treatment_rm001_v3"][
        "economic_scalar_stability_passed"
    ] is False
    assert result["status"] == "PO001_V4_NUMERICAL_STABILITY_NOT_ESTABLISHED"
