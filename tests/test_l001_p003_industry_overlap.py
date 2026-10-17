"""Adversarial integrity checks for provisional NSE industry overlap."""

from __future__ import annotations

import copy
import json

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p003_industry_overlap import build_provisional_industry_crosswalk
from scripts.materialize_l001_p003_industry_overlap import (
    COHORT, CSV, OUTPUT, READINESS, materialize,
)


def inputs():
    return (
        json.loads(COHORT.read_text(encoding="utf-8")),
        CSV.read_bytes(),
        json.loads(READINESS.read_text(encoding="utf-8")),
    )


def test_real_nse_source_matches_46_out_of_100_but_not_promoted():
    result = build_provisional_industry_crosswalk(*inputs())
    assert result["csv_row_count"] == 755
    assert result["original_frozen_cohort_count"] == 100
    assert result["exact_identity_matches"] == 46
    assert result["outside_nifty_total_market_subset"] == 54
    assert result["financial_services_caution_symbols"] == [
        "ABCAPITAL", "BAJFINANCE", "M&MFIN", "MUTHOOTFIN"
    ]
    assert result["sc002_ready_before_cutoff_sessions"] == 0
    assert result["source_is_quality_approved_for_model"] is False
    assert all(not row["industry_model_admitted"] for row in result["rows"])
    assert all(not row["valuation_ready"] for row in result["rows"])
    assert result["report_sha256"] == digest({
        k: v for k, v in result.items() if k != "report_sha256"
    })


def test_replay_committed_hundred_company_report_bytes():
    assert OUTPUT.read_text(encoding="utf-8") == materialize()


def test_raw_nse_csv_tampering_rejected():
    cohort, raw, readiness = inputs()
    with pytest.raises(AlphaContractError, match="original NSE CSV bytes"):
        build_provisional_industry_crosswalk(cohort, raw + b"t", readiness)


def test_resealed_frozen_cohort_change_rejected():
    cohort, raw, readiness = inputs()
    changed = copy.deepcopy(cohort)
    changed["selected"][0]["symbol"] = "FAKE"
    changed["cohort_sha256"] = digest({
        k: v for k, v in changed.items() if k != "cohort_sha256"
    })
    with pytest.raises(AlphaContractError, match="HG009 original"):
        build_provisional_industry_crosswalk(changed, raw, readiness)


def test_false_source_readiness_rejected_even_if_resealed():
    cohort, raw, readiness = inputs()
    changed = copy.deepcopy(readiness)
    changed["prospective_industry_source_ready"] = True
    changed["ready_before_cutoff_session_count"] = 5
    changed["summary_sha256"] = digest({
        k: v for k, v in changed.items() if k != "summary_sha256"
    })
    with pytest.raises(AlphaContractError, match="SC002 archived"):
        build_provisional_industry_crosswalk(cohort, raw, changed)


def test_no_industrial_model_inferred_from_absent_industry():
    report = build_provisional_industry_crosswalk(*inputs())
    by_symbol = {row["symbol"]: row for row in report["rows"]}
    assert by_symbol["ACE"]["provisional_industry_from_exact_csv"] == "Capital Goods"
    assert by_symbol["ACE"]["industry_model_admitted"] is False
    assert by_symbol["SATIN"]["provisional_industry_from_exact_csv"] is None
    assert by_symbol["SATIN"]["industry_model_admitted"] is False
    assert by_symbol["BAJFINANCE"]["potential_financial_services_not_valuation_class"]
    assert by_symbol["BAJFINANCE"]["industry_model_admitted"] is False
