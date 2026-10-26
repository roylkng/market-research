"""Verify Century Enka's book-return hurdle without pretending it is a DCF."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open006_centenka_roe_hurdle.py"
SPEC = importlib.util.spec_from_file_location("open006_book", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
INPUT = ROOT / "research/broad-discovery/OPEN006_CENTENKA_ROE_HURDLE_INPUT_20261026.json"


@pytest.fixture
def packet():
    return json.loads(INPUT.read_text(encoding="utf-8"))


def test_official_book_pat_price_hurdle(packet):
    r = MODULE.evaluate(packet)
    assert r["issuer"] == "CENTENKA"
    assert r["price_at_last_regular_close_inr"] == 505.8
    assert r["reference_shares_from_prior_original_crore"] == 2.1850589
    assert r["indicative_equity_market_cap_crore"] == 1105.2
    assert r["fy26_book_per_reference_share_inr"] == 684.6
    assert r["price_to_march_book"] == 0.7388
    assert r["discount_to_march_book_pct"] == 26.12
    assert r["FY26_pat_crore"] == 100.8
    assert r["FY26_earnings_yield_pct"] == 9.12
    assert r["years_closing_equity_ROE_pct"] == [
        {"year": "FY24", "year_end_ROE_pct": 3.1369},
        {"year": "FY25", "year_end_ROE_pct": 4.691},
        {"year": "FY26", "year_end_ROE_pct": 6.7384},
    ]
    assert r["three_year_closing_ROE_average_pct"] == 4.8554
    assert r["FY26_revenue_change_pct"] == -14.8
    assert r["planned_FY27_capex_as_share_of_FY26_approx_operating_cash_pct"] == 96.0
    assert r["hypothetical_cash_remaining_if_FY26_approx_cash_repeats_crore"] == 5.0
    assert r["investment_approved"] is False
    assert r["intrinsic_value_verified"] is False


def test_earnings_yield_is_not_a_proven_equity_valuation(packet):
    r = MODULE.evaluate(packet)
    h = r["analytical_zero_growth_full_distribution_hurdles"]
    assert [x["required_equity_return_pct"] for x in h] == [10, 12, 15]
    assert [x["ROE_required_to_support_dated_price_pct"] for x in h] == [
        7.388, 8.866, 11.082
    ]
    assert [x["earnings_capitalization_identity_share_inr"] for x in h] == [
        461.31, 384.43, 307.54
    ]
    assert all(x["price_target"] is False for x in h)


@pytest.mark.parametrize("key,value", [
    ("price_date", "2026-10-27"),
    ("symbol", "BLS"),
    ("type", "PROSPECTIVE_ALPHA"),
    ("status", "BUY"),
])
def test_reject_backfill_and_promotion(packet, key, value):
    changed = copy.deepcopy(packet)
    changed[key] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(changed)


def test_reject_fabricated_source_hash_and_valuation(packet):
    changed = copy.deepcopy(packet)
    changed["source_lineage"]["original_bytes_sha256_archived_here"] = "f" * 64
    with pytest.raises(ValueError, match="evidence"):
        MODULE.evaluate(changed)
    changed = copy.deepcopy(packet)
    changed["economic_test"]["intrinsic_equity_value_crore"] = 2000
    with pytest.raises(ValueError, match="unverified"):
        MODULE.evaluate(changed)


def test_reject_future_earnings_or_unsupported_share_count(packet):
    changed = copy.deepcopy(packet)
    changed["unresolved"]["FY27_Q2_results_original_verified"] = True
    with pytest.raises(ValueError, match="backfilled"):
        MODULE.evaluate(changed)
    changed = copy.deepcopy(packet)
    changed["exact_shares_from_March_2025_annual_report"] = -1
    with pytest.raises(ValueError, match="share count"):
        MODULE.evaluate(changed)


def test_reject_nonfinite_numbers_and_hurdle_revisions(packet):
    changed = copy.deepcopy(packet)
    changed["annual_data"]["FY26"]["group_PAT_crore"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        MODULE.evaluate(changed)
    changed = copy.deepcopy(packet)
    changed["economic_test"]["required_equity_yields"] = [0.08, 0.09, 0.10]
    with pytest.raises(ValueError, match="hurdle"):
        MODULE.evaluate(changed)
