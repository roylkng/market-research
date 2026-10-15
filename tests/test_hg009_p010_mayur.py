"""P010 requires exact archived NSE statement, not a derived P/E or screenshot."""

from __future__ import annotations

import copy
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p010_mayur_cash import (
    CASH_ROWS_LAKH,
    OTHER_ASSET_BALANCE_ROWS,
    SOURCE_RAW,
    SOURCE_RAW_SHA256,
    build_mayur_cash_use_bridge,
    extract_original_financial_rows,
    validate_mayur_cash_use_bridge,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg009/hg009-p010-mayur-investing-cash-bridge-v1.json"


def test_original_nse_html_replays_cashflow_rows_and_arithmetic():
    result = build_mayur_cash_use_bridge(ROOT)
    assert result["company_symbol"] == "MAYURUNIQ"
    assert result["company_isin"] == "INE040D01038"
    assert result["original_period_end"] == "2026-03-31"
    assert result["pinned_original_byte_sha256"] == SOURCE_RAW_SHA256
    assert result["number_of_source_row_values_matched"] == (
        len(CASH_ROWS_LAKH) + len(OTHER_ASSET_BALANCE_ROWS)
    )
    assert result["fy26_cfo_cr"] == 133.1527
    assert result["fy26_ppe_cash_purchase_cr"] == 24.2071
    assert result["fy26_cfo_less_ppe_cr_not_fcf"] == 108.9456
    assert result["other_long_term_assets_purchase_cr"] == 266.2441
    assert result["other_long_term_assets_proceeds_cr"] == 160.3842
    assert result["other_long_term_assets_net_cash_placement_cr"] == 105.8599
    assert result[
        "residual_cfo_less_ppe_less_net_asset_placement_cr_not_owner_fcf"
    ] == 3.0857
    assert result["fy26_cash_after_all_investing_cr"] == 18.1056
    assert result[
        "fy26_cash_after_all_investing_and_financing_before_fx_cr"
    ] == -5.6673
    assert result["reported_cash_fx_effect_cr"] == 1.702
    assert result["reported_change_cash_after_fx_cr"] == -3.9653
    assert result["cashflow_beginning_cash_cr"] == 83.1003
    assert result["cashflow_ending_cash_cr"] == 79.135
    assert result["original_balance_sheet_investments_and_deposits_cr"] == {
        "current_investments": 176.8723,
        "noncurrent_investments": 108.0728,
        "noncurrent_long_deposits": 73.55,
    }
    validate_mayur_cash_use_bridge(result, ROOT)


def test_dont_call_cash_placements_expense_or_equity_fcf():
    data = build_mayur_cash_use_bridge(ROOT)
    for key in (
        "other_long_term_asset_placement_is_an_irreversible_expense",
        "asset_buy_and_sell_proceeds_are_full_bank_reconciliation",
        "reported_residual_is_normalized_owner_free_cash",
        "restricted_vs_unrestricted_investments_verified",
        "future_cash_return_from_long_term_asset_purchases_established",
        "receivables_and_inventory_multi_year_reversal_verified",
        "balance_sheet_asset_note_crosswalk_verified",
        "current_equity_share_capital_and_dilution_verified",
        "source_has_any_prospective_equity_price_or_return",
        "investor_valuation_ready",
        "live_capital_allowed",
    ):
        assert data[key] is False
    assert data["expected_return"] is None
    assert data["reporting_basis"] == (
        "FY26_CONSOLIDATED_AUDITED_NOT_OWNER_EARNINGS"
    )


def test_source_cell_or_archived_issuer_tamper_cannot_pass():
    raw = gzip.decompress((ROOT / SOURCE_RAW).read_bytes())
    assert raw
    values = extract_original_financial_rows(raw)
    assert values["other_long_asset_purchase"] > values["other_long_asset_sale_proceeds"]
    altered = raw.replace(b"26,624.41", b"27,624.41", 1)
    assert altered != raw
    with pytest.raises(AlphaContractError, match="original"):
        extract_original_financial_rows(altered)

    broken = raw.replace(b"MAYURUNIQ", b"FAKE_WIN", 1)
    with pytest.raises(AlphaContractError, match="issuer/period mismatch"):
        extract_original_financial_rows(broken)


def test_packet_cannot_promote_synthetic_future_equity_return():
    observed = build_mayur_cash_use_bridge(ROOT)
    data = copy.deepcopy(observed)
    data["expected_return"] = 0.5
    with pytest.raises(AlphaContractError, match="report hash mismatch"):
        validate_mayur_cash_use_bridge(data, ROOT)
    data["report_sha256"] = digest({
        k: v for k, v in data.items() if k != "report_sha256"
    })
    with pytest.raises(AlphaContractError, match="no longer replays"):
        validate_mayur_cash_use_bridge(data, ROOT)


def test_bitwise_original_report_and_standalone_cli():
    actual = json.loads(REPORT.read_text(encoding="utf-8"))
    expected = build_mayur_cash_use_bridge(ROOT)
    assert actual == expected
    proc = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p010_mayur.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    status = json.loads(proc.stdout)
    assert status["status"] == "VERIFIED"
    assert status["report_sha256"] == expected["report_sha256"]
    assert status["live_capital_allowed"] is False
