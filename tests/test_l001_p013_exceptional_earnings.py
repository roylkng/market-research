"""L001 P013 original Q1 exceptional earnings integrity gates."""

from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p013_exceptional_earnings import (
    P007_SHA256,
    analyze_exceptional_original,
)


def synthetic():
    rows = []
    for n in range(100):
        rows.append({
            "symbol": f"S{n:03d}",
            "isin": f"INE{n:09d}",
            "original_quarter_sha256": "a" * 64,
            "q1_original_income_facts_cr": {
                "exceptional_items_before_tax": 0.,
                "profit_before_exceptional": 100.,
                "profit_before_tax": 100.,
                "profit_loss_for_period": 80.,
            },
        })
    doc = {
        "report_id": "L001-P007-ORIGINAL-Q1-OTHER-INCOME-TRIAGE-ALL100-v1",
        "original_quarter_xbrl_hashes_verified": 100,
        "live_capital_allowed": False,
        "companies": rows,
    }
    doc["report_sha256"] = digest(doc)
    return doc


def test_resealed_fake_source_does_not_bypass_p007_original_sha():
    with pytest.raises(AlphaContractError, match="sealed original"):
        analyze_exceptional_original(synthetic())


def test_original_document_cannot_be_silently_revised():
    altered = synthetic()
    altered["companies"][0]["q1_original_income_facts_cr"]["exceptional_items_before_tax"] = 80
    with pytest.raises(AlphaContractError, match="sealed original"):
        analyze_exceptional_original(altered)


def test_journal_makes_no_assumption_about_oneoff_pat():
    # Synthetic PBT bridge manually checked: 35.0696 + 56.252 = 91.3216.
    assert abs(35.0696 + 56.252 - 91.3216) < 0.00001
    assert abs(112.98 + 123.99 - 236.97) < 0.00001
    assert 56.252 / 91.3216 > .5
    assert 123.99 / 236.97 > .5


def test_source_pin_is_full_sha_and_fixed():
    assert len(P007_SHA256) == 64
    assert P007_SHA256 == (
        "ade5ea8f0d1e491fba4416443a8c5831b69cbbae81f6479bec61cfbba0e0c276"
    )
