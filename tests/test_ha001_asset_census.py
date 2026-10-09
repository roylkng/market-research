from __future__ import annotations

import copy

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ha001_asset_census import (
    EXPECTED_COUNT,
    build_asset_anomaly_census,
)


def _fact(value: float | None, *, status: str = "READY", unit: str = "INR") -> dict:
    return {
        "status": status,
        "value": value,
        "unit_ref": unit,
        "selected_concept": "ConceptUnderTest",
        "context_refs": ["FY26_Instant"],
    }


def _annual(*, source_url: str = "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_TEST.xml") -> dict:
    return {
        "status": "READY",
        "parsed": {
            "period_end": "2026-03-31",
            "accounting_basis": "Consolidated",
            "source_url": source_url,
            "raw_sha256": "a" * 64,
            "facts": {
                "total_assets": _fact(100.0),
                "cash": _fact(40.0),
                "current_investments": _fact(20.0),
                "noncurrent_investments": _fact(20.0),
                "borrowings_current": _fact(10.0),
                "borrowings_noncurrent": _fact(5.0),
                "ppe": _fact(45.0),
                "capital_work_in_progress": _fact(15.0),
                "investment_property": _fact(5.0),
            },
        },
    }


def _panel() -> dict:
    rows = [
        {
            "symbol": f"T{i:04d}",
            "isin": f"INE{i:07d}01",
            "company_name": f"Company {i}",
            "in_existing_u001": False,
            "annual": _annual() if i == 0 else {"status": "NO_CANDIDATE"},
        }
        for i in range(EXPECTED_COUNT)
    ]
    return {
        "panel_id": "FA001-D002-v1",
        "panel_sha256": (
            "cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124"
        ),
        "source_ss001_census_sha256": (
            "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
        ),
        "identity_count": EXPECTED_COUNT,
        "rows": rows,
        "feasibility_pass": True,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_three_independent_flags_are_deterministic_and_source_only() -> None:
    result = build_asset_anomaly_census(_panel())
    assert result["identity_count"] == EXPECTED_COUNT
    assert result["any_signal_flagged_count"] == 1
    first = result["rows"][0]
    assert all(s["state"] == "FLAGGED" for s in first["signals"].values())
    assert first["signals"]["MATERIAL_FINANCIAL_SURPLUS_PROXY"]["ratio"] == pytest.approx(0.45)
    assert first["signals"]["MATERIAL_BOOK_INVESTMENTS"]["ratio"] == pytest.approx(0.40)
    assert first["signals"]["TANGIBLE_CAPITAL_CONCENTRATION"]["ratio"] == pytest.approx(0.65)
    assert result["market_capitalization_calculated"] is False
    assert result["return_outcomes_opened"] is False
    assert result["live_capital_allowed"] is False
    assert "target_price" not in first


def test_missing_fact_is_never_imputed_to_zero() -> None:
    panel = _panel()
    annual = panel["rows"][0]["annual"]["parsed"]["facts"]
    annual["cash"] = _fact(None, status="MISSING")
    result = build_asset_anomaly_census(panel)
    first = result["rows"][0]
    assert first["signals"]["MATERIAL_FINANCIAL_SURPLUS_PROXY"]["state"] == "MISSING_REQUIRED_FACT"
    assert first["signals"]["MATERIAL_BOOK_INVESTMENTS"]["state"] == "FLAGGED"


def test_non_inr_or_negative_balances_cannot_be_flagged() -> None:
    panel = _panel()
    annual = panel["rows"][0]["annual"]["parsed"]["facts"]
    annual["cash"] = _fact(40, unit="USD")
    annual["ppe"] = _fact(-45)
    result = build_asset_anomaly_census(panel)
    first = result["rows"][0]["signals"]
    assert first["MATERIAL_FINANCIAL_SURPLUS_PROXY"]["state"] == "INVALID_NUMERIC_OR_UNIT"
    assert first["TANGIBLE_CAPITAL_CONCENTRATION"]["state"] == "INVALID_NUMERIC_OR_UNIT"


def test_nbfc_taxonomy_cannot_be_treated_like_industrial_cash() -> None:
    panel = _panel()
    panel["rows"][0]["annual"] = _annual(
        source_url=(
            "https://nsearchives.nseindia.com/corporate/xbrl/"
            "INTEGRATED_FILING_NBFC_INDAS_EXAMPLE_WEB.xml"
        )
    )
    result = build_asset_anomaly_census(panel)
    assert all(
        signal["state"] == "FINANCIAL_SECTOR_NOT_COMPARABLE"
        for signal in result["rows"][0]["signals"].values()
    )
    assert result["any_signal_flagged_count"] == 0


def test_thresholds_do_not_promote_small_positive_balances() -> None:
    panel = _panel()
    annual = panel["rows"][0]["annual"]["parsed"]["facts"]
    annual["cash"] = _fact(12.0)
    annual["current_investments"] = _fact(1.0)
    annual["noncurrent_investments"] = _fact(1.0)
    annual["ppe"] = _fact(5.0)
    annual["capital_work_in_progress"] = _fact(0.0)
    annual["investment_property"] = _fact(0.0)
    result = build_asset_anomaly_census(panel)
    assert all(signal["state"] == "NOT_FLAGGED" for signal in result["rows"][0]["signals"].values())


def test_fails_closed_on_panel_or_identity_mutation() -> None:
    panel = _panel()
    panel["panel_sha256"] = "changed"
    with pytest.raises(AlphaContractError, match="panel SHA"):
        build_asset_anomaly_census(panel)

    panel = _panel()
    panel["rows"][1]["symbol"] = panel["rows"][0]["symbol"]
    with pytest.raises(AlphaContractError, match="duplicated"):
        build_asset_anomaly_census(panel)

    panel = _panel()
    panel["return_outcomes_opened"] = True
    with pytest.raises(AlphaContractError, match="return_outcomes_opened=false"):
        build_asset_anomaly_census(panel)


def test_results_are_deterministic_when_source_order_changes() -> None:
    panel = _panel()
    first = build_asset_anomaly_census(panel)
    reversed_panel = copy.deepcopy(panel)
    reversed_panel["rows"].reverse()
    second = build_asset_anomaly_census(reversed_panel)
    assert second["census_sha256"] == first["census_sha256"]
