"""Source-bound Sambhv 2026 proposed warrant cash/dilution *timing* audit.

The official 15 July issuer board proposal states 8,695,400 proposed
warrants at INR 115, 25% due upon allotment, 75% due upon exercise
within 18 months FROM THE ACTUAL ALLOTMENT DATE. Neither an August
shareholder vote nor an October monitoring agency appointment proves
that any warrant was allotted, exercised, or paid into company bank cash.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

AUDIT_ID = "HG007-P032-SAMBHV-BOARD-WARRANT-CASH-TRANCHES-v1"
ISSUER_PDF = (
    "https://www.sambhv.com/uploads/pdf/investors/investor-information/"
    "announcement/Outcome-of-Board-meeting-of-July-15-2026-for-Raising-of-Funds.pdf"
)
HISTORICAL_HG005 = (
    "research/hg005-d001-result-v1.json",
    "2dbbc3055d1aacec8a37dd510a1a75a3c7868006",
)
OCTOBER_P031 = (
    "research/hg007/sambhv-oct2026-sources/sambhv-october-case-v1.json",
    "4f6c9df119250e9a29efa432570bb00f386d1614",
)
AUGUST_P017 = (
    "research/hg007/sambhv-aug2026-investor/phase1-steel-power-capex-v1.json",
    "1dbb0ddaa6243b6afe79746906f214c4cc422461",
)
PDF_PAGES = 5
PDF_MAX_BYTES = 12_000_000
WARRANT_COUNT_PROPOSED = 8_695_400
WARRANT_PRICE_INR = 115
MAX_GROSS_FUNDING_INR = 999_971_000
INSTALLMENT_FRACTIONS = (0.25, 0.75)
PROPOSED_ANJANEYA = 6_608_600
PROPOSED_OTHERS = (347_800,) * 6
SOURCE_STATES = frozenset({
    "ORIGINAL_BOARD_PDF_CAPTURED_AND_TERMS_BOUND",
    "ORIGINAL_BOARD_PDF_NOT_PUBLISHED",
    "ORIGINAL_BOARD_PDF_ACCESS_BLOCKED",
    "ORIGINAL_BOARD_PDF_REDIRECT_NOT_FOLLOWED",
    "ORIGINAL_BOARD_PDF_INVALID_OR_UNVERIFIED",
    "ORIGINAL_BOARD_PDF_FETCH_FAILED",
})


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _pinned_json(root: Path, reference: tuple[str, str]) -> tuple[dict, dict]:
    filename, blob = reference
    original = (root / filename).read_bytes()
    if _git_blob(original) != blob:
        raise ValueError(f"warrant research source Git blob drifted: {filename}")
    content = json.loads(original)
    if not isinstance(content, dict):
        raise TypeError("warrant original companion evidence must be a JSON object")
    return content, {
        "path": filename,
        "git_blob_sha": blob,
        "raw_sha256": hashlib.sha256(original).hexdigest(),
    }


def _check_pdf(raw: bytes) -> bool:
    return (
        isinstance(raw, bytes)
        and 1024 <= len(raw) <= PDF_MAX_BYTES
        and raw.startswith(b"%PDF-")
        and b"%%EOF" in raw[-2048:]
    )


def _pdf_text_pages(raw: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) != PDF_PAGES:
            raise ValueError("expected exactly five issuer board pages")
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("issuer original warrant PDF pages unreadable") from exc
    if any(len(s.strip()) < 100 for s in pages):
        raise ValueError("issuer original PDF text blank/too short")
    return pages


def verify_original_board_terms(raw: bytes) -> dict[str, Any]:
    if not _check_pdf(raw):
        raise ValueError("issuer original warrant source fails PDF envelope")
    pages = _pdf_text_pages(raw)
    text = [re.sub(r"\s+", " ", row.casefold()) for row in pages]
    # Check page placement as well as numbers; a counterfeit unrelated
    # 8,695,400 transaction somewhere in a PDF must never be admitted.
    requirements = (
        ("sambhv steel tubes", "july 15, 2026", "8,695,400", "115", "999,971,000"),
        ("shareholders", "funds"),
        ("8,695,400", "115", "18 months"),
        ("25%", "75%", "18", "forfeited", "equity share"),
        ("anjaneya minerals", "6,608,600", "suresh kumar goyal", "anu garg"),
    )
    for page_idx, tokens in enumerate(requirements):
        # "Shareholders" and "funds" may appear on page 1 or 2,
        # but required table/term numbers must stay on their source page.
        if page_idx == 1:
            if "shareholders" not in text[1] and "members" not in text[1]:
                raise ValueError("second original board page absent/invalid")
        elif any(token not in text[page_idx] for token in tokens):
            raise ValueError(
                f"original Sambhv July board PDF page {page_idx + 1} lacks required terms"
            )
    # Each warrant is one share; up to 18 months from *allotment*, not
    # from the board or shareholder approval date.
    joined = text[3]
    if not ("date of allotment" in joined and "at the time of" in joined):
        raise ValueError("warrant payments are not linked to actual allotment/exercise")
    if PROPOSED_ANJANEYA + sum(PROPOSED_OTHERS) != WARRANT_COUNT_PROPOSED:
        raise ValueError("proposed allottee distribution does not sum to board limit")
    if WARRANT_COUNT_PROPOSED * WARRANT_PRICE_INR != MAX_GROSS_FUNDING_INR:
        raise ValueError("board offer count does not reconcile with face issue price")
    return {
        "pdf_page_count": len(pages),
        "original_page_text_sha256": [
            hashlib.sha256(row.encode("utf-8")).hexdigest() for row in pages
        ],
        "reported_board_date": "2026-07-15",
        "reported_maximum_warrants": WARRANT_COUNT_PROPOSED,
        "reported_issue_price_per_warrant_inr": WARRANT_PRICE_INR,
        "reported_maximum_total_issue_consideration_inr": MAX_GROSS_FUNDING_INR,
        "warrant_to_equity_share_conversion_ratio": 1,
        "max_tenure_months_FROM_ACTUAL_ALLOTMENT": 18,
        "percent_due_only_at_actual_warrant_allotment": 25,
        "percent_due_only_at_equity_conversion": 75,
        "forfeiture_if_not_exercised_in_18_months": True,
        "proposed_promoter_group_anjaneya_warrants": PROPOSED_ANJANEYA,
        "remaining_six_proposed_allottee_warrants_each": 347_800,
        "original_pdf_visual_semantic_review_approved": False,
        "actual_allotment_or_exercise_verified": False,
        "realized_bank_cash_verified": False,
    }


def _receipt(
    *,
    state: str,
    http_status: int | None,
    raw: bytes | None,
    verified: dict[str, Any] | None,
    issue: str,
) -> dict[str, Any]:
    if state not in SOURCE_STATES:
        raise ValueError("invalid Sambhv original issuer source state")
    success = state == "ORIGINAL_BOARD_PDF_CAPTURED_AND_TERMS_BOUND"
    if success != (raw is not None and verified is not None):
        raise ValueError("warrant source state disagrees with original bytes")
    return {
        "schema_version": 1,
        "source_capture_id": AUDIT_ID,
        "symbol": "SAMBHV",
        "source_url": ISSUER_PDF,
        "captured_at_utc": _now(),
        "state": state,
        "http_status": http_status,
        "original_pdf_sha256": hashlib.sha256(raw).hexdigest() if success else None,
        "original_pdf_bytes": len(raw) if success else None,
        "source_text_verified": verified,
        "source_issue": issue,
        "complete_pdf_visual_review": False,
        "actual_warrant_allotment_verified": False,
        "actual_warrant_conversion_verified": False,
        "warrant_proceeds_received_in_bank_verified": False,
        "project_capex_funded_verified": False,
        "prospective_stock_expected_return_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def fetch_original_board(
    *,
    attempts: int = 2,
    sleep_seconds: float = 2.0,
) -> tuple[dict[str, Any], bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("original board source requires one to three attempts")
    if type(sleep_seconds) not in (int, float) or not 0 <= sleep_seconds <= 20:
        raise ValueError("original board retry sleep out of bounds")
    last_http = None
    last_issue = "NO_HTTP_RESPONSE"
    for step in range(attempts):
        try:
            response = requests.get(
                ISSUER_PDF,
                allow_redirects=False,
                timeout=30,
                headers={
                    "User-Agent": "marketlab-source-bound-research/1.0",
                    "Accept": "application/pdf",
                },
            )
            status = response.status_code
            last_http = status
            if getattr(response, "url", ISSUER_PDF) != ISSUER_PDF:
                return _receipt(
                    state="ORIGINAL_BOARD_PDF_REDIRECT_NOT_FOLLOWED",
                    http_status=status, raw=None, verified=None,
                    issue="UNEXPECTED_DESTINATION",
                ), None
            if status == 200:
                raw = response.content
                try:
                    verified = verify_original_board_terms(raw)
                except ValueError as exc:
                    return _receipt(
                        state="ORIGINAL_BOARD_PDF_INVALID_OR_UNVERIFIED",
                        http_status=status, raw=None, verified=None,
                        issue=type(exc).__name__ + ": " + str(exc),
                    ), None
                return _receipt(
                    state="ORIGINAL_BOARD_PDF_CAPTURED_AND_TERMS_BOUND",
                    http_status=200, raw=raw, verified=verified,
                    issue="FIVE_PAGE_ISSUER_TERMS_PENDING_VISUAL_APPROVAL",
                ), raw
            if status in (401, 403, 429):
                return _receipt(
                    state="ORIGINAL_BOARD_PDF_ACCESS_BLOCKED",
                    http_status=status, raw=None, verified=None,
                    issue=f"HTTP_{status}_NO_ACCESS_BYPASS",
                ), None
            if status == 404:
                return _receipt(
                    state="ORIGINAL_BOARD_PDF_NOT_PUBLISHED",
                    http_status=404, raw=None, verified=None,
                    issue="EXACT_ISSUER_ATTACHMENT_NOT_AVAILABLE",
                ), None
            if 300 <= status < 400:
                return _receipt(
                    state="ORIGINAL_BOARD_PDF_REDIRECT_NOT_FOLLOWED",
                    http_status=status, raw=None, verified=None,
                    issue="NO_UNVERIFIED_EXTERNAL_REDIRECT",
                ), None
            last_issue = f"HTTP_{status}"
            if status < 500:
                break
        except requests.RequestException as exc:
            last_issue = type(exc).__name__
        if step + 1 < attempts:
            time.sleep(sleep_seconds)
    return _receipt(
        state="ORIGINAL_BOARD_PDF_FETCH_FAILED",
        http_status=last_http, raw=None, verified=None, issue=last_issue,
    ), None


def build_conditional_board_cash_timing(
    receipt: dict[str, Any],
    companion: dict[str, dict],
    *,
    provenance: dict[str, dict],
) -> dict[str, Any]:
    if (
        receipt.get("state") != "ORIGINAL_BOARD_PDF_CAPTURED_AND_TERMS_BOUND"
        or receipt.get("source_capture_id") != AUDIT_ID
        or receipt.get("original_pdf_sha256") is None
        or receipt.get("actual_warrant_allotment_verified") is not False
        or receipt.get("warrant_proceeds_received_in_bank_verified") is not False
    ):
        raise ValueError("warrant source is not exact original or already claims cash")
    q2 = companion.get("p031")
    hg005 = companion.get("hg005")
    p017 = companion.get("p017")
    if not all(isinstance(v, dict) for v in (q2, hg005, p017)):
        raise TypeError("all three frozen company research records required")
    if (
        q2.get("readout_id")
        != "HG007-P031-SAMBHV-OCT2026-VOLUME-WARRANT-PRIMARY-SOURCE-v1"
        or q2.get("warrant_proceeds_issuer_disclosed_inr_crore") != 99.9971
        or q2.get("warrant_proceeds_are_verified_current_cash") is not False
        or q2.get("warrant_exercise_and_dilution_verified") is not False
        or q2.get("shareholder_prior_approval_date") != "2026-08-10"
        or p017.get("source_verified_steel_only_capex_inr_crore") != 810
        or p017.get("source_verified_additional_power_capex_inr_crore") != 125
        or p017.get("new_plant_operational_ebitda_verified") is not False
    ):
        raise ValueError("later issuer monitoring/capex reference does not reconcile")
    old = hg005.get("key_mechanical_context", {}).get("SAMBHV")
    if not isinstance(old, dict):
        raise TypeError("frozen old SAMBHV diluted denominator unavailable")
    lane = old.get("lanes", {}).get("DILUTION_FINANCING", {})
    if (
        lane.get("event_security_count") != WARRANT_COUNT_PROPOSED
        or lane.get("issue_price_per_security_inr") != WARRANT_PRICE_INR
        or lane.get("gross_issue_consideration_inr_crore") != 99.9971
        or lane.get("share_adjustment_state") != "PRO_FORMA_PENDING_POST_REPORT_APPROVAL"
        or old.get("close_price_inr") != 161.45
    ):
        raise ValueError("original frozen warrant model is not provenance-compatible")
    reported_fd = old["reported_fd_market_cap_inr_crore"] * 10_000_000 / 161.45
    new_fd = lane["event_adjusted_fd_shares"]
    if not math.isclose(reported_fd, 294_671_429, abs_tol=1e-7):
        raise ValueError("frozen August/October share baseline changed")
    if new_fd != int(reported_fd) + WARRANT_COUNT_PROPOSED:
        raise ValueError("original proforma full-conversion share count disagrees")
    statement = receipt["source_text_verified"]
    if (
        statement.get("reported_maximum_warrants") != WARRANT_COUNT_PROPOSED
        or statement.get("reported_issue_price_per_warrant_inr") != WARRANT_PRICE_INR
        or statement.get("percent_due_only_at_actual_warrant_allotment") != 25
        or statement.get("percent_due_only_at_equity_conversion") != 75
        or statement.get("max_tenure_months_FROM_ACTUAL_ALLOTMENT") != 18
    ):
        raise ValueError("original issuer July board terms no longer match financing model")

    total = MAX_GROSS_FUNDING_INR / 10_000_000
    first = total * INSTALLMENT_FRACTIONS[0]
    second = total * INSTALLMENT_FRACTIONS[1]
    combined_capex = 810 + 125
    if not math.isclose(first + second, 99.9971, abs_tol=1e-9):
        raise ValueError("25/75 cash installments do not sum to proposal")
    return {
        "schema_version": 1,
        "readout_id": AUDIT_ID,
        "classification": "ORIGINAL_ISSUER_CONDITIONAL_WARRANT_CASH_DILUTION_NOT_BANK_PROCEEDS",
        "symbol": "SAMBHV",
        "original_source_provenance": {
            "url": ISSUER_PDF,
            "original_pdf_sha256": receipt["original_pdf_sha256"],
            "original_pdf_byte_count": receipt["original_pdf_bytes"],
            "captured_at_utc": receipt["captured_at_utc"],
            "page_text_sha256": statement["original_page_text_sha256"],
            "companion_git_blob_receipts": provenance,
        },
        "original_board_proposal_date": "2026-07-15",
        "issuer_later_shareholder_approval_reported_date": "2026-08-10",
        "monitoring_agency_appointment_reported_date": "2026-10-06",
        "proposed_maximum_warrants": WARRANT_COUNT_PROPOSED,
        "cash_issue_price_per_warrant_inr": WARRANT_PRICE_INR,
        "fully_exercised_maximum_gross_issue_consideration_cr": total,
        "scenario_only_upfront_cash_at_100pct_allotment_cr": first,
        "scenario_only_later_cash_at_100pct_conversion_cr": second,
        "if_zero_actual_warrants_allotted_cash_from_issue_cr": 0.0,
        "promoter_group_anjaneya_proposed_warrants": PROPOSED_ANJANEYA,
        "promoter_group_anjaneya_proportion_of_proposal_pct": (
            100 * PROPOSED_ANJANEYA / WARRANT_COUNT_PROPOSED
        ),
        "other_six_proposed_warrants_each": 347_800,
        "promoter_versus_nonpromoter_total_final_subscriptions_verified": False,
        "exercise_time_limit_months_after_actual_allotment": 18,
        "actual_allotment_date_verified": False,
        "last_permitted_exercise_calendar_date_verified": False,
        "fully_exercised_pro_forma_added_shares": WARRANT_COUNT_PROPOSED,
        "frozen_old_reported_fd_shares_reference_not_current": int(reported_fd),
        "frozen_old_full_conversion_pro_forma_fd_shares_not_current": new_fd,
        "frozen_source_steel_plus_power_project_capex_cr": combined_capex,
        "maximum_gross_warrant_proceeds_fraction_of_steel_power_capex": (
            total / combined_capex
        ),
        "hypothetical_non_warrant_financing_gap_if_both_projects_and_full_issue_cr": (
            combined_capex - total
        ),
        "tranche_payment_state": "SCENARIOS_ONLY_PENDING_ISSUANCE_EXERCISE_AND_BANK_CONFIRMATION",
        "first_25pct_subscription_cash_received_verified": False,
        "last_75pct_conversion_cash_received_verified": False,
        "full_99_9971cr_cash_received_verified": False,
        "all_8_6954m_warrants_issued_verified": False,
        "warrant_exercise_completed_verified": False,
        "current_fully_diluted_share_count_verified": False,
        "project_capex_and_cash_uses_reconciled": False,
        "q2_sales_growth_verifies_project_ebitda": False,
        "investment_price_target_calculated": False,
        "future_shareholder_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _retain(
    directory: Path, receipt: dict[str, Any], original: bytes | None,
    companion: dict[str, dict], provenance: dict[str, dict],
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    success = receipt["state"] == "ORIGINAL_BOARD_PDF_CAPTURED_AND_TERMS_BOUND"
    if success:
        if original is None or hashlib.sha256(original).hexdigest() != receipt.get("original_pdf_sha256"):
            raise ValueError("original source capture hash failed")
        if verify_original_board_terms(original) != receipt["source_text_verified"]:
            raise ValueError("original issuer source page text changed between operations")
        original_path = directory / "original-raw" / "sha256" / f"{receipt['original_pdf_sha256']}.pdf"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        if original_path.exists() and original_path.read_bytes() != original:
            raise ValueError("original PDF content address already assigned different bytes")
        original_path.write_bytes(original)
        packet = build_conditional_board_cash_timing(receipt, companion, provenance=provenance)
        (directory / "warrant-board-cash-timing-v1.json").write_text(
            json.dumps(packet, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
        )
    elif original is not None:
        raise ValueError("unverified PDF bytes must never be retained as original")
    (directory / "original-source-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    return {
        "success": success,
        "source_state": receipt["state"],
        "original_pdf_sha256": receipt["original_pdf_sha256"],
        "full_warrant_cash_received_verified": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    args = parser.parse_args()
    companions = {}
    receipts = {}
    for name, ref in (("hg005", HISTORICAL_HG005), ("p031", OCTOBER_P031), ("p017", AUGUST_P017)):
        companions[name], receipts[name] = _pinned_json(args.repo_root, ref)
    source, original = fetch_original_board(
        attempts=args.attempts, sleep_seconds=args.sleep_seconds
    )
    print(json.dumps(_retain(args.out_dir, source, original, companions, receipts), sort_keys=True))


if __name__ == "__main__":
    main()
