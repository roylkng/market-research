from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_size import (
    build_company_size_panel,
    parse_trade_info_market_cap,
    size_band,
)


def test_trade_info_market_cap_parser_uses_official_fields() -> None:
    payload = {
        "marketDeptOrderBook": {
            "tradeInfo": {
                "totalMarketCap": 8750.25,
                "ffmc": 3200.5,
            }
        }
    }
    result = parse_trade_info_market_cap(
        payload,
        symbol="TEST",
        raw=b'{"marketDeptOrderBook":{}}',
    )
    assert result["status"] == "READY"
    assert result["total_market_cap_inr_crore"] == pytest.approx(8750.25)
    assert result["free_float_market_cap_inr_crore"] == pytest.approx(3200.5)


def test_trade_info_rejects_ffmc_above_total_cap() -> None:
    payload = {
        "marketDeptOrderBook": {
            "tradeInfo": {
                "totalMarketCap": 1000.0,
                "ffmc": 1100.0,
            }
        }
    }
    with pytest.raises(ValueError, match="ffmc exceeds"):
        parse_trade_info_market_cap(payload, symbol="TEST", raw=b"{}")


def test_frozen_size_bands() -> None:
    assert size_band(499.9) == "S1_BELOW_500CR"
    assert size_band(500.0) == "S2_500_TO_1000CR"
    assert size_band(1000.0) == "S3_1000_TO_2500CR"
    assert size_band(2500.0) == "S4_2500_TO_5000CR"
    assert size_band(5000.0) == "S5_5000_TO_10000CR"
    assert size_band(10000.0) == "S6_10000_TO_25000CR"
    assert size_band(25000.0) == "S7_25000CR_PLUS"
    assert size_band(None) == "SIZE_UNAVAILABLE"


def _census() -> dict:
    rows=[]
    for idx in range(2319):
        rows.append({
            "symbol":f"S{idx:04d}",
            "isin":f"INE{idx:09d}"[-12:],
            "company_name":f"Company {idx}",
            "in_existing_u001":idx<100,
            "market":{"median_daily_turnover_inr":10_000_000.0},
            "financial_source":{"has_integrated_financial_filing":True},
            "corporate_actions_1y":{
                "rights":1 if idx==0 else 0,
                "scheme_or_reorganisation":0,
                "buyback":0,
                "split_or_consolidation":0,
                "bonus":0,
                "delisting":0,
            },
        })
    return {
        "census_id":"SS001-D001-v1",
        "census_sha256":"0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7",
        "eq_identity_count":2319,
        "rows":rows,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }


def test_panel_preserves_every_identity_and_context() -> None:
    acquired=[]
    for idx in range(2319):
        acquired.append({
            "symbol":f"S{idx:04d}",
            "status":"READY",
            "total_market_cap_inr_crore":750.0,
            "free_float_market_cap_inr_crore":300.0,
            "raw_sha256":"a"*64,
            "error":None,
        })
    panel=build_company_size_panel(
        d001_census=_census(),
        acquired_rows=acquired,
        captured_at_utc="2026-10-04T12:00:00Z",
    )
    assert panel["identity_count"]==2319
    assert panel["ready_market_cap_count"]==2319
    assert panel["size_band_counts"]["S2_500_TO_1000CR"]==2319
    first=panel["rows"][0]
    assert first["has_special_action_1y"] is True
    assert first["portfolio_eligibility_allowed"] is False


def test_panel_fails_closed_on_wrong_source_hash() -> None:
    census=_census()
    census["census_sha256"]="wrong"
    with pytest.raises(AlphaContractError, match="census SHA mismatch"):
        build_company_size_panel(
            d001_census=census,
            acquired_rows=[],
            captured_at_utc="2026-10-04T12:00:00Z",
        )
