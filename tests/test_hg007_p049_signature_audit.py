"""P049 old self-signature mismatch must not rewrite historical original data."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg007_p049_signature_audit import (
    LEGACY_CLAIMED_SHA,
    SOURCE,
    SOURCE_GIT_BLOB,
    build_p049_signature_audit,
    validate_p049_signature_audit,
)

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "research/hg007/hg007-p049-legacy-signature-audit-v2.json"


def test_original_git_identity_and_claimed_sha_are_explicitly_distinct():
    report = build_p049_signature_audit(ROOT)
    assert report["historical_original_git_blob_sha1"] == SOURCE_GIT_BLOB
    assert report["legacy_packet_claimed_sha256"] == LEGACY_CLAIMED_SHA
    assert report["canonical_recomputed_without_claim_sha256"] != LEGACY_CLAIMED_SHA
    assert report["legacy_packet_sha_claim_matches_current_digest"] is False
    assert report["historical_original_path"] == str(SOURCE)
    assert report["historical_original_raw_sha256"]
    assert report["legacy_report_market_price_inr"] == 777.9
    assert report["legacy_source_issuer"] == "DATAMATICS"
    assert report["legacy_data_was_mutated"] is False
    assert report["financial_statement_cashflow_newly_verified"] is False
    assert report["equity_target_price_approved"] is False
    assert report["live_capital_allowed"] is False
    validate_p049_signature_audit(report, ROOT)


def test_signed_v2_separate_artifact_does_not_replace_v1():
    audit = build_p049_signature_audit(ROOT)
    assert V2.is_file()
    assert json.loads(V2.read_text(encoding="utf-8")) == audit
    proc = subprocess.run(
        [
            sys.executable, "scripts/audit_hg007_p049_signature.py",
            "--check",
        ],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    recorded = json.loads(proc.stdout)
    assert recorded["original_git_blob_verified"] is True
    assert recorded["legacy_self_sha_valid"] is False
    assert recorded["live_capital_allowed"] is False


def test_modified_source_must_fail_git_blob_even_if_re_signed(tmp_path: Path):
    path = tmp_path / SOURCE
    path.parent.mkdir(parents=True, exist_ok=True)
    original = (ROOT / SOURCE).read_text(encoding="utf-8")
    path.write_text(original.replace("777.9", "999.0", 1), encoding="utf-8")
    with pytest.raises(AlphaContractError, match="exact historical Git blob"):
        build_p049_signature_audit(tmp_path)


def test_resigned_audit_does_not_promote_price_targets():
    report = build_p049_signature_audit(ROOT)
    report["equity_target_price_approved"] = True
    with pytest.raises(AlphaContractError, match="selfhash invalid"):
        validate_p049_signature_audit(report, ROOT)
