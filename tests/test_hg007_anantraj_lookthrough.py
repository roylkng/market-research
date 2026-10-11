from __future__ import annotations

import json
import math
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_anantraj_lookthrough import (
    ADDITIONAL_SUBSCRIBED_SHARES,
    OLD_POSSIBLE_PARENT_FD_SHARE_COUNT,
    PARENT_RETAINED_SHARES_AFTER_SUBSCRIPTION,
    build_conditional_ownership_lookthrough,
    load_original_ownership_sources,
)


def _build() -> dict:
    documents, market, receipts = load_original_ownership_sources(Path("."))
    return build_conditional_ownership_lookthrough(
        documents, market, original_source_provenance=receipts
    )


def test_real_three_original_issuer_sources_prove_two_layer_not_approval() -> None:
    result = _build()
    assert result["review_id"] == (
        "HG007-P022-ANANTRAJ-ASHOKCLOUD-CONDITIONAL-LOOKTHROUGH-v1"
    )
    assert len(result["original_source_provenance"]["original_documents"]) == 3
    assert result["original_rights_subscription"]["completed_additional_newco_shares"] == (
        ADDITIONAL_SUBSCRIBED_SHARES
    )
    assert result["original_rights_subscription"][
        "parent_newco_shares_after_july21_subscription"
    ] == PARENT_RETAINED_SHARES_AFTER_SUBSCRIPTION
    assert result["original_rights_subscription"][
        "completed_parent_cash_subscription_inr_crore"
    ] == pytest.approx(74.8645106)
    original = result["proposed_scheme"]
    assert original["one_newco_share_per_one_eligible_ARL_share"] is True
    assert original["parent_existing_newco_shares_not_cancelled"] is True
    assert original["parent_subsidiary_status_will_remain_per_issuer_statement"] is True
    assert original["effective_nclt_scheme_verified"] is False
    assert original["scheme_record_date_verified"] is False


def test_conditional_share_class_and_double_counting_math() -> None:
    result = _build()
    hyp = result["illustrative_no_other_newco_share_events_scenario"]
    n = OLD_POSSIBLE_PARENT_FD_SHARE_COUNT
    p = PARENT_RETAINED_SHARES_AFTER_SUBSCRIPTION
    assert n == 359_876_930
    assert p == 374_572_553
    assert hyp["record_date_parent_eligible_shares_NOT_VERIFIED"] == n
    assert hyp["newco_parent_retained_shares_IF_NOT_CANCELLED"] == p
    assert hyp["total_newco_shares_if_effective"] == p + n
    assert hyp["hypothetical_parent_retained_newco_equity_fraction"] == pytest.approx(
        0.5100045158585809
    )
    assert hyp["hypothetical_direct_ARL_shareholder_newco_fraction"] == pytest.approx(
        0.48999548414141914
    )
    assert hyp["parent_lookthrough_newco_share_per_original_ARL_share"] == pytest.approx(
        1.0408351349446046
    )
    assert hyp["two_layer_lookthrough_equivalent_newco_shares_per_original_ARL_share"] == pytest.approx(
        2.0408351349446046
    )
    assert math.isclose(
        hyp["two_layer_equity_claim_fraction_per_original_ARL_share"],
        1 / n,
        abs_tol=1e-18,
    )
    guard = result["valuation_double_counting_guard"]
    assert guard["cannot_add_100pct_newco_val_to_unchanged_parent_business_value"] is True
    assert guard["parent_cross_holding_must_be_removed_or_consistently_attributed"] is True
    assert guard["possible_revaluation_from_separate_listing_empirically_verified"] is False
    assert result["historical_share_count_proxy"][
        "is_independently_verified_future_record_date_basic_share_count"
    ] is False
    assert result["new_company_fair_value_or_distribution_price_calculated"] is False
    assert result["transaction_completion_probabilities_published"] is False
    assert result["live_capital_allowed"] is False


def test_mutating_original_pdf_or_receipt_cannot_advance_semantic_model(tmp_path: Path) -> None:
    from marketlab.hg007_anantraj_lookthrough import HG005_PATH, RAW_ROOT, RECEIPT_PATH, SOURCES

    files = [HG005_PATH, RECEIPT_PATH] + [
        RAW_ROOT / f"{spec['sha256']}.pdf" for spec in SOURCES.values()
    ]
    for path in files:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    load_original_ownership_sources(tmp_path)
    tampered = tmp_path / RAW_ROOT / (
        SOURCES["july21_completed_subscription"]["sha256"] + ".pdf"
    )
    tampered.write_bytes(tampered.read_bytes() + b"fake")
    with pytest.raises(ValueError, match="actual NSE original PDF changed"):
        load_original_ownership_sources(tmp_path)


def test_cannot_assume_future_record_date_or_make_retroactive_share_changes() -> None:
    documents, market, receipts = load_original_ownership_sources(Path("."))
    originals = deepcopy((documents, market))
    build_conditional_ownership_lookthrough(
        documents, market, original_source_provenance=receipts
    )
    assert (documents, market) == originals
    altered = deepcopy(market)
    altered["key_mechanical_context"]["ANANTRAJ"][
        "reported_fd_market_cap_inr_crore"
    ] += 1.0
    with pytest.raises(ValueError, match="source HG005 original frozen share denominator"):
        build_conditional_ownership_lookthrough(
            documents, altered, original_source_provenance=receipts
        )
    altered_docs = deepcopy(documents)
    altered_docs["july21_conditional_demerger_press"][3] = altered_docs[
        "july21_conditional_demerger_press"
    ][3].replace(
        "not result in the cancellation",
        "result in the cancellation",
    )
    with pytest.raises(ValueError, match="original July21 scheme press page 4"):
        build_conditional_ownership_lookthrough(
            altered_docs, market, original_source_provenance=receipts
        )


def test_reproducible_cli_and_expected_returns_firewall(tmp_path: Path) -> None:
    out = tmp_path / "conditional.json"
    command = [
        sys.executable,
        "scripts/build_hg007_anantraj_lookthrough.py",
        "--out", str(out),
    ]
    run = subprocess.run(command, check=True, capture_output=True, text=True)
    brief = json.loads(run.stdout)
    assert brief["parent_retained_pct_conditional"] == pytest.approx(51.00045158585809)
    assert brief["demerger_effective"] is False
    assert brief["live_capital_allowed"] is False
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result == _build()
    assert result["portfolio_eligibility_allowed"] is False
    assert result["stock_expected_returns_calculated"] is False
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    out.write_text(out.read_text(encoding="utf-8") + "{}")
    failed = subprocess.run(
        command + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "original source conditional economics changed" in failed.stderr
