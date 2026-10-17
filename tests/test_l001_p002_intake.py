"""L001 P002 keeps all 100 HG009 names without pretending to source full cash flow."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p002_intake import (
    ClassificationReceipt,
    build_source_intake,
    industry_from_original,
)

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "research/hg009/hg009-d001-100-experimental-companies-v1.json"
P014 = ROOT / "research/hg009/hg009-p014-economic-symmetry-and-cash-v1.json"
CUTOFF = "2026-10-17T12:00:00Z"


def sources():
    return (
        json.loads(COHORT.read_text(encoding="utf-8")),
        json.loads(P014.read_text(encoding="utf-8")),
    )


def receipt(symbol: str, isin: str, industry: str) -> ClassificationReceipt:
    text = f"Official NSE industry: {industry}; symbol: {symbol}; ISIN: {isin}"
    return ClassificationReceipt(
        symbol=symbol, isin=isin, official_industry=industry,
        original_raw_bytes=text.encode(), expected_sha256=sha256(text.encode()).hexdigest(),
        source_url="https://nsearchives.nseindia.com/corporate/index.html",
        published_utc="2026-10-15T06:00:00Z",
        first_seen_utc="2026-10-16T08:00:00Z",
        reviewer_status="INDEPENDENTLY_REVIEWED",
    )


def test_real_100_roster_preserved_without_inventing_valuation():
    result = build_source_intake(*sources(), research_cutoff_utc=CUTOFF)
    assert result["company_count"] == 100
    assert result["counts"]["detailed_p014_dossiers"] == 10
    assert result["counts"]["fy26_consolidated_cash_replay_references"] == 5
    assert result["counts"]["official_industry_verified_in_this_intake"] == 0
    assert result["counts"]["source_complete"] == 0
    assert all(not row["source_complete"] for row in result["companies"])
    assert all(row["expected_return"] is None for row in result["companies"])
    assert all(row["model"] == "CLASSIFICATION_REQUIRED" for row in result["companies"])
    assert result["report_sha256"] == digest({
        k: v for k, v in result.items() if k != "report_sha256"
    })


def test_every_p014_cash_replay_is_still_not_owner_cash():
    report = build_source_intake(*sources(), research_cutoff_utc=CUTOFF)
    by_symbol = {row["symbol"]: row for row in report["companies"]}
    assert by_symbol["ACE"]["prior_dossier_source_state"] == (
        "FY26_CASH_REPLAY_REFERENCE_NOT_OWNER_CASH"
    )
    assert by_symbol["DATAMATICS"]["valid_long_horizon_valuation"] is False
    assert by_symbol["PIXTRANS"]["prior_dossier_source_state"] == (
        "INTERIM_OR_OTHER_FINANCIAL_DIAGNOSTIC"
    )
    assert by_symbol["ANANTRAJ"]["prior_dossier_source_state"] == (
        "DOSSIER_WITHOUT_OWNER_CASH"
    )
    assert by_symbol["ABCAPITAL"]["prior_dossier_source_state"] == (
        "NO_PRIOR_COMPANY_CASH_DOSSIER"
    )


def test_original_selection_mutation_cannot_be_resealed():
    cohort, p014 = sources()
    changed = copy.deepcopy(cohort)
    changed["selected"][0]["isin"] = "INE000000000"
    changed["cohort_sha256"] = digest({
        k: v for k, v in changed.items() if k != "cohort_sha256"
    })
    with pytest.raises(AlphaContractError, match="immutable source signature"):
        build_source_intake(changed, p014, research_cutoff_utc=CUTOFF)


def test_resealed_prior_cash_dossier_mutation_rejected():
    cohort, p014 = sources()
    changed = copy.deepcopy(p014)
    changed["cash_flow_and_other_income_diagnostics"][0]["symbol"] = "SPOOF"
    changed["report_sha256"] = digest({
        k: v for k, v in changed.items() if k != "report_sha256"
    })
    with pytest.raises(AlphaContractError, match="immutable source signature"):
        build_source_intake(cohort, changed, research_cutoff_utc=CUTOFF)


def test_financial_issuer_never_receives_industrial_roic_template():
    cohort, p014 = sources()
    # Use the actual sealed ISIN, not an invented example.
    actual = next(row for row in cohort["selected"] if row["symbol"] == "BAJFINANCE")
    r = receipt(actual["symbol"], actual["isin"], "Financial Services")
    report = build_source_intake(
        cohort, p014, research_cutoff_utc=CUTOFF,
        classifications={(r.symbol, r.isin): r},
    )
    entry = next(row for row in report["companies"] if row["symbol"] == "BAJFINANCE")
    assert entry["model"] == "FINANCIAL_SPECIALIST_ONLY"
    assert "REQUIRED_CREDIT_COST_AND_ASSET_QUALITY_MISSING" in entry["missing_evidence"]
    assert "REQUIRED_INCREMENTAL_NOPAT_AND_INVESTED_CAPITAL_MISSING" not in (
        entry["missing_evidence"]
    )
    assert entry["valid_long_horizon_valuation"] is False


def test_nonfinancial_source_classification_does_not_claim_full_cash_completeness():
    cohort, p014 = sources()
    entry = next(row for row in cohort["selected"] if row["symbol"] == "ACE")
    r = receipt(entry["symbol"], entry["isin"], "Capital Goods")
    report = build_source_intake(
        cohort, p014, research_cutoff_utc=CUTOFF,
        classifications={(r.symbol, r.isin): r},
    )
    actual = next(row for row in report["companies"] if row["symbol"] == "ACE")
    assert actual["model"] == "INDUSTRIAL_REVIEW_ONLY"
    assert "REQUIRED_INCREMENTAL_NOPAT_AND_INVESTED_CAPITAL_MISSING" in (
        actual["missing_evidence"]
    )
    assert actual["source_complete"] is False


def test_ticker_identity_and_missing_classification_fail_closed():
    assert industry_from_original(
        None, symbol="BAJFINANCE", isin="INE296A01032",
        decision_cutoff_utc=CUTOFF,
    ) == "UNCLASSIFIED"
    r = receipt("ACE", "INE731H01025", "Capital Goods")
    assert industry_from_original(
        r, symbol="ACUTAAS", isin="INE00FF01025",
        decision_cutoff_utc=CUTOFF,
    ) == "UNCLASSIFIED"


def test_bad_hash_future_publication_and_review_fail_closed():
    r = receipt("ACE", "INE731H01025", "Capital Goods")
    for changed in (
        replace(r, expected_sha256="0" * 64),
        replace(r, published_utc="2026-10-18T00:00:00Z"),
        replace(r, reviewer_status="SELF_REPORTED"),
        replace(r, source_url="https://nsearchives.nseindia.com.evil.test/file"),
    ):
        assert industry_from_original(
            changed, symbol=r.symbol, isin=r.isin, decision_cutoff_utc=CUTOFF,
        ) == "UNCLASSIFIED"


def test_cannot_add_or_silently_delete_member():
    cohort, p014 = sources()
    cohort["selected"].pop()
    with pytest.raises(AlphaContractError):
        build_source_intake(cohort, p014, research_cutoff_utc=CUTOFF)


def test_unknown_issuer_receipts_rejected():
    cohort, p014 = sources()
    fake = receipt("NOTIN100", "INE000000000", "Financial Services")
    with pytest.raises(AlphaContractError, match="extraneous issuer classification"):
        build_source_intake(
            cohort, p014, research_cutoff_utc=CUTOFF,
            classifications={(fake.symbol, fake.isin): fake},
        )
