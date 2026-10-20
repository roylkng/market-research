"""P020 cannot confuse historical subsidiary profit with annualized franchise ROIC."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p019_suntv_rights import (
    build_suntv_2026_cash_reconciliation,
    load_prior_evidence,
)
from marketlab.l001_p020_srl_hurdles import (
    AOC_SOURCE,
    ARCHIVED_PDF_SHA,
    IMPAIRMENT_SOURCE,
    P019_REPORT_SHA,
    REPORT_DATE,
    _normal,
    build_franchise_hurdle,
    materialize,
    original_page_proof,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / (
    "research/l001/l001-p020-srl-franchise-profit-and-impairment-hurdle-v1.json"
)


def _p019() -> dict:
    original, receipts = load_prior_evidence(ROOT)
    return build_suntv_2026_cash_reconciliation(original, receipts)


def test_issuer_archived_full_pdf_original_pages_and_clock():
    source = original_page_proof(ROOT)
    assert source["full_original_pdf_sha256"] == ARCHIVED_PDF_SHA
    assert source["original_full_pdf_retained"] is True
    assert source["first_real_retrieval_at_utc"].startswith("2026-10-20")
    assert [x["original_pdf_zero_based_page"] for x in source["original_page_proofs"]] == [32, 226]
    assert all(len(x["extracted_page_text_sha256"]) == 64 for x in source["original_page_proofs"])


def test_aoc_period_accounting_and_impairment_hurdles_are_not_annualized():
    output = materialize(ROOT)
    assert output["research_as_of"] == REPORT_DATE
    assert output["p019_audited_cash_bridge_sha256"] == P019_REPORT_SHA
    assert output["source_aoc1_period"] == AOC_SOURCE
    assert output["source_impairment_note"] == IMPAIRMENT_SOURCE
    assert output["initial_franchise_right_asset_cr"] == pytest.approx(1190.88)
    assert output["reported_group_carrying_value_cr_not_liquidation_value"] == pytest.approx(1248.27)
    assert output["source_period_PAT_to_initial_asset_cost_percent_not_ROIC"] == pytest.approx(1.3713)
    assert output["source_period_reported_PAT_margin_percent"] == pytest.approx(17.2768)
    assert [x["required_recurring_owner_cash_cr_if_no_growth"] for x in output["hypothetical_cash_hurdles_unlinked_to_forecasts"]] == pytest.approx([
        59.544, 107.1792, 142.9056,
    ])
    assert output["hypothetical_cash_hurdles_unlinked_to_forecasts"][1][
        "compared_to_nonannualized_period_PAT_ratio_not_ROIC"
    ] == pytest.approx(6.5633)
    assert output["post_acquisition_annual_SRL_owner_cash_cr"] is None
    assert output["normalized_parent_owner_FCF_cr"] is None
    assert output["expected_net_3y_stock_return"] is None
    for name in (
        "franchise_acquisition_cash_vs_accounting_asset_mapped_to_bank_records",
        "aoc1_period_is_post_control_only",
        "AOC_profit_is_cash_flow",
        "AOC_PAT_ratio_is_annualized_invested_capital_ROIC",
        "9pct_discount_rate_is_proven_investor_required_return",
        "no_impairment_means_stock_is_undervalued",
        "franchise_perpetuity_cash_flow_assumed",
        "historical_return_signal_preregistered_prior_oct15",
        "company_paper_investment_eligible",
        "live_capital_allowed",
    ):
        assert output[name] is False, name
    validate(output, ROOT)


def test_fake_cash_or_period_normalization_is_rejected():
    src = original_page_proof(ROOT)
    prior = _p019()
    modified = copy.deepcopy(AOC_SOURCE)
    modified["parent_control_effective"] = "2025-01-01"
    with pytest.raises(AlphaContractError, match="source period"):
        build_franchise_hurdle(p019=prior, source_proof=src, original_aoc=modified)

    changed_impairment = copy.deepcopy(IMPAIRMENT_SOURCE)
    changed_impairment["gross_franchise_asset_carrying_cr"] = "800"
    with pytest.raises(AlphaContractError, match="source period"):
        build_franchise_hurdle(p019=prior, source_proof=src, impairment=changed_impairment)


def test_tampered_pdf_or_receipt_does_not_generate_owner_cash():
    report = materialize(ROOT)
    report["hypothetical_cash_hurdles_unlinked_to_forecasts"][1][
        "required_recurring_owner_cash_cr_if_no_growth"
    ] = 0
    with pytest.raises(AlphaContractError, match="digest mismatch"):
        validate(report, ROOT)
    bad = {"full_original_pdf_sha256": "0" * 64}
    with pytest.raises(AlphaContractError, match="original full PDF source proof"):
        build_franchise_hurdle(p019=_p019(), source_proof=bad)


def test_immutable_original_pdf_replays_and_direct_cli_checks_report():
    expected = materialize(ROOT)
    observed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert observed == expected
    run = subprocess.run(
        [sys.executable, "scripts/materialize_l001_p020_srl.py", "--check"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(run.stdout)
    assert report["state"] == "VERIFIED"
    assert report["source_document_sha256"] == ARCHIVED_PDF_SHA
    assert report["source_profit_ratio_is_ROIC"] is False
    assert report["live_capital_allowed"] is False


def test_pdf_ligature_typography_preserves_strict_source_terms():
    # pypdf may decode a printed 'fi' glyph as the Unicode ligature U+FB01.
    assert _normal("inde\uFB01nite useful life") == _normal("indefinite useful life")
    assert _normal("no impairment loss") != _normal("impairment loss")
