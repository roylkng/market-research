from __future__ import annotations

from marketlab.hg004_l002 import (
    EXPECTED_RUN_SHA,
    build_transaction_term_synthesis,
)
from marketlab.ss002_llm_contract import empty_fact_tree


def _explicit(facts: dict, family: str, field: str, value) -> None:
    facts[family][field] = {
        "status": "EXPLICIT",
        "value": value,
        "unit": "TEST",
        "evidence_segment_ids": ["seg:1"],
    }


def _row(
    symbol: str,
    document_id: str,
    *,
    families: list[str],
    stage: str,
    relevance: str = "DIRECT_LISTED_SECURITY",
    explicit: list[tuple[str, str, object]] | None = None,
    caveats: list[str] | None = None,
) -> dict:
    facts = empty_fact_tree()
    for family, field, value in explicit or []:
        _explicit(facts, family, field, value)
    return {
        "document_id": document_id,
        "symbols": [symbol],
        "validated_extraction": {
            "economic_relevance": relevance,
            "transaction_families": families,
            "transaction_stage": stage,
            "facts": facts,
            "extraction_caveats": list(caveats or []),
        },
    }


def _run() -> dict:
    rows = [
        _row(
            "ANANTRAJ",
            "a1",
            families=["SCHEME_REORGANISATION"],
            stage="BOARD_APPROVED",
            explicit=[
                (
                    "ratios_entitlement",
                    "exchange_ratio_text",
                    "1 Ashok Cloud share for every 1 Anant Raj share",
                ),
                (
                    "business_economics",
                    "asset_or_business_description",
                    "Data Center Business demerged to a resulting company",
                ),
            ],
        ),
        _row(
            "ANANTRAJ",
            "a2",
            families=["SCHEME_REORGANISATION"],
            stage="BOARD_APPROVED",
            explicit=[
                (
                    "business_economics",
                    "stated_transaction_rationale",
                    "Create two focused listed companies",
                )
            ],
        ),
        _row(
            "AXITA",
            "x1",
            families=["INSOLVENCY_RESOLUTION", "ACQUISITION_INVESTMENT"],
            stage="PROPOSAL",
            relevance="LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
            explicit=[
                (
                    "business_economics",
                    "asset_or_business_description",
                    "Cotton yarn manufacturing unit",
                )
            ],
        ),
        _row(
            "DATAMATICS",
            "d1",
            families=["SCHEME_REORGANISATION"],
            stage="BOARD_APPROVED",
            explicit=[
                (
                    "consideration",
                    "non_cash_consideration_description",
                    "Wholly owned subsidiary merger with no new shares",
                ),
                (
                    "ratios_entitlement",
                    "exchange_ratio_text",
                    "No share exchange ratio applies because both are wholly owned",
                ),
            ],
        ),
        _row(
            "DEVX",
            "v1",
            families=["PREFERENTIAL_WARRANT", "FUND_RAISE_OTHER"],
            stage="ALLOTMENT_COMPLETED",
            explicit=[
                ("security_economics", "issue_price_per_share", 45),
                (
                    "security_economics",
                    "number_of_securities",
                    "44m shares plus 33m warrants",
                ),
            ],
        ),
        _row(
            "DEVX",
            "v2",
            families=["PREFERENTIAL_WARRANT", "FUND_RAISE_OTHER"],
            stage="REGULATORY_OR_COURT_APPROVED",
            explicit=[
                ("security_economics", "number_of_securities", "33m warrants")
            ],
        ),
        _row(
            "DEVX",
            "v3",
            families=["PREFERENTIAL_WARRANT", "FUND_RAISE_OTHER"],
            stage="PROCEDURAL_UPDATE",
            explicit=[
                (
                    "business_economics",
                    "stated_use_of_proceeds",
                    "Refundable lease security deposit",
                ),
                (
                    "business_economics",
                    "capacity_or_operating_metric_disclosed",
                    "450,000 sq ft centre",
                ),
            ],
        ),
        _row(
            "FCL",
            "f1",
            families=["PREFERENTIAL_WARRANT", "FUND_RAISE_OTHER"],
            stage="PROCEDURAL_UPDATE",
            explicit=[
                (
                    "business_economics",
                    "stated_use_of_proceeds",
                    "Final utilization report",
                )
            ],
            caveats=["This is a final monitoring-agency report and not a fresh 2026 issue."],
        ),
        _row(
            "FCL",
            "f2",
            families=["PREFERENTIAL_WARRANT", "FUND_RAISE_OTHER"],
            stage="PROCEDURAL_UPDATE",
            explicit=[
                (
                    "business_economics",
                    "stated_use_of_proceeds",
                    "Final utilization report",
                )
            ],
            caveats=["This is not a fresh warrant issuance."],
        ),
        _row(
            "INOXGREEN",
            "i1",
            families=["INSOLVENCY_RESOLUTION", "ACQUISITION_INVESTMENT"],
            stage="REGULATORY_OR_COURT_APPROVED",
            relevance="LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
            explicit=[
                ("consideration", "total_consideration", 550),
                (
                    "business_economics",
                    "asset_or_business_description",
                    "WWIL O&M business",
                ),
                (
                    "business_economics",
                    "capacity_or_operating_metric_disclosed",
                    "4.5GW O&M portfolio",
                ),
                (
                    "conditions_approvals",
                    "approvals_required",
                    "Subject to plan and IMC approval",
                ),
            ],
        ),
        _row(
            "INOXGREEN",
            "i2",
            families=["INSOLVENCY_RESOLUTION", "ACQUISITION_INVESTMENT"],
            stage="REGULATORY_OR_COURT_APPROVED",
            relevance="LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
            explicit=[
                (
                    "business_economics",
                    "asset_or_business_description",
                    "WWIL businesses",
                )
            ],
        ),
        _row(
            "INOXGREEN",
            "i3",
            families=["SCHEME_REORGANISATION"],
            stage="REGULATORY_OR_COURT_APPROVED",
            explicit=[
                (
                    "ratios_entitlement",
                    "exchange_ratio_text",
                    "122 Resco shares for every 2000 Inox Green shares",
                ),
                (
                    "business_economics",
                    "asset_or_business_description",
                    "Demerger of Power Evacuation Business",
                ),
            ],
        ),
        _row(
            "NPST",
            "n1",
            families=["FUND_RAISE_OTHER"],
            stage="PROCEDURAL_UPDATE",
            explicit=[
                ("consideration", "total_consideration", 300),
                (
                    "business_economics",
                    "stated_use_of_proceeds",
                    "Expansion, product development and acquisitions",
                ),
                (
                    "business_economics",
                    "capacity_or_operating_metric_disclosed",
                    "INR277.86cr unutilized",
                ),
            ],
        ),
        _row(
            "SAMBHV",
            "s1",
            families=["PREFERENTIAL_WARRANT"],
            stage="BOARD_APPROVED",
            explicit=[
                ("security_economics", "issue_price_per_share", 115),
                ("security_economics", "number_of_securities", 8695400),
            ],
        ),
        _row(
            "SAMBHV",
            "s2",
            families=["PREFERENTIAL_WARRANT"],
            stage="PROCEDURAL_UPDATE",
            explicit=[
                ("security_economics", "issue_price_per_share", 115),
                ("security_economics", "number_of_securities", 8695400),
            ],
        ),
        _row(
            "SANDESH",
            "h1",
            families=["SCHEME_REORGANISATION"],
            stage="BOARD_APPROVED",
            explicit=[
                (
                    "consideration",
                    "non_cash_consideration_description",
                    "Wholly owned subsidiary merger with no consideration",
                ),
                (
                    "ratios_entitlement",
                    "exchange_ratio_text",
                    "No share exchange ratio because transferor is wholly owned",
                ),
            ],
        ),
        _row(
            "SUVIDHAA",
            "u1",
            families=["RIGHTS_ISSUE"],
            stage="BOARD_APPROVED",
            explicit=[("consideration", "total_consideration", 12)],
        ),
        _row(
            "TREL",
            "t1",
            families=["SCHEME_REORGANISATION"],
            stage="BOARD_APPROVED",
            explicit=[
                (
                    "consideration",
                    "non_cash_consideration_description",
                    "No consideration for wholly owned subsidiary merger",
                ),
                (
                    "ratios_entitlement",
                    "exchange_ratio_text",
                    "No share exchange ratio",
                ),
            ],
        ),
        _row(
            "TREL",
            "t2",
            families=["SCHEME_REORGANISATION"],
            stage="PROCEDURAL_UPDATE",
            explicit=[
                (
                    "consideration",
                    "non_cash_consideration_description",
                    "Wholly owned subsidiary procedural merger",
                ),
                (
                    "ratios_entitlement",
                    "exchange_ratio_text",
                    "No share exchange ratio",
                ),
            ],
        ),
    ]
    assert len(rows) == 19
    return {
        "run_id": "HG004-L001-GPT56SOL-NATIVE-v1",
        "run_sha256": EXPECTED_RUN_SHA,
        "validated_output_count": 19,
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_frozen_11_company_readiness_states() -> None:
    result = build_transaction_term_synthesis(_run())
    states = {
        row["symbol"]: row["primary_readiness_state"]
        for row in result["rows"]
    }
    assert states == {
        "ANANTRAJ": "READY_DEMERGER_ENTITLEMENT",
        "AXITA": "PARTIAL_ACQUISITION_TERMS_REQUIRED",
        "DATAMATICS": "PROCEDURAL_INTERNAL_REORGANISATION",
        "DEVX": "READY_DILUTION_FINANCING",
        "FCL": "HISTORICAL_FINANCING_MONITOR",
        "INOXGREEN": "READY_ACQUISITION_ECONOMICS",
        "NPST": "READY_CAPITAL_DEPLOYMENT_MONITOR",
        "SAMBHV": "READY_DILUTION_FINANCING",
        "SANDESH": "PROCEDURAL_INTERNAL_REORGANISATION",
        "SUVIDHAA": "PARTIAL_RIGHTS_TERMS_REQUIRED",
        "TREL": "PROCEDURAL_INTERNAL_REORGANISATION",
    }
    assert result["symbol_count"] == 11
    assert result["payoff_model_ready_symbol_count"] == 5
    assert result["partial_terms_symbol_count"] == 2
    assert result["procedural_or_historical_symbol_count"] == 4
    assert result["portfolio_eligibility_allowed"] is False


def test_inoxgreen_keeps_independent_acquisition_and_demerger_lanes() -> None:
    result = build_transaction_term_synthesis(_run())
    inox = next(row for row in result["rows"] if row["symbol"] == "INOXGREEN")
    states = {
        lane["readiness_state"] for lane in inox["payoff_model_lanes"]
    }
    assert "READY_ACQUISITION_ECONOMICS" in states
    assert "READY_DEMERGER_ENTITLEMENT" in states


def test_partial_cases_expose_missing_terms_without_inference() -> None:
    result = build_transaction_term_synthesis(_run())
    by_symbol = {row["symbol"]: row for row in result["rows"]}
    axita = by_symbol["AXITA"]["payoff_model_lanes"][0]
    assert "FINAL_PURCHASE_PRICE_OR_ADJUSTMENTS" in axita["missing_inputs"]
    suvidhaa = by_symbol["SUVIDHAA"]["payoff_model_lanes"][0]
    assert "RIGHTS_ISSUE_PRICE" in suvidhaa["missing_inputs"]
    assert "RIGHTS_ENTITLEMENT_RATIO" in suvidhaa["missing_inputs"]
