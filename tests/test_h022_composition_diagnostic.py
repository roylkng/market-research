from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab import h022_composition_diagnostic as diagnostic


def _hashed(payload: dict[str, object], field: str) -> dict[str, object]:
    result = deepcopy(payload)
    result[field] = diagnostic._canonical_hash(result)
    return result


def test_composition_classification_is_sign_based() -> None:
    assert diagnostic._composition_classification(1.0, 2.0) == "BROAD_POSITIVE"
    assert diagnostic._composition_classification(-0.1, 2.0) == "CURRENT_U001_CONCENTRATED"
    assert diagnostic._composition_classification(1.0, 0.0) == "ADDITIONAL_CONCENTRATED"
    assert diagnostic._composition_classification(0.0, -0.1) == "BROAD_NONPOSITIVE"


def test_industry_classification_locks_coverage_and_breadth_gates() -> None:
    assert (
        diagnostic._industry_classification(
            coverage_share=0.89,
            eligible_count=500,
            coefficient=2.0,
            ci_low=1.0,
            leave_one_out_min=1.0,
        )
        == "DATA_INSUFFICIENT"
    )
    assert (
        diagnostic._industry_classification(
            coverage_share=0.95,
            eligible_count=500,
            coefficient=2.0,
            ci_low=0.1,
            leave_one_out_min=0.2,
        )
        == "SUPPORTIVE_BREADTH"
    )
    assert (
        diagnostic._industry_classification(
            coverage_share=0.95,
            eligible_count=500,
            coefficient=2.0,
            ci_low=-0.1,
            leave_one_out_min=0.2,
        )
        == "PARTIAL_BREADTH"
    )
    assert (
        diagnostic._industry_classification(
            coverage_share=0.95,
            eligible_count=500,
            coefficient=2.0,
            ci_low=0.1,
            leave_one_out_min=-0.2,
        )
        == "SECTOR_SENSITIVE"
    )
    assert (
        diagnostic._industry_classification(
            coverage_share=0.95,
            eligible_count=500,
            coefficient=0.0,
            ci_low=-1.0,
            leave_one_out_min=-1.0,
        )
        == "NOT_ESTABLISHED"
    )


def test_composition_regression_recovers_group_specific_positive_slopes() -> None:
    rows = []
    for index, signal in enumerate((-2.0, -1.0, 1.0, 2.0)):
        rows.append(
            {
                "source_id": f"a{index}",
                "symbol": f"A{index}",
                "h022_signal": signal,
                "future_60d_excess_pp": 2.0 * signal,
                "composition_group": "ADDITIONAL_HISTORICAL_NIFTY200",
                "industry": "A",
            }
        )
        rows.append(
            {
                "source_id": f"c{index}",
                "symbol": f"C{index}",
                "h022_signal": signal,
                "future_60d_excess_pp": 4.0 * signal,
                "composition_group": "CURRENT_U001",
                "industry": "B",
            }
        )
    additional, current, interaction = diagnostic._composition_coefficients(rows)
    assert additional > 0
    assert current > additional
    assert interaction > 0


def test_industry_fixed_effect_coefficient_uses_within_industry_signal() -> None:
    rows = []
    for industry, level in (("A", 10.0), ("B", -10.0)):
        for index, signal in enumerate((-2.0, -1.0, 1.0, 2.0)):
            rows.append(
                {
                    "source_id": f"{industry}{index}",
                    "symbol": f"{industry}{index}",
                    "h022_signal": signal,
                    "future_60d_excess_pp": level + 3.0 * signal,
                    "composition_group": "CURRENT_U001",
                    "industry": industry,
                }
            )
    assert diagnostic._industry_fixed_effect_coefficient(rows) > 0


def test_build_panel_preserves_missing_industry_without_backfill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = {
        "schema_version": 1,
        "hypothesis_id": "H022",
        "execution_rule_id": "H022-X001",
        "records": [
            {
                "source_id": "s1",
                "symbol": "AAA",
                "primary_signal": 1.5,
                "horizons": {"60": {"status": "COMPLETE", "gross_excess_pp": 3.0}},
            },
            {
                "source_id": "s2",
                "symbol": "BBB",
                "primary_signal": -0.5,
                "horizons": {"60": {"status": "COMPLETE", "gross_excess_pp": -1.0}},
            },
        ],
    }
    outcome = _hashed(outcome, "report_sha256")
    reconstruction = {
        "schema_version": 1,
        "hypothesis_id": "H022",
        "expanded_union_members": [
            {"symbol": "AAA", "industry": "Industrials"},
            {"symbol": "BBB", "industry": None},
        ],
    }
    reconstruction = _hashed(reconstruction, "reconstruction_sha256")
    u001 = {
        "cohort_id": "test-u001",
        "captured_at_utc": "2026-09-06T00:00:00Z",
        "members": [{"symbol": "AAA"}],
    }

    monkeypatch.setattr(diagnostic, "OUTCOME_REPORT_SHA256", outcome["report_sha256"])
    monkeypatch.setattr(
        diagnostic,
        "RECONSTRUCTION_SHA256",
        reconstruction["reconstruction_sha256"],
    )
    monkeypatch.setattr(diagnostic, "U001_COHORT_ID", "test-u001")
    monkeypatch.setattr(diagnostic, "U001_CAPTURED_AT_UTC", "2026-09-06T00:00:00Z")
    monkeypatch.setattr(diagnostic, "U001_MEMBER_COUNT", 1)
    monkeypatch.setattr(diagnostic, "EXPECTED_COMPLETE_PRIMARY", 2)

    panel = diagnostic.build_diagnostic_panel(outcome, reconstruction, u001)
    by_symbol = {row["symbol"]: row for row in panel["records"]}
    assert by_symbol["AAA"]["composition_group"] == "CURRENT_U001"
    assert by_symbol["AAA"]["industry"] == "Industrials"
    assert by_symbol["BBB"]["composition_group"] == "ADDITIONAL_HISTORICAL_NIFTY200"
    assert by_symbol["BBB"]["industry"] is None
