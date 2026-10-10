from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_eps_sign_audit import (
    BATCH_PATH,
    COMPARISON_PATH,
    CURRENT_PATH,
    PRIOR_PATH,
    UNIVERSE_PATH,
    audit_sealed_first_cohort,
    build_eps_sign_audit,
)
from marketlab.h021_legacy_adapter import load_h021_capture_compatible


def _source_inputs() -> tuple[dict, dict, dict]:
    u = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    batch = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    prior, _ = load_h021_capture_compatible(PRIOR_PATH, universe=u, batch_spec=batch)
    current, _ = load_h021_capture_compatible(CURRENT_PATH, universe=u, batch_spec=batch)
    comparison = json.loads(COMPARISON_PATH.read_text(encoding="utf-8"))
    return comparison, prior, current


def test_first_cohort_reproduces_all_97_eligible_eps_without_outcomes() -> None:
    result = audit_sealed_first_cohort()
    source = json.loads(COMPARISON_PATH.read_text(encoding="utf-8"))
    assert result["eligible_eps_observations"] == 97
    assert len(result["ineligible_rows_retained"]) == 3
    assert result["original_top_decile_symbols_unchanged"] == source[
        "primary_top_decile_symbols"
    ]
    assert sum(
        row["selected_by_original_h021_top_decile"] for row in result["audited_rows"]
    ) == 10
    assert result["direction_inversion_count"] == sum(
        row["ratio_direction_inverted_vs_absolute_eps_change"]
        for row in result["audited_rows"]
    )
    assert result["direction_inversion_top_decile_count"] == len(
        result["top_decile_inverted_symbols"]
    )
    for row in result["audited_rows"]:
        assert row["return_outcomes_opened"] is False
        if row["absolute_eps_change"] != 0 and row["prior_eps"] < 0:
            assert row["ratio_revision_direction"] != row["absolute_eps_change_direction"]
            assert row["ratio_direction_inverted_vs_absolute_eps_change"] is True
        elif row["absolute_eps_change"] != 0:
            assert row["ratio_revision_direction"] == row["absolute_eps_change_direction"]
            assert row["ratio_direction_inverted_vs_absolute_eps_change"] is False
    assert result["h021_primary_selection_revised"] is False
    assert result["entry_intents_revised"] is False
    assert result["return_outcomes_opened"] is False
    assert result["live_capital_allowed"] is False
    assert result["portfolio_eligibility_allowed"] is False


@pytest.mark.parametrize("prior_eps,current_eps,ratio_pct,delta", [
    (-2.0, -1.0, -50.0, 1.0),  # Improving loss perversely ranks negative
    (-2.0, -3.0, 50.0, -1.0),  # Worsening loss perversely ranks positive
    (-1.0, 1.0, -200.0, 2.0),  # Crossing loss to profit flips ratio
])
def test_negative_prior_eps_inverts_direction_without_changing_frozen_selection(
    prior_eps: float, current_eps: float, ratio_pct: float, delta: float
) -> None:
    comparison, prior, current = _source_inputs()
    ticker = comparison["primary_top_decile_symbols"][0]
    previous = next(x for x in prior["observations"] if x["symbol"] == ticker)
    now = next(x for x in current["observations"] if x["symbol"] == ticker)
    comp_row = next(x for x in comparison["revision_observations"] if x["symbol"] == ticker)
    previous["consensus_eps"] = prior_eps
    now["consensus_eps"] = current_eps
    comp_row["eps_revision_pct"] = ratio_pct

    result = build_eps_sign_audit(comparison, prior, current)
    matched = next(x for x in result["audited_rows"] if x["symbol"] == ticker)
    assert matched["absolute_eps_change"] == delta
    assert matched["original_ratio_revision_pct"] == ratio_pct
    assert matched["ratio_direction_inverted_vs_absolute_eps_change"] is True
    assert matched["selected_by_original_h021_top_decile"] is True
    assert result["h021_primary_selection_revised"] is False


def test_positive_prior_eps_preserves_economic_direction() -> None:
    comparison, prior, current = _source_inputs()
    symbol = comparison["primary_top_decile_symbols"][0]
    before = next(x for x in prior["observations"] if x["symbol"] == symbol)
    after = next(x for x in current["observations"] if x["symbol"] == symbol)
    comp = next(x for x in comparison["revision_observations"] if x["symbol"] == symbol)
    before["consensus_eps"], after["consensus_eps"], comp["eps_revision_pct"] = (
        2.0, 3.0, 50.0
    )
    result = build_eps_sign_audit(comparison, prior, current)
    selected = next(x for x in result["audited_rows"] if x["symbol"] == symbol)
    assert selected["ratio_direction_inverted_vs_absolute_eps_change"] is False
    assert selected["absolute_eps_change"] == 1.0


def test_tampered_source_eps_ratio_cannot_pass_as_original_primary() -> None:
    comp, prior, current = _source_inputs()
    symbol = comp["primary_top_decile_symbols"][0]
    changed = next(x for x in current["observations"] if x["symbol"] == symbol)
    changed["consensus_eps"] = 1234.56
    with pytest.raises(ValueError, match="does not reproduce"):
        build_eps_sign_audit(comp, prior, current)


def test_mismatched_analyst_identity_rejected() -> None:
    comp, prior, current = _source_inputs()
    symbol = comp["primary_top_decile_symbols"][0]
    before = next(x for x in prior["observations"] if x["symbol"] == symbol)
    before["analyst_count"] = 900
    with pytest.raises(ValueError, match="analyst-panel identity"):
        build_eps_sign_audit(comp, prior, current)


def test_original_sources_never_mutated_by_audit() -> None:
    comp, prior, current = _source_inputs()
    originals = deepcopy((comp, prior, current))
    build_eps_sign_audit(comp, prior, current)
    assert (comp, prior, current) == originals


def test_cli_emits_reproducible_source_sha_and_no_price_fields(tmp_path: Path) -> None:
    out = tmp_path / "sign-audit.json"
    completed = subprocess.run(
        [sys.executable, "scripts/audit_h021_eps_sign.py", "--out", str(out)],
        check=True, capture_output=True, text=True,
    )
    summary = json.loads(completed.stdout)
    audit = json.loads(out.read_text(encoding="utf-8"))
    assert summary["eligible_eps_observations"] == 97
    assert audit["eligible_eps_observations"] == 97
    assert len(audit["source_provenance"]["prior_original_gzip_sha256"]) == 64
    assert len(audit["source_provenance"]["current_original_gzip_sha256"]) == 64
    assert audit["return_outcomes_opened"] is False
    assert "price" not in json.dumps(audit).lower()
    assert "return" in json.dumps(audit).lower()  # Only closed-return flags, never labels


def test_published_negative_eps_evidence_matches_exact_sealed_source() -> None:
    recorded = json.loads(
        Path("research/h021-p007-result-v1.json").read_text(encoding="utf-8")
    )
    live = audit_sealed_first_cohort()
    assert recorded["eligible_eps_observations"] == live["eligible_eps_observations"]
    assert recorded["direction_inversion_count"] == live["direction_inversion_count"]
    assert recorded["prior_eps_negative_count"] == live["prior_eps_negative_count"]
    assert recorded["direction_inversion_top_decile_count"] == live[
        "direction_inversion_top_decile_count"
    ]
    assert recorded["original_top_decile_inverted_symbols"] == live[
        "top_decile_inverted_symbols"
    ]
    negatives = {r["symbol"]: r for r in live["audited_rows"] if r["negative_prior_eps"]}
    assert set(negatives) == {r["symbol"] for r in recorded["negative_prior_eps_cases"]}
    for case in recorded["negative_prior_eps_cases"]:
        row = negatives[case["symbol"]]
        assert case["prior_eps"] == pytest.approx(row["prior_eps"])
        assert case["current_eps"] == pytest.approx(row["current_eps"])
        assert case["original_ratio_revision_pct"] == pytest.approx(
            row["original_ratio_revision_pct"]
        )
        assert case["absolute_eps_change"] == pytest.approx(row["absolute_eps_change"])
        assert case["in_original_primary_top_decile"] == row[
            "selected_by_original_h021_top_decile"
        ]
        if case["economic_direction"] == "LOSS_IMPROVING":
            assert row["absolute_eps_change"] > 0
        else:
            assert case["economic_direction"] == "LOSS_WORSENING"
            assert row["absolute_eps_change"] < 0
    assert recorded["return_outcomes_opened"] is False
    assert recorded["live_capital_allowed"] is False
