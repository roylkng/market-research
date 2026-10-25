"""OPEN003: tamper tests for the cross-NSE evidence/decision barrier."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/open003_cross_universe_audit.py"
SPEC = importlib.util.spec_from_file_location("open003_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PACKET = (
    REPO / "research/broad-discovery/OPEN003_CROSS_UNIVERSE_EVIDENCE_20261025.json"
)


@pytest.fixture
def original():
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_exact_universe_and_no_buys(original):
    result = MODULE.evaluate(original)
    assert result["reviewed_candidates"] == 23
    assert result["group_counts"] == {
        "NEW_BROAD": 11, "ORIGINAL_10": 10, "SECTOR_CHALLENGER": 2
    }
    assert result["source_backed_parent_underwriting_complete"] == 0
    assert result["approved_positions"] == 0
    assert all(not row["investment_approved"] for row in result["candidate_rows"])


def test_cash_proxies_are_not_owner_cash_or_valuation(original):
    by_symbol = {x["symbol"]: x for x in MODULE.evaluate(original)["candidate_rows"]}
    expected = {
        "BLS": (765.8431, 8.93),
        "MASTEK": (513.7, 9.39),
        "CRIZAC": (127.2478, 5.26),
        "TRANSRAILL": (394.17, 6.84),
        "CMSINFO": (-9.674, None),
        "MAYURUNIQ": (108.9456, None),
        "INOXGREEN": (65.09, None),
        "ACE": (324.01, None),
    }
    for symbol, (proxy, yield_pct) in expected.items():
        r = by_symbol[symbol]
        assert r["consolidated_CFO_less_selected_PPE_cr"] == proxy
        assert r["naive_proxy_yield_pct"] == yield_pct
        assert r["parent_owner_cash_verified"] is False
    assert by_symbol["OIL"]["consolidated_CFO_less_selected_PPE_cr"] is None
    assert by_symbol["AXTEL"]["consolidated_CFO_less_selected_PPE_cr"] is None


@pytest.mark.parametrize("group,symbol", [
    ("ORIGINAL_10", "ANANTRAJ"),
    ("NEW_BROAD", "BLS"),
    ("SECTOR_CHALLENGER", "SUNTV"),
])
def test_cannot_remove_original_denominators(original, group, symbol):
    edited = copy.deepcopy(original)
    edited["candidates"] = [
        x for x in edited["candidates"] if x["symbol"] != symbol
    ]
    with pytest.raises(ValueError, match="23 unique"):
        MODULE.evaluate(edited)


def test_cannot_insert_or_approve_investment(original):
    edited = copy.deepcopy(original)
    edited["claims"]["approved_positions"] = 1
    with pytest.raises(ValueError, match="approval"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(original)
    edited["candidates"][0]["investment_approved"] = True
    with pytest.raises(ValueError, match="falsely approved"):
        MODULE.evaluate(edited)


def test_dont_fabricate_owner_cash_or_intrinsic_value(original):
    edited = copy.deepcopy(original)
    edited["candidates"][0]["underwritten_intrinsic_value_per_share"] = 900
    with pytest.raises(ValueError, match="unverified owner cash"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(original)
    edited["candidates"][0]["sustaining_parent_owner_cash_cr"] = 100
    with pytest.raises(ValueError, match="unverified owner cash"):
        MODULE.evaluate(edited)


def test_dont_backdate_price_or_infer_blank_as_zero(original):
    edited = copy.deepcopy(original)
    bls = next(x for x in edited["candidates"] if x["symbol"] == "BLS")
    bls["price_date"] = "2026-10-15"
    with pytest.raises(ValueError, match="cutoff"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(original)
    axtel = next(x for x in edited["candidates"] if x["symbol"] == "AXTEL")
    axtel["price_inr"] = None
    axtel["price_date"] = "2026-10-23"
    with pytest.raises(ValueError, match="no dated quote"):
        MODULE.evaluate(edited)


def test_reject_nonfinite_or_negative_cash_inputs(original):
    edited = copy.deepcopy(original)
    cms = next(x for x in edited["candidates"] if x["symbol"] == "CMSINFO")
    cms["fy26_after_tax_consolidated_cfo_cr"] = float("nan")
    with pytest.raises(ValueError, match="nonfinite"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(original)
    cms = next(x for x in edited["candidates"] if x["symbol"] == "CMSINFO")
    cms["fy26_selected_ppe_cash_cr"] = -409.268
    with pytest.raises(ValueError, match="capex sign"):
        MODULE.evaluate(edited)


def test_missing_source_or_bear_case_fails(original):
    edited = copy.deepcopy(original)
    edited["candidates"][0]["source_url"] = ""
    with pytest.raises(ValueError, match="source"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(original)
    edited["candidates"][0]["primary_blocker"] = "  "
    with pytest.raises(ValueError, match="bear-thesis blocker"):
        MODULE.evaluate(edited)


def test_hg009_experiment_guard_cannot_be_removed(original):
    edited = copy.deepcopy(original)
    edited["claims"]["original_hg009_selection_unchanged"] = False
    with pytest.raises(ValueError, match="approval"):
        MODULE.evaluate(edited)
