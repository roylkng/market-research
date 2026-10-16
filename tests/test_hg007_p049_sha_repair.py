"""P049 legacy self-SHA mismatch is disclosed, not silently fixed in place."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg007_p049_sha_repair import (
    OLD_GIT_BLOB,
    OLD_PATH,
    P047_GIT_BLOB,
    P047_PATH,
    build_p049_sha_repair,
    verify_repair_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg007/hg007-p049-canonical-sha-repair-v2.json"


def test_preserves_original_git_and_explicitly_different_signed_body():
    result = build_p049_sha_repair(ROOT)
    assert result["legacy_original_json_git_blob_sha"] == OLD_GIT_BLOB
    assert result["parent_original_nse_market_git_blob_sha"] == P047_GIT_BLOB
    assert result["legacy_original_claimed_packet_sha256"] != (
        result["recomputed_original_canonical_body_sha256"]
    )
    assert result["legacy_original_self_signature_matches_canonical_digest"] is False
    assert result["numeric_serialization_mismatch_root_cause_independently_proven"] is False
    assert result["original_v1_packet_modified"] is False
    assert result["source_byte_identity_preserved"] is True
    assert result["frozen_original_oct13_eq_close_inr_not_current"] == 777.9
    assert result["frozen_original_isin"] == "INE365B01017"
    assert result["current_oct16_fully_diluted_share_count_verified"] is False
    assert result["new_expected_returns_or_probability_published"] is False
    assert result["live_capital_allowed"] is False
    verify_repair_artifact(result, root=ROOT)


def test_original_p049_bytes_and_2026_oct13_nse_market_stay_untouched():
    report = build_p049_sha_repair(ROOT)
    original = json.loads((ROOT / OLD_PATH).read_text("utf-8"))
    market = json.loads((ROOT / P047_PATH).read_text("utf-8"))
    assert original["packet_sha256"] == report["legacy_original_claimed_packet_sha256"]
    assert original["market_source"]["official_EQ_close_inr_not_current_quote"] == 777.9
    assert original["market_source"]["frozen_original_28_case_packet_sha256"] == (
        market["packet_sha256"]
    )
    assert report["parent_original_nse_market_packet_sha256"] == market["packet_sha256"]


def test_modified_original_cash_or_quote_source_blobs_fail_before_resigning(
    tmp_path: Path,
):
    for item in (OLD_PATH, P047_PATH):
        target = tmp_path / item
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / item).read_bytes())
    altered = tmp_path / OLD_PATH
    old = altered.read_bytes()
    assert b"DATAMATICS" in old
    altered.write_bytes(old.replace(b"DATAMATICS", b"BOGUS_XXX", 1))
    with pytest.raises(AlphaContractError, match="Git object drifted"):
        build_p049_sha_repair(tmp_path)

    altered.write_bytes(old)
    market = tmp_path / P047_PATH
    raw = market.read_bytes()
    market.write_bytes(raw.replace(b"DATAMATICS", b"BOGUS_XXX", 1))
    with pytest.raises(AlphaContractError, match="Git object drifted"):
        build_p049_sha_repair(tmp_path)


def test_new_v2_receipt_cannot_be_resealed_with_false_return():
    result = build_p049_sha_repair(ROOT)
    bad = copy.deepcopy(result)
    bad["new_investment_recommendations"] = True
    with pytest.raises(AlphaContractError, match="signed discrepancy"):
        verify_repair_artifact(bad, root=ROOT)
    bad = copy.deepcopy(result)
    bad["new_investment_recommendations"] = True
    bad.pop("repair_packet_sha256")
    bad["repair_packet_sha256"] = digest(bad)
    with pytest.raises(AlphaContractError, match="pinned original"):
        verify_repair_artifact(bad, root=ROOT)


def test_v2_packet_is_deterministic_under_original_sources_and_cli():
    expected = build_p049_sha_repair(ROOT)
    assert expected == json.loads(REPORT.read_text("utf-8"))
    proc = subprocess.run(
        [sys.executable, "scripts/materialize_hg007_p049_sha_repair.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    result = json.loads(proc.stdout)
    assert result["state"] == "VERIFIED"
    assert result["repair_sha256"] == expected["repair_packet_sha256"]
    assert result["legacy_v1_modified"] is False
