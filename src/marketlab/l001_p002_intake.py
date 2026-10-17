"""L001 P002: preserve all HG009 identities in a separate long-horizon source intake.

The frozen HG009 discovery cohort is a source of names, NEVER a new
preregistered long-horizon portfolio. Without dated official industry,
complete owner cash, share capital and corporate-action documents, abstain.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest

COHORT_SHA256 = "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5"
P014_SHA256 = "093c29805ccf0423c1d8b0bfbb8c80c9d89c83c2f12395ea16348a0d6ae47ddc"
HORIZONS = (252, 504, 756)
FINANCIAL_GROUPS = frozenset({
    "Financial Services", "Banking", "Insurance", "Capital Markets",
    "Non Banking Financial Services",
})
INDUSTRIAL_GROUPS = frozenset({
    "Automobile", "Automobile and Auto Components", "Capital Goods",
    "Chemicals", "Construction", "Construction Materials", "Consumer Durables",
    "Consumer Services", "Diversified", "Fast Moving Consumer Goods",
    "Healthcare", "Information Technology", "Media Entertainment & Publication",
    "Metals & Mining", "Oil Gas & Consumable Fuels", "Power", "Realty",
    "Services", "Telecommunication", "Textiles", "Utilities",
})
INDUSTRIAL_ROLES = (
    "AUDITED_CONSOLIDATED_FINANCIALS",
    "DILUTED_PARENT_SHARES_AND_ACTIONS",
    "PARENT_OWNER_CASH_RECONCILED",
    "MAINTENANCE_GROWTH_CAPEX_SPLIT",
    "ACQUISITION_MINORITY_AND_LEASE_CLAIMS",
    "EXCESS_CASH_RECONCILED",
    "INCREMENTAL_NOPAT_AND_INVESTED_CAPITAL",
    "TRADABILITY_CORPORATE_ACTION_AND_EXIT_SOURCES",
)
FINANCIAL_ROLES = (
    "REGULATED_BALANCE_SHEET_AND_BOOK_VALUE",
    "DILUTED_PARENT_SHARES_AND_ACTIONS",
    "CREDIT_COST_AND_ASSET_QUALITY",
    "LOAN_BOOK_AND_FUNDING_COST",
    "REGULATORY_CAPITAL_AND_CAPITAL_ADEQUACY",
    "PARENT_EARNINGS_ROE_AND_DISTRIBUTABLE_CAPITAL",
    "ACQUISITION_MINORITY_AND_CONTINGENT_CLAIMS",
    "TRADABILITY_CORPORATE_ACTION_AND_EXIT_SOURCES",
)


@dataclass(frozen=True)
class ClassificationReceipt:
    symbol: str
    isin: str
    official_industry: str
    original_raw_bytes: bytes
    expected_sha256: str
    source_url: str
    published_utc: str
    first_seen_utc: str
    reviewer_status: str


def _utc(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        return None
    return dt


def _signature(doc: dict, field: str, pin: str) -> None:
    unsigned = {key: value for key, value in doc.items() if key != field}
    if doc.get(field) != pin or digest(unsigned) != pin:
        raise AlphaContractError(f"immutable source signature mismatch: {field}")


def industry_from_original(
    receipt: ClassificationReceipt | None,
    *,
    symbol: str,
    isin: str,
    decision_cutoff_utc: str,
) -> str:
    """An official source envelope is required even for an obvious bank ticker.

    The reviewer_status is an assertion, not authenticated reviewer identity.
    Unknown classifications MUST NOT fall into the industrial calculation.
    """
    cutoff = _utc(decision_cutoff_utc)
    if cutoff is None or receipt is None:
        return "UNCLASSIFIED"
    if receipt.symbol != symbol or receipt.isin != isin:
        return "UNCLASSIFIED"
    if (
        not isinstance(receipt.original_raw_bytes, bytes)
        or not receipt.original_raw_bytes
        or sha256(receipt.original_raw_bytes).hexdigest() != receipt.expected_sha256
    ):
        return "UNCLASSIFIED"
    if (
        not isinstance(receipt.official_industry, str)
        or receipt.official_industry not in FINANCIAL_GROUPS | INDUSTRIAL_GROUPS
        or receipt.official_industry.encode() not in receipt.original_raw_bytes
        or symbol.encode() not in receipt.original_raw_bytes
        or isin.encode() not in receipt.original_raw_bytes
    ):
        return "UNCLASSIFIED"
    parsed = urlparse(receipt.source_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"nsearchives.nseindia.com", "archives.nseindia.com",
                                   "www.nseindia.com"}
    ):
        return "UNCLASSIFIED"
    published = _utc(receipt.published_utc)
    seen = _utc(receipt.first_seen_utc)
    if (
        published is None or seen is None or not published <= seen <= cutoff
        or receipt.reviewer_status != "INDEPENDENTLY_REVIEWED"
    ):
        return "UNCLASSIFIED"
    return (
        "FINANCIAL_REGULATED"
        if receipt.official_industry in FINANCIAL_GROUPS
        else "NON_FINANCIAL_OPERATING_COMPANY"
    )


def build_source_intake(
    frozen_cohort: dict,
    p014_packet: dict,
    *,
    research_cutoff_utc: str,
    classifications: dict[tuple[str, str], ClassificationReceipt] | None = None,
) -> dict:
    """All 100 rows retained. Unavailable original documents stay missing."""
    if _utc(research_cutoff_utc) is None:
        raise AlphaContractError("valid exact UTC research cutoff required")
    _signature(frozen_cohort, "cohort_sha256", COHORT_SHA256)
    _signature(p014_packet, "report_sha256", P014_SHA256)
    members = frozen_cohort.get("selected")
    cases = p014_packet.get("cash_flow_and_other_income_diagnostics")
    if not isinstance(members, list) or not isinstance(cases, list):
        raise AlphaContractError("source lists missing")
    if len(members) != 100 or frozen_cohort.get("selected_count") != 100:
        raise AlphaContractError("frozen roster has not retained 100 companies")
    pairs = [(row.get("symbol"), row.get("isin")) for row in members]
    if (
        any(not isinstance(s, str) or not s or not isinstance(i, str) or len(i) != 12
            for s, i in pairs)
        or len(set(pairs)) != 100
        or len({s for s, _ in pairs}) != 100
        or sorted(s for s, _ in pairs) != frozen_cohort.get("selected_symbols_sorted")
    ):
        raise AlphaContractError("frozen company symbol and ISIN mismatch")
    case_by_symbol = {row["symbol"]: row for row in cases}
    if len(case_by_symbol) != 10 or len(cases) != 10:
        raise AlphaContractError("P014 ten original dossiers changed")
    if not set(case_by_symbol).issubset({s for s, _ in pairs}):
        raise AlphaContractError("P014 dossier not in frozen HG009 roster")
    classifiers = classifications or {}
    if not set(classifiers).issubset(set(pairs)):
        raise AlphaContractError("extraneous issuer classification supplied")
    rows = []
    for original in members:
        symbol, isin = original["symbol"], original["isin"]
        class_ = industry_from_original(
            classifiers.get((symbol, isin)), symbol=symbol, isin=isin,
            decision_cutoff_utc=research_cutoff_utc,
        )
        case = case_by_symbol.get(symbol)
        if case is not None and case["original_isin"] != isin:
            raise AlphaContractError("P014 original dossier ISIN identity drift")
        cash = case.get("source_reported_economics_not_owner_fcf") if case else None
        basis = cash.get("basis") if isinstance(cash, dict) else None
        if basis == "FY26_CONSOLIDATED_ORIGINAL_SOURCE_REPLAY":
            old_source_state = "FY26_CASH_REPLAY_REFERENCE_NOT_OWNER_CASH"
        elif basis is not None:
            old_source_state = "INTERIM_OR_OTHER_FINANCIAL_DIAGNOSTIC"
        elif case is not None:
            old_source_state = "DOSSIER_WITHOUT_OWNER_CASH"
        else:
            old_source_state = "NO_PRIOR_COMPANY_CASH_DOSSIER"
        model = (
            "FINANCIAL_SPECIALIST_ONLY" if class_ == "FINANCIAL_REGULATED"
            else "INDUSTRIAL_REVIEW_ONLY" if class_ == "NON_FINANCIAL_OPERATING_COMPANY"
            else "CLASSIFICATION_REQUIRED"
        )
        roles = (
            FINANCIAL_ROLES if model == "FINANCIAL_SPECIALIST_ONLY"
            else INDUSTRIAL_ROLES if model == "INDUSTRIAL_REVIEW_ONLY" else ()
        )
        reasons = (
            ["OFFICIAL_PIT_INDUSTRY_CLASSIFICATION_MISSING"]
            if model == "CLASSIFICATION_REQUIRED" else []
        )
        # Even original P014 replay references are not P002 source-complete
        # current owner-cash packets. Every role remains unproven until read
        # from an independently authenticated document in a separate workflow.
        reasons.extend(f"REQUIRED_{role}_MISSING" for role in roles)
        rows.append({
            "symbol": symbol,
            "isin": isin,
            "frozen_router_row_sha256": original["full_frozen_router_row_sha256"],
            "frozen_source_liquidity_band_not_fill_capacity": original[
                "source_liquidity_band"
            ],
            "classification": class_,
            "model": model,
            "prior_dossier_source_state": old_source_state,
            "p014_replay_reference_path": (
                "research/hg009/hg009-p014-economic-symmetry-and-cash-v1.json"
                if case is not None else None
            ),
            "missing_evidence": reasons,
            "source_complete": False,
            "valid_long_horizon_valuation": False,
            "realized_return_horizons_sessions": [],
            "expected_return": None,
            "investment_authorized": False,
        })
    rows.sort(key=lambda row: (row["symbol"], row["isin"]))
    counts = {
        "detailed_p014_dossiers": len(case_by_symbol),
        "fy26_consolidated_cash_replay_references": sum(
            row["prior_dossier_source_state"] == "FY26_CASH_REPLAY_REFERENCE_NOT_OWNER_CASH"
            for row in rows
        ),
        "official_industry_verified_in_this_intake": sum(
            row["classification"] != "UNCLASSIFIED" for row in rows
        ),
        "finance_specialist_gate": sum(row["model"] == "FINANCIAL_SPECIALIST_ONLY"
                                        for row in rows),
        "source_complete": 0,
        "investable_valuations": 0,
        "long_horizon_outcomes_mature": 0,
    }
    report = {
        "schema_version": 1,
        "intake_id": "L001-P002-HG009-ALL100-SOURCE-READINESS-v1",
        "scope": "POST_HG009_SEPARATE_PROSPECTIVE_INTAKE_NOT_FROZEN_SIGNAL",
        "research_cutoff_utc": research_cutoff_utc,
        "frozen_cohort_sha256": COHORT_SHA256,
        "p014_prior_diligence_sha256": P014_SHA256,
        "company_count": len(rows),
        "horizons_sessions": list(HORIZONS),
        "counts": counts,
        "companies": rows,
        "member_retention_verified": True,
        "industry_is_not_inferred_from_ticker": True,
        "prior_p014_cash_cfo_less_ppe_is_not_owner_cash": True,
        "no_prediction_or_entry_signal_created": True,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
