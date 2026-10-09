from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_composition import AUDIT_ID, build_analyst_composition_audit

COMPARISON_PATH = Path(
    "research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json"
)


def _comparison() -> dict:
    return json.loads(COMPARISON_PATH.read_text(encoding="utf-8"))


def test_october_9_immutable_composition_and_frozen_primary_cohort() -> None:
    original = _comparison()
    input_copy = deepcopy(original)
    result = build_analyst_composition_audit(original)

    assert original == input_copy
    assert result["audit_id"] == AUDIT_ID
    assert result["total_symbol_count"] == 100
    assert result["primary_signal_available_count"] == 97
    assert result["primary_top_decile_symbols_unchanged"] == original[
        "primary_top_decile_symbols"
    ]
    assert result["eligible_panel"] == {
        "count": 97,
        "decreased": 44,
        "unchanged": 42,
        "increased": 11,
        "unavailable": 0,
        "decline_at_least_30pct": 11,
        "decline_at_least_50pct": 4,
    }
    assert result["primary_top_decile_panel"] == {
        "count": 10,
        "decreased": 5,
        "unchanged": 5,
        "increased": 0,
        "unavailable": 0,
        "decline_at_least_30pct": 2,
        "decline_at_least_50pct": 1,
    }

    indexed = {row["symbol"]: row for row in result["observations"]}
    assert list(indexed) == sorted(indexed)
    assert indexed["DMART"]["analyst_count_prior"] == 31
    assert indexed["DMART"]["analyst_count_current"] == 12
    assert indexed["DMART"]["analyst_count_delta"] == -19
    assert indexed["DMART"]["analyst_count_change_ratio"] == pytest.approx(-19 / 31)
    assert indexed["DMART"]["primary_top_decile"] is True
    assert indexed["GAIL"]["analyst_count_delta"] == -12
    assert result["coverage_churn_changes_primary_rank_or_selection"] is False
    assert result["contains_return_or_price_outcomes"] is False
    assert result["promotes_research_or_portfolio_gate"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False


@pytest.mark.parametrize("flag,value", [
    ("outcomes_opened", True),
    ("live_capital_allowed", True),
    ("schema_version", 2),
    ("hypothesis_id", "H999"),
    ("primary_signal", "alternate momentum signal"),
])
def test_rejects_unfrozen_or_outcome_bearing_input(flag: str, value: object) -> None:
    comparison = _comparison()
    comparison[flag] = value
    with pytest.raises(ValueError):
        build_analyst_composition_audit(comparison)


def test_rejects_missing_and_ineligible_decile_names() -> None:
    comparison = _comparison()
    comparison["primary_top_decile_symbols"][0] = "NO_SUCH_SYMBOL"
    with pytest.raises(ValueError, match="missing"):
        build_analyst_composition_audit(comparison)

    comparison = _comparison()
    comparison["primary_top_decile_symbols"][0] = "TRENT"
    with pytest.raises(ValueError, match="ineligible"):
        build_analyst_composition_audit(comparison)


def test_rejects_duplicate_symbols_and_modified_eligibility_count() -> None:
    comparison = _comparison()
    comparison["revision_observations"][1]["symbol"] = comparison[
        "revision_observations"
    ][0]["symbol"]
    with pytest.raises(ValueError, match="duplicate"):
        build_analyst_composition_audit(comparison)

    comparison = _comparison()
    comparison["primary_signal_available_count"] = 96
    with pytest.raises(ValueError, match="available count"):
        build_analyst_composition_audit(comparison)


@pytest.mark.parametrize("invalid_count", [False, 9.5, -1, "12"])
def test_rejects_invalid_analyst_count(invalid_count: object) -> None:
    comparison = _comparison()
    comparison["revision_observations"][0]["analyst_count_prior"] = invalid_count
    with pytest.raises(ValueError, match="invalid analyst count"):
        build_analyst_composition_audit(comparison)


def test_cli_emits_reproducible_hashed_provenance(tmp_path: Path) -> None:
    output_path = tmp_path / "coverage.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "marketlab.h021_composition",
            str(COMPARISON_PATH),
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(output["comparison_raw_sha256"]) == 64
    assert output["eligible_panel"]["count"] == 97
    assert output["contains_return_or_price_outcomes"] is False
