"""P013 original NSE FY26 cash and investing source evidence tests."""

from __future__ import annotations

import copy
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p009_attestation import SOURCES
from marketlab.hg009_p013_cash_bridge import (
    EXPECTED_LAKH,
    FIELDS,
    _row_values,
    build_original_fy26_cash_use,
    extract_exact_fy26_cells,
    verify_original_fy26_cash_use,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/hg009/hg009-p013-fy26-cash-use-bridge-v1.json"


def _original(symbol: str) -> bytes:
    pin = SOURCES[symbol]
    location = (
        ROOT / "research/hg009/p008-originals" / symbol
        / (pin["raw_sha256"] + ".html.gz")
    )
    return gzip.decompress(location.read_bytes())


def test_archived_nse_cash_flow_row_values_prove_every_field_and_reconcile_cash():
    report = build_original_fy26_cash_use(ROOT)
    assert report["archived_full_original_fy26_cashflow_source_count"] == 3
    assert report["individually_row_replayed_source_cash_fields"] == 51
    assert report["all_three_cashflow_open_close_arithmetics_reconcile"] is True
    assert report["owner_cashflow_models_validated_count"] == 0
    assert report["live_capital_allowed"] is False
    records = {row["symbol"]: row for row in report["symbol_records"]}
    assert set(records) == set(SOURCES)
    for symbol, values in EXPECTED_LAKH.items():
        assert len(values) == len(FIELDS) == 17
        extracted = extract_exact_fy26_cells(_original(symbol), symbol)
        assert set(extracted) == set(FIELDS)
        assert records[symbol]["verified_original_cash_flow_cell_count"] == 17
        assert records[symbol]["cash_begin_to_end_reconciles_to_CFO_investing_financing"]
        assert records[symbol]["probability_weighted_equity_value"] is None
        assert records[symbol]["portfolio_eligible"] is False
        assert records[symbol]["live_capital_allowed"] is False
    verify_original_fy26_cash_use(report, root=ROOT)


def test_investment_and_financing_are_separate_from_owner_cash():
    records = {
        row["symbol"]: row
        for row in build_original_fy26_cash_use(ROOT)["symbol_records"]
    }
    a, e, t = (records["ACUTAAS"], records["ACE"], records["TRAVELFOOD"])
    assert a["cashflow_after_all_investing_cr_not_owner_fcf"] == 26.2306
    assert e["cashflow_after_all_investing_cr_not_owner_fcf"] == 67.38
    assert t["cashflow_after_all_investing_cr_not_owner_fcf"] == 243.161
    assert a["cashflow_after_investing_and_financing_cr_not_owner_fcf"] == 30.3268
    assert e["cashflow_after_investing_and_financing_cr_not_owner_fcf"] == 15.47
    assert t["cashflow_after_investing_and_financing_cr_not_owner_fcf"] == 22.424
    assert a["source_CFO_less_PPE_cash_proxy_cr_not_owner_fcf"] == -35.8052
    assert e["source_CFO_less_PPE_cash_proxy_cr_not_owner_fcf"] == 324.01
    assert t["source_CFO_less_PPE_cash_proxy_cr_not_owner_fcf"] == 354.436
    assert e["purchased_less_sold_financial_securities_cr_not_expense"] == 322.75
    assert t["purchased_less_sold_financial_securities_cr_not_expense"] == 144.495
    assert a["purchased_less_sold_financial_securities_cr_not_expense"] == 0.0
    assert t[
        "financing_lease_dividend_interest_paid_total_cr_not_recurring_FCF"
    ] == 213.806
    assert a[
        "selected_inventory_receivables_payables_cash_movement_cr_not_total_WC"
    ] == -109.0133
    assert e[
        "selected_inventory_receivables_payables_cash_movement_cr_not_total_WC"
    ] == -24.02
    assert t[
        "selected_inventory_receivables_payables_cash_movement_cr_not_total_WC"
    ] == -155.112


def test_missing_or_corrupted_original_row_fails_closed_without_repricing():
    raw = _original("ACUTAAS")
    assert b"29,217.36" in raw
    replaced = raw.replace(b"29,217.36", b"99,999.99", 1)
    with pytest.raises(AlphaContractError, match="source FY26 number differs"):
        extract_exact_fy26_cells(replaced, "ACUTAAS")
    # Deleting a number must be a source absence, never silently imputed.
    removed = raw.replace(b"29,217.36", b"no-longer-original", 1)
    with pytest.raises(AlphaContractError, match="missing or duplicated"):
        extract_exact_fy26_cells(removed, "ACUTAAS")
    missing = copy.deepcopy(build_original_fy26_cash_use(ROOT))
    missing["symbol_records"][0]["live_capital_allowed"] = True
    with pytest.raises(AlphaContractError, match="signature changed"):
        verify_original_fy26_cash_use(missing, root=ROOT)


def test_operating_interest_zero_cannot_replace_actual_financing_interest():
    raw = _original("ACE")
    parsed = _row_values(raw)
    assert parsed[("operating", "interest paid")][0] == 0
    assert parsed[("financing", "interest paid")][0] == 1261
    selected = extract_exact_fy26_cells(raw, "ACE")
    assert selected["interest_paid"] == 1261
    assert selected["lease_paid"] == 145
    assert selected["dividends_paid"] == 2380


def test_deterministic_materializer_requires_identical_original_source_bytes():
    report = build_original_fy26_cash_use(ROOT)
    assert json.loads(OUTPUT.read_text(encoding="utf-8")) == report
    result = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p013.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    status = json.loads(result.stdout)
    assert status["state"] == "REPLAY_VERIFIED"
    assert status["source_cells"] == 51
    assert status["live_capital_allowed"] is False
