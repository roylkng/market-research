import pytest

from marketlab.alpha import AlphaContractError
from marketlab.rta001 import (
    benjamini_hochberg,
    benjamini_yekutieli,
    bonferroni,
    build_rta001_summary,
    holm,
)


def test_adjustments_match_known_small_family():
    rows = [
        ("A", 0.01),
        ("B", 0.04),
        ("C", 0.20),
        ("D", 1.0),
    ]
    bh = benjamini_hochberg(rows)
    by = benjamini_yekutieli(rows)
    holm_values = holm(rows)
    bonf = bonferroni(rows)

    assert bh["A"] == pytest.approx(0.04)
    assert bh["B"] == pytest.approx(0.08)
    assert bh["C"] == pytest.approx(0.26666666666666666)
    assert bh["D"] == pytest.approx(1.0)
    assert by["A"] >= bh["A"]
    assert holm_values["A"] == pytest.approx(0.04)
    assert bonf["A"] == pytest.approx(0.04)


def _manifest():
    return {
        "schema_version": 1,
        "accounting_id": "RTA001-v1",
        "as_of_date": "2026-10-03",
        "live_capital_allowed": False,
        "fdr_families": {
            "F1": {"alpha": 0.05},
        },
        "trials": [
            {
                "trial_id": "T1",
                "category": "ALPHA_FEATURE_DISCOVERY",
                "registration_mode": "PRE_REGISTERED_BEFORE_OUTCOMES",
                "result_state": "COMPLETE",
                "reported_primary_supported": True,
                "nominal_primary_p_value": 0.01,
                "fdr_accounting_p_value": 0.01,
                "p_value_status": "SCALAR",
                "fdr_family": "F1",
            },
            {
                "trial_id": "T2",
                "category": "ALPHA_FEATURE_DISCOVERY",
                "registration_mode": "RETROSPECTIVE_ACCOUNTING_BACKFILL",
                "result_state": "COMPLETE",
                "reported_primary_supported": False,
                "nominal_primary_p_value": None,
                "fdr_accounting_p_value": 1.0,
                "p_value_status": "CONSERVATIVE",
                "fdr_family": "F1",
            },
            {
                "trial_id": "T3",
                "category": "ALPHA_FEATURE_DISCOVERY",
                "registration_mode": "PROSPECTIVE_PRE_REGISTERED",
                "result_state": "PENDING_PROSPECTIVE",
                "reported_primary_supported": None,
                "nominal_primary_p_value": None,
                "fdr_accounting_p_value": None,
                "p_value_status": "PENDING",
                "fdr_family": "F1",
            },
        ],
        "source_feasibility_results": ["research/source-result.json"],
    }


def test_summary_keeps_pending_out_of_current_adjustment():
    summary = build_rta001_summary(_manifest())
    family = summary["fdr_families"]["F1"]["inclusive"]
    assert family["registered_trial_count"] == 3
    assert family["completed_adjusted_trial_count"] == 2
    assert family["pending_or_unadjusted_trial_count"] == 1
    assert family["records"][0]["trial_id"] == "T1"
    assert family["records"][0]["bh_q_value"] == pytest.approx(0.02)


def test_preregistered_sensitivity_excludes_retrospective_seed():
    summary = build_rta001_summary(_manifest())
    family = summary["fdr_families"]["F1"][
        "preregistered_only_sensitivity"
    ]
    assert family["completed_adjusted_trial_count"] == 1
    assert family["records"][0]["bh_q_value"] == pytest.approx(0.01)


def test_duplicate_trial_ids_fail_closed():
    manifest = _manifest()
    manifest["trials"].append(dict(manifest["trials"][0]))
    with pytest.raises(AlphaContractError, match="unique"):
        build_rta001_summary(manifest)
