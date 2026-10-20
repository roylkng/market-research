"""HG009 P030 blocks false preentry industry features in the 300-stock study."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import load_hg009_inputs
from marketlab.hg009_p030_sector_queue import (
    _load_pinned,
    build_sector_audit,
    materialize_sector_audit,
    validate_sector_audit,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/hg009/hg009-p030-sector-proof-queue-v1.json"


def _source_inputs() -> dict:
    original, selected = load_hg009_inputs(ROOT)
    controls = json.loads((
        ROOT / "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
    ).read_text(encoding="utf-8"))
    p026, receipt_a = _load_pinned(ROOT, "p026")
    p027, receipt_b = _load_pinned(ROOT, "p027")
    return {
        "original": original,
        "selected": selected,
        "controls": controls,
        "p026": p026,
        "p027": p027,
        "source_receipts": {"p026": receipt_a, "p027": receipt_b},
    }


def test_300_original_research_identities_and_158_unknown_sector_tasks():
    data = materialize_sector_audit(ROOT)
    assert data["original_company_count"] == 300
    assert len(data["future_source_collection_queue"]) == 300
    assert data["original_postentry_index_subset_exact_match_count"] == 142
    assert data["unclassified_in_index_subset_count"] == 158
    assert data["postentry_index_subset_matches_by_arm"] == {
        "SELECTED": 46,
        "ONE_LANE": 43,
        "ZERO_LANE": 53,
    }
    assert data["unclassified_in_index_subset_by_arm"] == {
        "SELECTED": 54,
        "ONE_LANE": 57,
        "ZERO_LANE": 47,
    }
    assert sum(
        x["source_status"] == "POSTENTRY_INDEX_MATCH_FIRST_RETRIEVAL_NOT_VERIFIED"
        for x in data["future_source_collection_queue"]
    ) == 142
    assert sum(
        x["source_status"] == "NO_ORIGINAL_OFFICIAL_INDUSTRY_SOURCE"
        for x in data["future_source_collection_queue"]
    ) == 158
    assert len({
        (x["original_symbol"], x["frozen_isin"])
        for x in data["future_source_collection_queue"]
    }) == 300


def test_forward_cohort_cannot_register_with_postentry_or_unverified_data():
    data = materialize_sector_audit(ROOT)
    assert data["legacy_sector_source_is_post_entry"] is True
    assert data["source_independently_verified_before_legacy_entry_count"] == 0
    assert data["source_retrieval_provenance_verified_count"] == 0
    assert data["minimum_verified_overall_companies_required"] == 285
    assert data["minimum_verified_companies_per_arm"] == 90
    assert data["additional_index_unclassified_companies_needed_for_95pct_if_postentry_matches_independently_attested"] == 143
    assert data["additional_by_arm_if_existing_index_matches_provenanced"] == {
        "SELECTED": 44,
        "ONE_LANE": 47,
        "ZERO_LANE": 37,
    }
    assert data["new_independent_cohort_registered"] is False
    assert data["next_cohort_entry_date"] is None
    assert data["ready_for_next_prospective_trial"] is False
    assert data["live_capital_allowed"] is False
    assert data["no_current_or_future_stock_expected_return_calculated"] is True
    assert all(
        x["verified_before_next_entry"] is False
        and x["sector_and_size_model_eligible"] is False
        and x["source_first_retrieved_at_utc"] is None
        for x in data["future_source_collection_queue"]
    )


def test_source_temporal_contamination_is_detected():
    kwargs = _source_inputs()
    damaged = copy.deepcopy(kwargs["p026"])
    damaged["all_source_identity_rows"][0][
        "sector_known_at_original_oct15_entry"
    ] = True
    with pytest.raises(AlphaContractError, match="after-entry sector"):
        build_sector_audit(**{**kwargs, "p026": damaged})
    damaged = copy.deepcopy(kwargs["p026"])
    damaged["all_source_identity_rows"][1]["symbol"] = "POSTHOC_FUTURE_WINNER"
    with pytest.raises(AlphaContractError, match="arm/ISIN"):
        build_sector_audit(**{**kwargs, "p026": damaged})
    damaged = copy.deepcopy(kwargs["p027"])
    damaged["next_experiment_protocol"]["next_experiment_active"] = True
    with pytest.raises(AlphaContractError, match="original no-alpha"):
        build_sector_audit(**{**kwargs, "p027": damaged})


def test_signed_sources_and_immutable_queue_replay(tmp_path: Path):
    original = materialize_sector_audit(ROOT)
    # During PR CI the bot's generated report may not yet exist in the
    # checkout. Verify the canonical file when present, but exercise the
    # exact generator/check protocol independently in a temporary location.
    if OUT.is_file():
        assert original == json.loads(OUT.read_text(encoding="utf-8"))
    assert original["report_sha256"] == digest({
        k: v for k, v in original.items() if k != "report_sha256"
    })
    validate_sector_audit(original, ROOT)
    corrupt = copy.deepcopy(original)
    corrupt["future_source_collection_queue"][0]["sector_and_size_model_eligible"] = True
    with pytest.raises(AlphaContractError, match="modified after source sealing"):
        validate_sector_audit(corrupt, ROOT)
    generated_path = tmp_path / "sector-proof-queue.json"
    cmd = [
        sys.executable,
        "scripts/materialize_hg009_p030_sector.py",
        "--output", str(generated_path),
    ]
    generated = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(generated.stdout)["state"] == "MATERIALIZED_SOURCE_BLOCKER"
    assert json.loads(generated_path.read_text(encoding="utf-8")) == original
    proc = subprocess.run(
        [*cmd, "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(proc.stdout)
    assert result["state"] == "VERIFIED"
    assert result["provisional_index_matches"] == 142
    assert result["unclassified"] == 158
    assert result["next_independent_cohort_is_live"] is False
