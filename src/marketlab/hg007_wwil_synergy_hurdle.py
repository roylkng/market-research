"""Source-pinned WWIL management post-synergy EBITDA reality-check.

The 7 Oct 2026 original BSE company press release (PDF SHA fixed below)
is a *management expectation*, not a historical audited carve-out EBITDA
statement. A headline ₹550cr/2x EBITDA is not a verified EV/EBITDA price.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from marketlab.ss002_text import _pdf_segments

ANALYSIS_ID = "HG007-P012-WWIL-ORIGINAL-SYNERGY-EBITDA-HURDLE-v1"
PRESS_SHA = "0a5a0f5028f07363311621e697f4a871e9baf59610777e4c40a54ac48be88bc9"
PDF_RELATIVE = Path(
    "research/hg007/wwil-oct7-press/raw/sha256/" + PRESS_SHA + ".pdf"
)
RECEIPT_RELATIVE = Path(
    "research/hg007/wwil-oct7-press/original-source-receipt-v1.json"
)
RECEIPT_GIT_BLOB_SHA = "18b073899d0a73443d741aa5aa12a5ae5eb335ed"

# Declared explicitly as manager-reported approximations rather than audited facts.
MANAGEMENT_HEADLINE_CONSIDERATION_CRORE = 550.0
MANAGEMENT_REPORTED_FY26_TURNOVER_CRORE = 580.0
MANAGEMENT_POST_SYNERGY_PURCHASE_MULTIPLE = 2.0
MANAGEMENT_CONTRACTUAL_ESCALATION_PCT = 5.0
MARGIN_STRESS_PCT = (15.0, 25.0, 35.0, 40.0)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold())


def _first_match(segments: list[dict], pattern: str) -> dict:
    matches = [
        row for row in segments
        if re.search(pattern, _normal(row["text"]), re.IGNORECASE)
    ]
    if not matches:
        raise ValueError("original issuer press PDF does not contain required management claim")
    row = matches[0]
    return {
        "page_number": row["locator"]["page_number"],
        "page_text_sha256": row["text_sha256"],
        "source_pdf_sha256": PRESS_SHA,
    }


def load_original_press(root: Path) -> tuple[bytes, dict[str, Any], dict]:
    raw = (root / PDF_RELATIVE).read_bytes()
    if (
        hashlib.sha256(raw).hexdigest() != PRESS_SHA
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
        or len(raw) != 459650
    ):
        raise ValueError("original BSE management press PDF SHA or byte count changed")
    receipt_bytes = (root / RECEIPT_RELATIVE).read_bytes()
    if _git_blob(receipt_bytes) != RECEIPT_GIT_BLOB_SHA:
        raise ValueError("original BSE press source custody receipt Git blob changed")
    receipt = json.loads(receipt_bytes)
    if not isinstance(receipt, dict):
        raise TypeError("original press receipt must be JSON object")
    if (
        receipt.get("document_id") != "HG007-P011-WWIL-2026-10-07-ORIGINAL-BSE-PRESS-v1"
        or receipt.get("source_status") != "BSE_ORIGINAL_PRESS_PDF_CAPTURED_UNREVIEWED"
        or receipt.get("source_original_pdf_sha256") != PRESS_SHA
        or receipt.get("source_original_pdf_byte_count") != len(raw)
        or receipt.get("http_status") != 200
        or receipt.get("management_2x_post_synergy_ebitda_multiple_semantically_approved") is not False
        or receipt.get("live_capital_allowed") is not False
    ):
        raise ValueError("original BSE WWIL press source custody receipt identity changed")
    return raw, receipt, {
        "original_pdf_path": str(PDF_RELATIVE),
        "original_pdf_sha256": PRESS_SHA,
        "original_pdf_byte_count": len(raw),
        "original_receipt_git_blob_sha": RECEIPT_GIT_BLOB_SHA,
        "original_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
    }


def build_wwil_management_hurdle(
    raw_original_pdf: bytes, receipt: dict[str, Any], source: dict
) -> dict[str, Any]:
    if hashlib.sha256(raw_original_pdf).hexdigest() != PRESS_SHA:
        raise ValueError("management hurdle must bind to exact original BSE press")
    if receipt.get("source_original_pdf_sha256") != PRESS_SHA:
        raise ValueError("original filing receipt differs from input source PDF")
    segments, extraction = _pdf_segments(
        raw_original_pdf, document_id=PRESS_SHA, prefix="HG007-P012"
    )
    pages = extraction.get("page_count")
    if (
        type(pages) is not int or not 1 <= pages <= 10
        or extraction.get("failed_page_count") != 0
        or extraction.get("empty_page_count") != 0
        or extraction.get("text_page_count") != pages
        or len(segments) != pages
    ):
        raise ValueError("original BSE company press has unreadable or missing pages")
    text = _normal("\n".join(row["text"] for row in segments))
    if "inox green" not in text or "wind world" not in text:
        raise ValueError("original source press issuer/asset identity mismatch")
    if not re.search(r"(?:~|approx(?:imately)?)?\s*2\s*x\s*ebitda", text):
        raise ValueError("original issuer press has no 2x EBITDA management wording")
    if "synerg" not in text or "over the next year" not in text:
        raise ValueError("original issuer press does not state future synergy timing")
    if not re.search(r"(?:rs\.?|inr|₹)\s*550\s*crore", text):
        raise ValueError("original issuer press does not support 550 crore amount")
    if not re.search(r"(?:rs\.?|inr|₹)\s*580\s*crore", text):
        raise ValueError("original issuer press does not support 580 crore turnover")
    if not re.search(r"5\s*%", text):
        raise ValueError("original issuer press does not support 5pct escalation reference")

    purchase = MANAGEMENT_HEADLINE_CONSIDERATION_CRORE
    turnover = MANAGEMENT_REPORTED_FY26_TURNOVER_CRORE
    multiple = MANAGEMENT_POST_SYNERGY_PURCHASE_MULTIPLE
    management_implied = purchase / multiple
    if not math.isclose(management_implied, 275.0, abs_tol=1e-9):
        raise ValueError("source management arithmetic drifted")
    if any(m <= 0 or m >= 100 for m in MARGIN_STRESS_PCT):
        raise ValueError("EBITDA margin stress must stay positive but below revenue")
    cases = []
    for margin in (*MARGIN_STRESS_PCT, 100 * management_implied / turnover):
        illustrative_ebitda = turnover * margin / 100
        cases.append({
            "illustrative_ebitda_margin_pct_of_reported_fy26_turnover": margin,
            "arithmetic_annual_ebitda_inr_crore": illustrative_ebitda,
            "headline_550cr_cash_consideration_divided_by_ebitda": (
                purchase / illustrative_ebitda
            ),
            "is_earnings_observation": False,
            "is_fair_value_enterprise_multiple": False,
        })
    return {
        "schema_version": 1,
        "analysis_id": ANALYSIS_ID,
        "classification": "MANAGEMENT_FORWARD_SYNERGY_HURDLE_NOT_NORMALIZED_EBITDA_OR_ALPHA",
        "listed_issuer": "INOXGREEN",
        "source_provenance": source,
        "original_pdf_page_count": pages,
        "original_pdf_page_text_sha256": [row["text_sha256"] for row in segments],
        "issuer_reported_claim_source_pages": {
            "management_2x_post_synergy_multiple": _first_match(
                segments, r"2\s*x\s*ebitda"
            ),
            "reported_580cr_fy26_turnover": _first_match(
                segments, r"(?:rs\.?|inr|₹)\s*580\s*crore"
            ),
            "management_synergies_future_year": _first_match(
                segments, r"over the next year"
            ),
            "contract_5pct_escalation": _first_match(segments, r"5\s*%"),
        },
        "management_reported_consideration_inr_crore": purchase,
        "management_reported_fy26_business_turnover_approx_inr_crore": turnover,
        "management_claimed_post_synergy_consideration_ebitda_multiple_approx": multiple,
        "reverse_implied_future_annual_ebitda_inr_crore_if_quote_basis_comparable": (
            management_implied
        ),
        "reverse_implied_ebitda_margin_on_older_fy26_turnover_pct": (
            100 * management_implied / turnover
        ),
        "note_forward_ebitda_vs_prior_fy26_turnover_are_not_same_period": True,
        "reported_contract_price_escalation_pct_not_guaranteed_total_revenue_growth": (
            MANAGEMENT_CONTRACTUAL_ESCALATION_PCT
        ),
        "nonforecast_illustrative_margin_stress": cases,
        "illustrative_multiple_is_issuer_claim_not_audited_transaction_ev_ebitda": True,
        "acquired_business_historical_normalized_ebitda_verified": False,
        "post_synergy_ebitda_achieved": False,
        "full_wwil_business_transfer_completed_verified": False,
        "third_party_debt_minority_and_group_eliminations_verified": False,
        "wwil_maintenance_capex_and_cash_conversion_verified": False,
        "fully_diluted_parent_equity_count_verified": False,
        "stock_target_price_authorized": False,
        "company_completion_probability_published": False,
        "company_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
