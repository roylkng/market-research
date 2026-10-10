"""Source-pinned underwriting casework for the frozen 28-name HG002 cohort.

This is an *evidence acquisition queue*, not a ranking of expected stock
returns. In particular, a completed warrant issuance is not completed
business deployment; historical unconditional base rates cannot stand in
for a case-specific completion probability.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_BLOBS = {
    "HG002_COHORT": (
        "research/hg002-d001-result-v1.json",
        "e4313bd333595fce068dc8fd0882dec16f2ec8b6",
    ),
    "HG003_CURRENT_STAGE": (
        "research/hg003-l002-result-v1.json",
        "de7841d248770c7e94943df6e5c79edd99c29c53",
    ),
    "HG004_TERMS": (
        "research/hg004-d001-result-v1.json",
        "bd2864718e13f445415298b0beb0eb92c3c0d06c",
    ),
    "HG005_MARKET": (
        "research/hg005-d001-result-v1.json",
        "2dbbc3055d1aacec8a37dd510a1a75a3c7868006",
    ),
    "HG005_PAYOFF": (
        "research/hg005-d003-result-v1.json",
        "b235bd9168bc658f7511f9cec1913f20f82cf311",
    ),
    "HG006_CURRENT_BASE_RATE": (
        "research/hg006-p001-result-v1.json",
        "2c13d5424c0f88af1bd0deeec559c60f190f464b",
    ),
    "SS002_OCTOBER_CASES": (
        "research/ss002-p005-result-v1.json",
        "a4e0a63c42f6ca66218794377f8c65aaebe47d07",
    ),
}

ROLE_FIELDS = {
    "ACTIVE_DIRECT_CATALYST": "active_direct_catalyst_symbols",
    "PROCEDURAL_DIRECT_REVIEW": "procedural_direct_review_symbols",
    "COMPLETED_DIRECT_EVENT_ONLY": "completed_direct_event_only_symbols",
    "CANCELLED_DIRECT_EVENT_ONLY": "cancelled_direct_event_only_symbols",
    "INDIRECT_OR_CONTEXT_ONLY": "indirect_or_context_only_symbols",
    "TEXT_PENDING": "text_pending_symbols",
}

# Requirements, not inferred document facts or expected stock returns.
RESEARCH_REQUESTS = {
    "ANANTRAJ": (
        "SEPARATED_BUSINESS_AUDITED_EARNINGS_AND_CASH_CONVERSION",
        "TRANSFERRED_NET_DEBT_LIABILITIES_AND_MINORITY_CLAIMS",
        "EFFECTIVE_DEMERGER_AND_ALLOTMENT_TIMELINE",
    ),
    "DEVX": (
        "WINSTON_450000_SQFT_REALIZED_EBITDA_AND_OCCUPANCY",
        "WARRANT_FULL_ECONOMIC_EXERCISE_AND_FD_DENOMINATOR",
        "INCREMENTAL_CAPEX_DEBT_CASH_AND_WORKING_CAPITAL_BRIDGE",
    ),
    "INOXGREEN": (
        "WWIL_NORMALIZED_EBITDA_CASH_FLOW_AND_CONTINGENT_OBLIGATIONS",
        "ACQUISITION_PURCHASE_PRICE_FUNDING_AND_DEBT_STRUCTURE",
        "SEPARATED_BUSINESS_EARNINGS_AND_LEGAL_EFFECTIVENESS",
        "RECONCILE_OCTOBER_2026_NEWER_CASE_WITH_OCT04_STAGE_EVIDENCE",
    ),
    "NPST": (
        "PROCEEDS_DEPLOYMENT_TO_VERIFIABLE_ADDITIONAL_EBITDA",
        "SUSTAINABLE_FY27_QUARTERLY_EARNINGS_AND_CASH_CONVERSION",
        "CURRENT_FULLY_DILUTED_SHARES_AND_CLEAN_PRICE_BASIS",
    ),
    "SAMBHV": (
        "PHASE_I_0_36_MMTPA_COMMISSIONING_AND_VERIFIED_CAPEX_SPEND",
        "REALIZED_CAPACITY_UTILIZATION_AND_EBITDA_PER_TONNE",
        "WARRANT_ISSUANCE_EXERCISE_DILUTION_AND_FINANCING",
        "RECONCILE_OCTOBER_2026_PROCEDURAL_NOTICE_WITH_JULY_STAGE",
    ),
}

RESEARCH_ROUTE_ORDER = {
    "SOURCE_INCOMPLETE_OR_EQUITY_BRIDGE_BLOCKED": 0,
    "SENSITIVITY_OR_REVERSE_HURDLE_NOT_PROVEN_EARNINGS": 1,
    "LIVE_TRANSACTION_WITHOUT_CASE_PAYOFF_MODEL": 2,
    "NONLIVE_FROZEN_COHORT_RETAINED_FOR_FUNDAMENTALS": 3,
}
BOARD_ID = "HG007-P001-EVIDENCE-ACQUISITION-BOARD-v1"


def _git_blob_sha(raw: bytes) -> str:
    data = b"blob " + str(len(raw)).encode() + b"\0" + raw
    return hashlib.sha1(data, usedforsecurity=False).hexdigest()


def load_exact_sources(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict]]:
    sources: dict[str, dict[str, Any]] = {}
    receipts: dict[str, dict] = {}
    for name, (raw_path, expected_git_sha) in SOURCE_BLOBS.items():
        path = root / raw_path
        raw = path.read_bytes()
        actual = _git_blob_sha(raw)
        if actual != expected_git_sha:
            raise ValueError(f"{name}: pinned Git source blob drifted")
        content = json.loads(raw)
        if not isinstance(content, dict):
            raise TypeError(f"{name}: source JSON root is not an object")
        if content.get("schema_version") != 1:
            raise ValueError(f"{name}: original research schema must remain v1")
        if content.get("return_outcomes_opened") is True:
            raise ValueError(f"{name}: source unexpectedly opened return labels")
        if content.get("live_capital_allowed") is not False:
            raise ValueError(f"{name}: original source cannot authorize capital")
        sources[name] = content
        receipts[name] = {
            "path": raw_path,
            "git_blob_sha": actual,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return sources, receipts


def build_casework_board(sources: dict[str, dict], receipts: dict[str, dict]) -> dict:
    needed = set(SOURCE_BLOBS)
    if set(sources) != needed or set(receipts) != needed:
        raise ValueError("HG007 requires exact seven immutable source families")
    cohort = sources["HG002_COHORT"]
    thread = sources["HG003_CURRENT_STAGE"]
    terms = sources["HG004_TERMS"]
    market = sources["HG005_MARKET"]
    payoff = sources["HG005_PAYOFF"]
    base_rate = sources["HG006_CURRENT_BASE_RATE"]
    october = sources["SS002_OCTOBER_CASES"]

    originals = cohort.get("symbols")
    if (
        cohort.get("cohort_count") != 28
        or not isinstance(originals, list)
        or len(originals) != 28
        or len(set(originals)) != 28
    ):
        raise ValueError("HG002 original mechanically selected 28 identities changed")
    role: dict[str, str] = {}
    for state, field in ROLE_FIELDS.items():
        values = thread.get(field)
        if not isinstance(values, list):
            raise TypeError(f"HG003 stage list is missing: {state}")
        for symbol in values:
            if symbol in role:
                raise ValueError(f"HG003 assigned multiple special-situation states: {symbol}")
            role[symbol] = state
    if set(originals) != set(role) or thread.get("symbol_count") != 28:
        raise ValueError("HG003 lost or substituted an HG002 selected company")
    direct = {
        symbol for symbol in originals
        if role[symbol] in {"ACTIVE_DIRECT_CATALYST", "PROCEDURAL_DIRECT_REVIEW"}
    }
    if len(direct) != 11 or terms.get("symbol_count") != 11:
        raise ValueError("exact 11 economic/procedural threads required")
    original_thread_names = {
        name.split("::", 1)[0] for name in terms.get("cluster_event_counts", {})
    }
    if original_thread_names != direct:
        raise ValueError("HG004 detailed transaction set differs from 11 live threads")

    hurdles = payoff.get("key_hurdles")
    prices = market.get("key_mechanical_context")
    expected_payoff = {"ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV"}
    if (
        not isinstance(hurdles, dict)
        or set(hurdles) != expected_payoff
        or not isinstance(prices, dict)
        or set(prices) != expected_payoff
        or market.get("price_session") != "2026-10-01"
        or market.get("symbol_count") != 5
    ):
        raise ValueError("HG005 payoff/market source identities or price vintage changed")
    if (
        payoff.get("completion_probabilities_assigned") is not False
        or payoff.get("expected_returns_calculated") is not False
        or base_rate.get("current_company_probability_surfaces_published") != 0
        or base_rate.get("current_evidence_cutoff") != "2026-10-04"
        or base_rate.get("case_count") != 6
    ):
        raise ValueError("HG005/HG006 payoff or company probability evidence changed")
    mapped_cases = base_rate.get("current_case_summary")
    if not isinstance(mapped_cases, list) or len(mapped_cases) != 6:
        raise ValueError("HG006 current stage mapping is incomplete")
    if any(row.get("probability_surface") is not None for row in mapped_cases):
        raise ValueError("current company probability surface was not frozen as supported")
    by_mapped: dict[str, list[dict]] = {}
    for row in mapped_cases:
        if row.get("symbol") not in expected_payoff:
            raise ValueError("HG006 current case outside HG005 payoff cohort")
        by_mapped.setdefault(row["symbol"], []).append(row)

    newer = october.get("cases")
    if not isinstance(newer, list) or october.get("case_count") != 8:
        raise ValueError("SS002 October case pilot changed")
    overlapping: dict[str, list[dict]] = {}
    for row in newer:
        symbol = row.get("symbol")
        if symbol in direct:
            if row.get("independent_semantic_audit") != "PENDING":
                raise ValueError("SS002 pilot independent audit state changed")
            overlapping.setdefault(symbol, []).append(row)
    if set(overlapping) != {"INOXGREEN", "SAMBHV"}:
        raise ValueError("unexpected newer October pilot/current case overlap")

    cases = []
    for symbol in originals:
        h = hurdles.get(symbol)
        economic_status = h.get("state") if h else "NO_VERIFIED_FAMILY_PAYOFF_MODEL"
        if economic_status in {
            "PAYOFF_FRAMEWORK_BLOCKED_SOURCE_PARTIAL",
            "SENSITIVITY_READY_GROSS_EV_ONLY",
        }:
            route = "SOURCE_INCOMPLETE_OR_EQUITY_BRIDGE_BLOCKED"
        elif economic_status in {"REVERSE_HURDLE_READY", "SENSITIVITY_READY"}:
            route = "SENSITIVITY_OR_REVERSE_HURDLE_NOT_PROVEN_EARNINGS"
        elif symbol in direct:
            route = "LIVE_TRANSACTION_WITHOUT_CASE_PAYOFF_MODEL"
        else:
            route = "NONLIVE_FROZEN_COHORT_RETAINED_FOR_FUNDAMENTALS"

        if symbol in RESEARCH_REQUESTS:
            requests = list(RESEARCH_REQUESTS[symbol])
        elif role[symbol] == "TEXT_PENDING":
            requests = [
                "RETRIEVE_READABLE_ORIGINAL_EXCHANGE_ATTACHMENT",
                "RECONCILE_LISTED_ISSUER_TRANSACTION_AND_SOURCE_DATE",
            ]
        elif symbol in direct:
            requests = [
                "RECONSTRUCT_ORIGINATING_TRANSACTION_AND_APPROVAL_CHAIN",
                "EXTRACT_ISSUER_SPECIFIC_CASH_FLOW_DILUTION_AND_DOWNCASE_TERMS",
                "PRESERVE_SEPARATE_ISSUER_VERSUS_INVESTEE_IDENTITY",
            ]
        else:
            requests = [
                "REFRESH_INDEPENDENT_EARNINGS_ASSET_AND_GOVERNANCE_EVIDENCE",
                "DO_NOT_ASSERT_LIVE_TRANSACTION_FROM_HISTORICAL_STATUS",
            ]
        snapshot = prices.get(symbol)
        price = snapshot.get("close_price_inr") if snapshot else None
        market_cap = snapshot.get("reported_fd_market_cap_inr_crore") if snapshot else None
        if snapshot is not None and (
            type(price) not in (int, float)
            or type(market_cap) not in (int, float)
            or price <= 0
            or market_cap <= 0
        ):
            raise ValueError("HG005 market reference missing exact positive price/cap")
        mapping = by_mapped.get(symbol, [])
        stage_is_completed = [
            item["historical_track"]
            for item in mapping
            if item["mapping_state"] == "CURRENT_TERMINAL_COMPLETED"
        ]
        cases.append({
            "symbol": symbol,
            "hg003_thread_state": role[symbol],
            "evidence_acquisition_route": route,
            "economic_sensitivity_state": economic_status,
            "price_reference_session": "2026-10-01" if snapshot else None,
            "price_reference_inr_not_current": price,
            "reported_fd_cap_reference_inr_cr_not_current": market_cap,
            "frozen_hg005_mechanical_hurdle": h,
            "older_hg006_current_stage_cases": mapping,
            "one_completed_issuance_is_not_full_economic_exercise": bool(
                stage_is_completed and "issuance_completion" in stage_is_completed
            ),
            "newer_ss002_october_pilot_exists_pending_independent_review": (
                symbol in overlapping
            ),
            "newer_pilot_research_lanes": [
                row["research_lane"] for row in overlapping.get(symbol, [])
            ],
            "next_source_documents_to_acquire_not_asserted_as_facts": requests,
            "stock_valuation_ready": False,
            "case_specific_probability_published": False,
            "current_execution_price_verified": False,
            "corporate_action_and_dividend_basis_verified": False,
            "probability_weighted_expected_return_permitted": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        })
    cases.sort(key=lambda row: (
        RESEARCH_ROUTE_ORDER[row["evidence_acquisition_route"]], row["symbol"]
    ))
    if len(cases) != 28:
        raise ValueError("casework failed original cohort accounting")

    result = {
        "schema_version": 1,
        "casework_id": BOARD_ID,
        "classification": "SOURCE_PINNED_RESEARCH_PRIORITY_NOT_STOCK_RANKING_OR_ALPHA",
        "snapshot_assembled_as_of": "2026-10-10",
        "source_provenance": receipts,
        "market_denominator_snapshot_session": "2026-10-01",
        "survivor_stage_current_evidence_cutoff": "2026-10-04",
        "source_membership_count": 28,
        "source_active_direct_catalyst_count": sum(
            row["hg003_thread_state"] == "ACTIVE_DIRECT_CATALYST" for row in cases
        ),
        "source_procedural_direct_review_count": sum(
            row["hg003_thread_state"] == "PROCEDURAL_DIRECT_REVIEW" for row in cases
        ),
        "source_nonlive_or_pending_count": sum(
            row["hg003_thread_state"]
            not in {"ACTIVE_DIRECT_CATALYST", "PROCEDURAL_DIRECT_REVIEW"}
            for row in cases
        ),
        "source_economic_context_case_count": len(expected_payoff),
        "gross_or_reverse_hurdle_surface_count": sum(
            row["economic_sensitivity_state"] in {
                "SENSITIVITY_READY_GROSS_EV_ONLY",
                "REVERSE_HURDLE_READY",
                "SENSITIVITY_READY",
            }
            for row in cases
        ),
        "current_case_specific_survivor_probability_surface_count": 0,
        "newer_october_pilot_cases_needing_stage_reconciliation": sorted(overlapping),
        "approved_stock_recommendation_count": 0,
        "casework": cases,
        "source_collection_only_no_price_refresh_performed": True,
        "company_expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return result
