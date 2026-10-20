"""L001 P027: original ZUARI agro issuer ICD repayment, not NAV uplift.

Two first-party Zuari Agro Chemicals September 2026 original BSE/NSE issuer
PDFs prove ₹214.50cr + ₹44cr paid to ZUARI INDUSTRIES. Repayment exchanges
a parent receivable for cash. It is NOT new equity asset creation. The
parent-only cash receipt, offsetting loan receivable decrease, treatment in
consolidation, pledge/collateral and lender debt reduction require proof.
"""

from __future__ import annotations

import copy
import hashlib
import io
import re
from datetime import UTC, datetime
from typing import Any

from pypdf import PdfReader

from marketlab.alpha import AlphaContractError, digest

REPORT_ID = "L001-P027-ZUARI-INTERCORPORATE-DEPOSIT-REPAYMENT-20261021-v1"
PARENT_SYMBOL = "ZUARIIND"
BORROWER_SYMBOL = "ZUARI"
PARENT_ISIN = "INE217A01012"
BORROWER_ISIN = "INE840M01016"
TOTAL_ICD_CR = 258.50
FRONTIER_SOURCE_SHA = "847f93a8cb6872a9c7a0a44049504617ea55c387bf3954edb532d3e97c05daef"
FRONTIER_BLOB = "dbcf91030ba488ba99d10287f45afead562da6a4"
FRONTIER_PATH = "research/l001/l001-p023-value-falsification-frontier-v1.json"
EVIDENCE = {
    "SEPT18": {
        "url": "https://www.zuari.in/assets/files/ZACLDisclosureunderReg30-RepaymentofICDs-18-09-2026.pdf",
        "original_issuer_document_date": "2026-09-18",
        "heading": "18th September, 2026",
        "amount_cr": 214.50,
        "pages": 1,
        "must_include": ("258.50", "214.50", "Zuari Industries Limited"),
    },
    "SEPT30": {
        "url": "https://www.zuari.in/assets/files/Reg30RepaymentofICDsdtd30.09.2026.pdf",
        "original_issuer_document_date": "2026-09-30",
        "heading": "30th September, 2026",
        "amount_cr": 44.0,
        "pages": 1,
        "must_include": (
            "258.50", "214.50", "44 Crore", "Zuari Industries Limited",
            "stand Nil",
        ),
    },
}
RESEARCH_BASELINE = {
    "source_market_session": "2026-10-19",
    "five_original_share_stake_marks_cr": 3764.9208,
    "March2026_parent_net_borrowings_cr_NOT_CURRENT": 2519.4245,
    "Oct19_historical_basic_market_cap_cr_NOT_CURRENT": 771.6305,
    "naive_undeclared_claim_residual_cr_NOT_EQUITY_NAV": 473.8658,
}


def _read_pdf(raw: bytes) -> tuple[int, str]:
    if not raw.startswith(b"%PDF") or not 400 < len(raw) < 3_000_000:
        raise AlphaContractError("P027 nonissuer or oversized original PDF")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        return len(reader.pages), " ".join(
            page.extract_text() or "" for page in reader.pages
        )
    except Exception as exc:
        raise AlphaContractError("P027 original issuer PDF unreadable") from exc


def validate_issuer_pdf(kind: str, raw: bytes) -> dict[str, Any]:
    spec = EVIDENCE.get(kind)
    if spec is None:
        raise AlphaContractError("P027 original issuer document kind changed")
    pages, extracted = _read_pdf(raw)
    if pages != spec["pages"]:
        raise AlphaContractError("P027 issuer PDF original page count drift")
    lowered = re.sub(r"\s+", " ", extracted).casefold()
    tight = re.sub(r"\s+", "", extracted).casefold()
    if (
        "zuari agro chemicals" not in lowered
        or "national stock exchange" not in lowered
        or "nse symbol: zuari" not in lowered
        or spec["heading"].casefold().replace(" ", "") not in tight
    ):
        raise AlphaContractError("P027 wrong issuer or original filing date")
    for phrase in spec["must_include"]:
        if phrase.casefold().replace(" ", "") not in tight:
            raise AlphaContractError(
                "P027 original filed repayment proof missing: " + phrase
            )
    if kind == "SEPT18" and "repaid" not in lowered:
        raise AlphaContractError("P027 issuer repayment verb absent")
    if kind == "SEPT30" and not (
        "30thseptember" in tight and "balanceicds" in tight
    ):
        raise AlphaContractError("P027 second original is not the final repayment")
    return {
        "document_kind": kind,
        "source_original_url": spec["url"],
        "issuer_symbol_ZUARI_NOT_PARENT": BORROWER_SYMBOL,
        "parent_creditor_symbol": PARENT_SYMBOL,
        "issuer_document_date": spec["original_issuer_document_date"],
        "pdf_pages": pages,
        "raw_pdf_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_pdf_bytes": len(raw),
        "issuer_reported_repayment_cr": spec["amount_cr"],
        "issuer_reported_total_ICDs_original_cr": TOTAL_ICD_CR,
        "original_issuer_PDF_authenticated": True,
        "parent_receivable_or_cash_account_not_separately_verified": True,
        "live_capital_allowed": False,
    }


def make_receipt(
    kind: str,
    original: bytes,
    *,
    captured_at_utc: str,
) -> dict[str, Any]:
    parsed = validate_issuer_pdf(kind, original)
    try:
        observed = datetime.fromisoformat(captured_at_utc)
    except (ValueError, TypeError) as exc:
        raise AlphaContractError("P027 invalid first source timestamp") from exc
    if observed.tzinfo is None:
        raise AlphaContractError("P027 source timestamp lacks offset")
    if observed.astimezone(UTC).date().isoformat() < parsed["issuer_document_date"]:
        raise AlphaContractError("P027 source timing retroactively backdated")
    receipt = {
        **parsed,
        "first_observed_at_utc": observed.astimezone(UTC).isoformat(),
        "original_raw_path": (
            "research/l001/originals/zuari_icd/"
            + kind.lower() + "/" + parsed["raw_pdf_sha256"] + ".pdf"
        ),
        "source_custody_state": "ORIGINAL_ISSUER_PDF_BYTES_VERIFIED",
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_receipt(kind: str, raw: bytes, receipt: dict[str, Any]) -> None:
    unsigned = copy.deepcopy(receipt)
    old = unsigned.pop("receipt_sha256", None)
    if old != digest(unsigned):
        raise AlphaContractError("P027 issuer original receipt hash modified")
    new = make_receipt(
        kind, raw, captured_at_utc=receipt["first_observed_at_utc"]
    )
    if new != receipt:
        raise AlphaContractError("P027 original source bytes or receipt changed")


def build_parent_icd_cash_bridge(
    originals: dict[str, bytes],
    receipts: dict[str, dict],
    *,
    earlier_frontier: dict[str, Any],
) -> dict[str, Any]:
    if set(originals) != set(EVIDENCE) or set(receipts) != set(EVIDENCE):
        raise AlphaContractError("P027 two original issuer PDFs are required")
    for kind in EVIDENCE:
        verify_receipt(kind, originals[kind], receipts[kind])
    frontier = copy.deepcopy(earlier_frontier)
    stored = frontier.pop("report_sha256", None)
    if stored != FRONTIER_SOURCE_SHA or stored != digest(frontier):
        raise AlphaContractError("P027 historical NAV frontier signed source changed")
    zuari = next(
        (r for r in earlier_frontier["evidence"] if r["symbol"] == PARENT_SYMBOL),
        None,
    )
    if (
        zuari is None
        or zuari["hypothetical_undiscounted_stake_gap_cr_not_parent_equity"]
        != RESEARCH_BASELINE["naive_undeclared_claim_residual_cr_NOT_EQUITY_NAV"]
        or zuari["march_net_borrowings_cr_not_current"]
        != RESEARCH_BASELINE["March2026_parent_net_borrowings_cr_NOT_CURRENT"]
    ):
        raise AlphaContractError("P027 incompatible earlier parent NAV context")
    early = receipts["SEPT18"]["issuer_reported_repayment_cr"]
    late = receipts["SEPT30"]["issuer_reported_repayment_cr"]
    if round(early + late, 2) != TOTAL_ICD_CR:
        raise AlphaContractError("P027 issuer principal repayment arithmetic failed")
    return_values = {
        "total_principal_icd_repaid_cr": round(early + late, 4),
        "sep18_deposit_principal_repayment_cr": early,
        "sep30_final_deposit_principal_repayment_cr": late,
        "reported_icd_from_parent_outstanding_after_sep30_cr": 0,
        "unverified_parent_beginning_loan_receivable_decrease_cr": None,
        "unverified_parent_cash_increase_reconciled_cr": None,
        "incremental_parent_net_asset_value_from_repayment_alone_cr": 0,
        "incremental_new_group_profit_from_principal_repayment_cr": 0,
        "reclassification_of_existing_parent_receivable_to_cash_is_not_new_wealth": True,
        "whether_parent_stale_borrowings_repaid_by_received_cash": None,
    }
    output = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "analysis_date_ist": "2026-10-21",
        "cashflow_event_dates": ["2026-09-18", "2026-09-30"],
        "borrower_issuer_symbol": BORROWER_SYMBOL,
        "parent_creditor_symbol": PARENT_SYMBOL,
        "borrower_issuer_isin_from_original_filings_verified": False,
        "parent_issuer_isin_from_market_study": PARENT_ISIN,
        "original_issuer_source_documents": receipts,
        "source_retrieval_actual_utc_not_event_date": True,
        "old_ZUARIIND_five_stake_reverse_hurdle_source_SHA": FRONTIER_SOURCE_SHA,
        "original_oct19_reverse_asset_test": RESEARCH_BASELINE,
        "issuer_published_ICD_parent_creditor_cash_event": return_values,
        "parent_statements_recorded_ICD_receivable_and_repayment_verified": False,
        "consolidation_group_and_intragroup_elimination_reconciled": False,
        "current_parent_net_debt_after_sep30_reconciled": False,
        "pledged_shares_original_sep30_depository_source_verified": False,
        "parent_creditor_lender_waterfall_known": False,
        "fully_diluted_parent_equity_current": None,
        "pledged_collateral_cannot_be_subtracted_again_without_lender_bridge": True,
        "stale_March_debt_and_Oct19_stakes_are_not_same_date_NA_V": True,
        "issuer_cash_repayment_is_not_independent_50pct_stock_upside": True,
        "probability_weighted_expected_return": None,
        "buy_rating_or_price_target": None,
        "after_cost_margin_of_safety_verified": False,
        "live_capital_allowed": False,
    }
    output["report_sha256"] = digest(output)
    return output


def validate_bridge(
    report: dict[str, Any],
    *,
    originals: dict[str, bytes],
    receipts: dict[str, dict],
    earlier_frontier: dict[str, Any],
) -> None:
    unsigned = copy.deepcopy(report)
    stored = unsigned.pop("report_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P027 signed source cashbridge changed")
    again = build_parent_icd_cash_bridge(
        originals, receipts, earlier_frontier=earlier_frontier
    )
    if again != report:
        raise AlphaContractError("P027 primary PDF bridge not source reproducible")
