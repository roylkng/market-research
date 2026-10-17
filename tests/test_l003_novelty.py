"""L003 contract tests. Synthetic guidance is not investment evidence."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from marketlab.l003_novelty import (
    QuantifiedGuidance,
    assess_guidance_revision,
    assess_sealed_h021_feature,
)

ROOT = Path(__file__).resolve().parents[1]
H021 = ROOT / "research/prospective/ae001-h021/expectations/2026-10-16-v1.json"
CUTOFF = "2026-10-16T13:00:00Z"


def statement(*, literal: str = "300", published: str = "2026-10-15T09:00:00Z"):
    original = f"Issuer guidance for FY27 expected revenue is INR {literal} crore."
    return QuantifiedGuidance(
        symbol="ACE", isin="INE731H01025", metric="REVENUE", period_end="2027-03-31",
        accounting_scope="CONSOLIDATED", unit="INR_CRORE", value=float(literal),
        value_literal=literal, statement_excerpt=original,
        original_document_bytes=original.encode(),
        expected_sha256=sha256(original.encode()).hexdigest(),
        source_url="https://nsearchives.nseindia.com/corporate/original.html",
        source_type="NSE_ORIGINAL", published_utc=published,
        first_seen_utc=published, reviewer_status="INDEPENDENTLY_REVIEWED",
    )


def test_synthetic_comparable_guidance_delta_is_not_alpha():
    old = statement()
    new = statement(literal="360", published="2026-10-16T11:00:00Z")
    result = assess_guidance_revision(old, new, decision_cutoff_utc=CUTOFF)
    assert result["absolute_delta"] == 60
    assert result["percent_delta"] == 20
    assert result["status"] == "SOURCE_BOUNDED_GUIDANCE_DELTA_ONLY"
    assert result["forecast_return"] is None
    assert result["investment_authorized"] is False


def test_no_prior_public_guidance_abstains():
    new = statement(literal="360", published="2026-10-16T11:00:00Z")
    result = assess_guidance_revision(None, new, decision_cutoff_utc=CUTOFF)
    assert "prior_and_current_public_guidance_required" in result["reasons"]


def test_future_issuer_document_is_rejected():
    new = statement(literal="360", published="2026-10-16T14:00:00Z")
    result = assess_guidance_revision(statement(), new, decision_cutoff_utc=CUTOFF)
    assert "source_publication_or_capture_after_cutoff" in result["reasons"]


def test_changed_original_byte_rejected():
    new = replace(statement(literal="360", published="2026-10-16T11:00:00Z"),
                  original_document_bytes=b"Different content")
    result = assess_guidance_revision(statement(), new, decision_cutoff_utc=CUTOFF)
    assert "original_bytes_digest_mismatch" in result["reasons"]


def test_guidance_literal_must_match_original_and_numeric():
    new = replace(statement(literal="360", published="2026-10-16T11:00:00Z"),
                  value=100.0)
    result = assess_guidance_revision(statement(), new, decision_cutoff_utc=CUTOFF)
    assert "guidance_literal_mismatch" in result["reasons"]


def test_wrong_issuer_basis_period_rejected():
    new = replace(statement(literal="360", published="2026-10-16T11:00:00Z"),
                  isin="INE000000000", accounting_scope="STANDALONE")
    result = assess_guidance_revision(statement(), new, decision_cutoff_utc=CUTOFF)
    assert "issuer_period_scope_metric_comparability_mismatch" in result["reasons"]


def test_revised_before_initial_guidance_rejected():
    new = statement(literal="360", published="2026-10-14T11:00:00Z")
    result = assess_guidance_revision(statement(), new, decision_cutoff_utc=CUTOFF)
    assert "guidance_not_chronologically_revised" in result["reasons"]


def test_nse_host_spoof_rejected():
    new = replace(statement(literal="360", published="2026-10-16T11:00:00Z"),
                  source_url="https://nsearchives.nseindia.com.bad.test/file")
    result = assess_guidance_revision(statement(), new, decision_cutoff_utc=CUTOFF)
    assert "nse_source_host_mismatch" in result["reasons"]


def test_review_is_required_and_not_independently_proved_by_code():
    new = replace(statement(literal="360", published="2026-10-16T11:00:00Z"),
                  reviewer_status="UNREVIEWED")
    result = assess_guidance_revision(statement(), new, decision_cutoff_utc=CUTOFF)
    assert "financial_semantic_review_missing" in result["reasons"]


def test_zero_prior_yields_absolute_delta_without_fabricated_percent():
    old = statement(literal="0")
    new = statement(literal="50", published="2026-10-16T11:00:00Z")
    result = assess_guidance_revision(old, new, decision_cutoff_utc=CUTOFF)
    assert result["status"] == "SOURCE_BOUNDED_GUIDANCE_DELTA_ONLY"
    assert result["percent_delta"] is None


def test_real_oct16_h021_panel_blocks_same_day_ae001_cutoff():
    panel = json.loads(H021.read_text(encoding="utf-8"))
    assert panel["row_count"] == 100
    assert panel["primary_signal_available_count"] == 92
    assert panel["ae001_same_day_eod_1830_compatible"] is False
    result = assess_sealed_h021_feature(
        panel, symbol="ABB", isin="INE117A01022", decision_cutoff_utc=CUTOFF,
    )
    assert result["status"] == "ABSTAIN"
    assert "h021_capture_after_decision_cutoff" in result["reasons"]


def test_real_h021_panel_allows_prospective_preopen_oct19_not_hg009():
    panel = json.loads(H021.read_text(encoding="utf-8"))
    result = assess_sealed_h021_feature(
        panel, symbol="ABB", isin="INE117A01022",
        decision_cutoff_utc="2026-10-19T03:00:00Z",
    )
    assert result["status"] == "PROSPECTIVE_H021_REVISION_SOURCE_ONLY"
    assert result["hg009_100_cohort_join_authorized"] is False
    assert result["investment_authorized"] is False


def test_h021_nonmember_returns_abstain_not_imputation():
    panel = json.loads(H021.read_text(encoding="utf-8"))
    result = assess_sealed_h021_feature(
        panel, symbol="ACE", isin="INE731H01025",
        decision_cutoff_utc="2026-10-19T03:00:00Z",
    )
    assert result["status"] == "ABSTAIN"
    assert "not_in_sealed_h021_u001_universe" in result["reasons"]


def test_h021_resealed_or_modified_panel_rejected():
    panel = json.loads(H021.read_text(encoding="utf-8"))
    changed = copy.deepcopy(panel)
    changed["rows"][0]["values"]["h021_primary_eps_revision_30d_pct"] = 1000
    result = assess_sealed_h021_feature(
        changed, symbol="ABB", isin="INE117A01022",
        decision_cutoff_utc="2026-10-19T03:00:00Z",
    )
    assert "h021_panel_hash_mismatch" in result["reasons"]
