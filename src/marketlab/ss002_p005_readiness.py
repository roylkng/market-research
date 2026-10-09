from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_p004_native import PILOT_DOCUMENT_IDS

GATE_ID = "SS002-P005-v1"
EXPECTED_P004_ID = "SS002-P004-NATIVE-8DOC-v1"
EXPECTED_P004_SHA = "03d8ae16dd642e8e107b62bdb03eb9dc7e178d0327d742586bc35b65de943ff3"

COMMON_GAPS = (
    "INDEPENDENT_SOURCE_PAGE_SEMANTIC_AUDIT",
    "POINT_IN_TIME_ISSUER_AND_SHARE_IDENTITY",
    "VERIFIED_CURRENT_FINANCIAL_AND_CAPITAL_BASELINE",
    "LIQUIDITY_SLIPPAGE_AND_PERMANENT_LOSS_REVIEW",
)

FAMILY_GAPS: dict[str, tuple[str, ...]] = {
    "SOURCE_VISUAL_REVIEW": (
        "ORIGINAL_NEWSPAPER_IMAGE_OR_OFFICIAL_VISUAL_NOTICE",
        "ECONOMIC_RELEVANCE_AND_TRANSACTION_TERMS_VERIFICATION",
    ),
    "PROCEDURAL_MONITOR": (
        "PRIMARY_EARLIER_ISSUE_OR_TRANSACTION_DOCUMENT",
        "ECONOMICALLY_NEW_VERSUS_REPEAT_DISCLOSURE",
    ),
    "COMPLETED_EVENT_IMPACT": (
        "DATE_OF_COMPLETION_AND_EXACT_SECURITY_OR_PRIVATE_INVESTEE_IDENTITY",
        "POST_EVENT_EQUITY_OR_INVESTMENT_AND_CASH_RECONCILIATION",
        "TAX_FEES_AND_EARNINGS_RECOGNITION",
    ),
    "ACQUISITION_DUE_DILIGENCE": (
        "AUDITED_TARGET_REVENUE_EBITDA_AND_CASH_CONVERSION",
        "PURCHASED_ASSETS_LIABILITIES_AND_CONTINGENT_OBLIGATIONS",
        "LEGAL_CLOSE_AND_CONDITIONS_PRECEDENT",
        "FINANCING_DEBT_COVENANTS_CONVERSION_AND_MINORITY_INTEREST",
        "ACQUISITION_INTEGRATION_AND_INCREMENTAL_RETURN_ON_CAPITAL",
    ),
    "TENDER_BUYBACK_DUE_DILIGENCE": (
        "RECORD_DATE_ELIGIBILITY_AND_TENDER_WINDOW",
        "ACCEPTANCE_RATIO_AND_DISTRIBUTION",
        "OFFICIAL_ENTRY_PRICE_AND_TAXES",
        "UNACCEPTED_SHARES_DOWNSIDE_AND_LIQUIDITY",
        "POST_BUYBACK_SHARE_COUNT",
    ),
    "RIGHTS_DILUTION_DUE_DILIGENCE": (
        "RENOUNCEABLE_ENTITLEMENT_VALUE_AND_TRADING",
        "APPLICATION_AND_FUTURE_PAYMENT_CALLS",
        "PRE_AND_POST_ISSUED_AND_PAID_UP_SHARE_DENOMINATOR",
        "PROMOTER_PARTICIPATION_AND_USE_OF_PROCEEDS",
        "OFFICIAL_CUM_EX_PRICE_AND_POST_RIGHTS_DOWNSIDE",
    ),
    "SCHEME_DUE_DILIGENCE": (
        "EXCHANGE_RATIO_AND_INDEPENDENT_VALUATION_REPORT",
        "GROUP_CROSS_HOLDING_AND_RELATED_PARTY_FAIRNESS",
        "SHAREHOLDER_CREDITOR_AND_REGULATORY_APPROVALS",
        "PRO_FORMA_BALANCE_SHEET_AND_CONTINGENT_LIABILITIES",
    ),
    "MANUAL_TRANSACTION_REVIEW": (
        "VERIFY_ACTUAL_TRANSACTION_ECONOMICS",
        "IDENTIFY_APPROVALS_AND_CURRENT_COMPLETION_STATE",
    ),
}

ACTIVE_RESEARCH_LANES = frozenset(
    {
        "ACQUISITION_DUE_DILIGENCE",
        "TENDER_BUYBACK_DUE_DILIGENCE",
        "RIGHTS_DILUTION_DUE_DILIGENCE",
        "SCHEME_DUE_DILIGENCE",
    }
)


def _route(case: dict[str, Any]) -> str:
    relevance = case.get("economic_relevance")
    families = case.get("transaction_families")
    stage = case.get("transaction_stage")
    if not isinstance(families, list):
        raise TypeError("SS002 P005 transaction_families must be list")
    if relevance == "UNKNOWN":
        return "SOURCE_VISUAL_REVIEW"
    if relevance == "PROCEDURAL_OR_NEWSPAPER_UPDATE":
        return "PROCEDURAL_MONITOR"
    if stage == "TRANSACTION_COMPLETED":
        return "COMPLETED_EVENT_IMPACT"
    if "ACQUISITION_INVESTMENT" in families:
        return "ACQUISITION_DUE_DILIGENCE"
    if "BUYBACK" in families:
        return "TENDER_BUYBACK_DUE_DILIGENCE"
    if "RIGHTS_ISSUE" in families:
        return "RIGHTS_DILUTION_DUE_DILIGENCE"
    if "SCHEME_REORGANISATION" in families:
        return "SCHEME_DUE_DILIGENCE"
    return "MANUAL_TRANSACTION_REVIEW"


def build_transaction_readiness(p004: dict[str, Any]) -> dict[str, Any]:
    if p004.get("pilot_id") != EXPECTED_P004_ID:
        raise AlphaContractError("SS002 P005 P004 pilot id mismatch")
    if p004.get("pilot_sha256") != EXPECTED_P004_SHA:
        raise AlphaContractError("SS002 P005 frozen P004 pilot SHA mismatch")
    if p004.get("selected_document_count") != 8 or p004.get(
        "structurally_validated_document_count"
    ) != 8:
        raise AlphaContractError("SS002 P005 requires eight validated source cases")
    if p004.get("independently_semantically_audited_document_count") != 0:
        raise AlphaContractError("SS002 P005 cannot assume passed independent audit")
    for field in (
        "return_outcomes_opened",
        "market_capitalization_calculated",
        "share_action_clearance_proven",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if p004.get(field) is not False:
            raise AlphaContractError(f"SS002 P005 input requires {field}=false")
    cases = p004.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise AlphaContractError("SS002 P005 requires all eight case summaries")
    if tuple(row.get("document_id") for row in cases) != PILOT_DOCUMENT_IDS:
        raise AlphaContractError("SS002 P005 document identity/order mismatch")

    rows = []
    seen_symbols_and_docs: set[tuple[str, str]] = set()
    for case in cases:
        symbol = case.get("symbol")
        doc_id = case.get("document_id")
        if not isinstance(symbol, str) or not symbol or not isinstance(doc_id, str):
            raise AlphaContractError("SS002 P005 case identity is invalid")
        if (symbol, doc_id) in seen_symbols_and_docs:
            raise AlphaContractError("SS002 P005 duplicate case")
        seen_symbols_and_docs.add((symbol, doc_id))
        if case.get("semantic_audit_status") != "PENDING_INDEPENDENT_SOURCE_REVIEW":
            raise AlphaContractError("SS002 P005 semantics are not independently audited")

        lane = _route(case)
        rows.append(
            {
                "symbol": symbol,
                "document_id": doc_id,
                "case_assessment": case.get("case_assessment"),
                "transaction_families": case.get("transaction_families"),
                "transaction_stage": case.get("transaction_stage"),
                "economic_relevance": case.get("economic_relevance"),
                "research_lane": lane,
                "active_transaction_research_lens": lane in ACTIVE_RESEARCH_LANES,
                "unverified_evidence_requirements": list(COMMON_GAPS + FAMILY_GAPS[lane]),
                "independent_semantic_audit": "PENDING",
                "underwriting_ready": False,
                "expected_return_modeled": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )
    counts = Counter(row["research_lane"] for row in rows)
    output = {
        "schema_version": 1,
        "gate_id": GATE_ID,
        "classification": "POST_LLM_EVIDENCE_GAP_RESEARCH_ROUTING_NOT_ALPHA",
        "source_p004_id": EXPECTED_P004_ID,
        "source_p004_sha256": EXPECTED_P004_SHA,
        "case_count": len(rows),
        "active_transaction_research_lens_count": sum(
            row["active_transaction_research_lens"] for row in rows
        ),
        "underwriting_ready_count": 0,
        "research_lane_counts": dict(sorted(counts.items())),
        "cases": rows,
        "independent_semantic_audit_complete": False,
        "return_outcomes_opened": False,
        "market_capitalization_calculated": False,
        "share_action_clearance_proven": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["gate_sha256"] = digest(output)
    return output
