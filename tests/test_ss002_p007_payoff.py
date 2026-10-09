from __future__ import annotations

import csv
import io
import zipfile

from marketlab.alpha import AlphaContractError
from marketlab.ss002_p007_payoff import (
    P006_SHA,
    build_p007_price_scenarios,
    rights_theoretical_surface,
    tender_payoff_surface,
)

import pytest


SYMBOLS = (
    "INOXGREEN", "KOTHARIPET", "OLAELEC", "PREMEXPLN", "PVRINOX",
    "SAMBHV", "TVSSRICHAK", "VRLLOG",
)


def _claim(path: str, value: object, unit: str) -> dict:
    return {
        "field_path": path,
        "extracted_value": value,
        "extracted_unit": unit,
        "citation_integrity_verified": True,
        "independent_semantic_verification": "PENDING",
    }


def _packet() -> dict:
    cases = []
    for i, symbol in enumerate(SYMBOLS):
        claims = []
        if symbol == "VRLLOG":
            claims = [
                _claim("security_economics.offer_price_per_share", 320, "INR_PER_SHARE"),
                _claim("security_economics.maximum_securities", 8750000, "EQUITY_SHARES"),
                _claim("consideration.total_consideration", 28000, "INR_LAKH"),
            ]
        if symbol == "OLAELEC":
            claims = [
                _claim("security_economics.issue_price_per_share", 27, "INR_PER_RIGHTS_SHARE"),
                _claim("ratios_entitlement.rights_entitlement_numerator", 2, "RIGHTS_SHARES"),
                _claim("ratios_entitlement.rights_entitlement_denominator", 25, "EXISTING_SHARES"),
                _claim("security_economics.number_of_securities", 370272665, "PARTLY_PAID_RIGHTS_SHARES"),
                _claim("consideration.total_consideration", 9997361955, "INR_ASSUMING_FULL_SUBSCRIPTION_AND_CALL"),
            ]
        cases.append(
            {
                "symbol": symbol,
                "isin": f"INE000000{i:03d}",
                "research_lane": "TENDER_BUYBACK_DUE_DILIGENCE" if symbol == "VRLLOG" else "RESEARCH_CONTEXT",
                "claims": claims,
            }
        )
    return {
        "pack_id": "SS002-P006-v1",
        "pack_sha256": P006_SHA,
        "case_count": 8,
        "explicit_fact_count": 52,
        "cases": cases,
        "independent_semantic_audit_complete": False,
        "current_entry_prices_verified": False,
        "share_action_clearance_proven": False,
        "expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _zip_bhavcopy() -> bytes:
    header = [
        "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb",
        "SctySrs", "OpnPric", "HghPric", "LwPric", "ClsPric",
        "PrvsClsgPric", "TtlTradgVol", "TtlTrfVal", "TtlNbOfTxsExctd",
    ]
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(header)
    for i, symbol in enumerate(SYMBOLS):
        price = 280.0 if symbol == "VRLLOG" else 35.0
        writer.writerow(
            [
                "2026-10-09", "CM", "NSE", "STK", f"INE000000{i:03d}",
                symbol, "EQ", price, price + 1, price - 1, price,
                price, 10000, 1_000_000, 200,
            ]
        )
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w") as archive:
        archive.writestr("BhavCopy.csv", stream.getvalue().encode())
    return zipped.getvalue()


def test_tender_payoff_is_conditional_and_breakeven_is_consistent() -> None:
    p = tender_payoff_surface(purchase_price=280, buyback_price=320)
    assert p["fully_accepted_gross_tender_premium_pct_before_all_costs"] == pytest.approx(
        (320 / 280 - 1) * 100
    )
    cell = next(
        x for x in p["hypothetical_scenarios"]
        if x["acceptance_fraction_hypothetical"] == 0.5
        and x["residual_price_multiple_hypothetical"] == 0.85
    )
    assert cell["gross_cash_proceeds_per_initial_share_inr"] == pytest.approx(279.0)
    assert cell["conditional_gross_price_change_pct_before_all_costs"] < 0
    assert cell["breakeven_acceptance"]["minimum_fraction"] == pytest.approx(42 / 82)
    assert p["acceptance_distribution_estimated"] is False


def test_rights_theoretical_formula_and_future_calls_not_inferred() -> None:
    r = rights_theoretical_surface(
        cum_rights_price=35,
        fully_paid_issue_price=27,
        rights_shares=2,
        existing_shares=25,
    )
    assert r["theoretical_ex_rights_price_inr"] == pytest.approx(929 / 27)
    assert r["existing_share_entitlement_value_inr"] == pytest.approx(35 - 929 / 27)
    assert r["partly_paid_cash_calls_verified"] is False
    assert r["investment_return_estimated"] is False


def test_out_of_money_rights_have_no_negative_entitlement() -> None:
    r = rights_theoretical_surface(
        cum_rights_price=24,
        fully_paid_issue_price=27,
        rights_shares=2,
        existing_shares=25,
    )
    assert r["state"] == "NO_POSITIVE_THEORETICAL_IN_THE_MONEY_EXERCISE_VALUE"
    assert r["existing_share_entitlement_value_inr"] == 0


def test_realization_keeps_all_eight_and_no_expected_return() -> None:
    result = build_p007_price_scenarios(_packet(), udiff_raw=_zip_bhavcopy())
    assert result["identity_count"] == 8
    assert result["matched_price_count"] == 8
    assert result["mechanical_scenario_count"] == 2
    assert result["feasibility_pass"] is True
    rows = {x["symbol"]: x for x in result["rows"]}
    assert rows["VRLLOG"]["scenario_family"] == "TENDER_BUYBACK"
    assert rows["OLAELEC"]["scenario_family"] == "PARTLY_PAID_RIGHTS_ISSUE"
    assert rows["INOXGREEN"]["conditional_mechanics"] is None
    assert result["future_holding_period_return_outcomes_opened"] is False
    assert result["post_announcement_price_observed"] is True
    assert result["portfolio_eligibility_allowed"] is False


def test_frozen_claim_inconsistency_fails_closed() -> None:
    packet = _packet()
    vrllog = next(x for x in packet["cases"] if x["symbol"] == "VRLLOG")
    vrllog["claims"][2]["extracted_value"] = 29000
    with pytest.raises(AlphaContractError, match="buyback terms contradict"):
        build_p007_price_scenarios(packet, udiff_raw=_zip_bhavcopy())


def test_invalid_frozen_packet_refuses_calculation() -> None:
    packet = _packet()
    packet["pack_sha256"] = "wrong"
    with pytest.raises(AlphaContractError, match="frozen P006 packet"):
        build_p007_price_scenarios(packet, udiff_raw=_zip_bhavcopy())


def test_unverified_semantic_label_cannot_be_marked_approved() -> None:
    packet = _packet()
    ol = next(x for x in packet["cases"] if x["symbol"] == "OLAELEC")
    ol["claims"][0]["independent_semantic_verification"] = "APPROVED"
    with pytest.raises(AlphaContractError, match="term provenance is invalid"):
        build_p007_price_scenarios(packet, udiff_raw=_zip_bhavcopy())
