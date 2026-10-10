"""Correct historical INOXGREEN QIP-denominator mismatch without alpha claims.

Original HG005 1-Oct-2026 share count is the issuer's *March 2026*
fully diluted count, not the basic capital after the 29-Sep QIP.
P008 retains the original result and makes exact point-in-time alternative
basic capitalizations; it NEVER presents post-QIP FD as verified.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

AUDIT_ID = "HG007-P008-INOXGREEN-QIP-DATED-CAPITALIZATION-v1"
SOURCE_BLOBS = {
    "hg005_original_2026_10_01": (
        "research/hg005-d001-result-v1.json",
        "2dbbc3055d1aacec8a37dd510a1a75a3c7868006",
    ),
    "ss002_official_2026_10_09": (
        "research/ss002-p007-result-v1.json",
        "ac8384ea4dfc2642411881165a3255e2553dd6fb",
    ),
    "qip_original_nse_receipt": (
        "research/hg007/inoxgreen-sep2026-qip/original-receipt-v1.json",
        "c0a6db1d3293c79932ce46b5a2a89fe647339ce8",
    ),
}
ORIGINAL_QIP_PDF_SHA256 = (
    "cd1bee4fe84805e2ecbb274ebfedc74b632ad1c50907e694e58ba2f6d43470ee"
)
ORIGINAL_QIP_PDF_RELATIVE_PATH = (
    "research/hg007/inoxgreen-sep2026-qip/raw/sha256/"
    + ORIGINAL_QIP_PDF_SHA256
    + ".pdf"
)
OFFICIAL_MARCH_SHP = "https://www.inoxgreen.com/PDF/SHP_31.03.2026.html"
INR_CRORE = 10_000_000
MARCH_2026_BASIC_SHARES = 401_492_045
MARCH_2026_REPORTED_ESOP = 2_467_620
MARCH_2026_FD_SHARES = 403_959_665
QIP_ISSUE_SHARES = 18_110_473
SEP29_ISSUED_SHARES = 419_602_518


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _read_pinned_json(root: Path, key: str) -> tuple[dict[str, Any], dict]:
    path, expected_sha = SOURCE_BLOBS[key]
    raw = (root / path).read_bytes()
    git_sha = _git_blob(raw)
    if git_sha != expected_sha:
        raise ValueError(f"QIP denominator original source drifted: {key}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("original result or receipt must contain a JSON object")
    return payload, {
        "path": path,
        "git_blob_sha": git_sha,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def load_verified_source_references(root: Path) -> tuple[dict, dict, dict, dict]:
    old, old_receipt = _read_pinned_json(root, "hg005_original_2026_10_01")
    oct9, oct9_receipt = _read_pinned_json(root, "ss002_official_2026_10_09")
    qip, qip_receipt = _read_pinned_json(root, "qip_original_nse_receipt")
    raw = (root / ORIGINAL_QIP_PDF_RELATIVE_PATH).read_bytes()
    if (
        hashlib.sha256(raw).hexdigest() != ORIGINAL_QIP_PDF_SHA256
        or len(raw) != 309090
        or not raw.startswith(b"%PDF-")
        or b"%%EOF" not in raw[-2048:]
    ):
        raise ValueError("retained original NSE QIP PDF bytes fail immutable hash")
    if (
        qip.get("capture_id") != "HG007-P007-INOXGREEN-SEP29-QIP-EXCHANGE-ORIGINAL-v1"
        or qip.get("source_original_pdf_sha256") != ORIGINAL_QIP_PDF_SHA256
        or qip.get("source_original_pdf_bytes") != len(raw)
        or qip.get("http_status") != 200
        or qip.get("state") != "ORIGINAL_NSE_QIP_PDF_CAPTURED_TEXT_IDENTITY_PASSED"
        or qip.get("qip_original_document_allotment_identity_confirmed") is not True
        or qip.get("current_fully_diluted_share_count_verified") is not False
        or qip.get("portfolio_eligibility_allowed") is not False
        or qip.get("live_capital_allowed") is not False
    ):
        raise ValueError("original NSE QIP source receipt identity mismatch")
    receipts = {
        "hg005_original_2026_10_01": old_receipt,
        "ss002_official_2026_10_09": oct9_receipt,
        "qip_original_nse_receipt": qip_receipt,
        "qip_original_pdf": {
            "path": ORIGINAL_QIP_PDF_RELATIVE_PATH,
            "sha256": ORIGINAL_QIP_PDF_SHA256,
            "byte_count": len(raw),
        },
    }
    return old, oct9, qip, receipts


def _price(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(float(value)) or value <= 0:
        raise ValueError(f"{label}: must be finite positive INR")
    return float(value)


def build_qip_denominator_audit(
    old: dict[str, Any],
    oct9: dict[str, Any],
    qip: dict[str, Any],
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """No current net cash, new FD shares or investment returns are inferred."""
    if (
        old.get("context_id") != "HG005-D001-v1"
        or old.get("price_session") != "2026-10-01"
        or old.get("expected_returns_calculated", False) is not False
        or old.get("live_capital_allowed") is not False
    ):
        raise ValueError("HG005 original market baseline changed")
    if (
        oct9.get("diagnostic_id") != "SS002-P007-v1"
        or oct9.get("price_session") != "2026-10-09"
        or oct9.get("live_capital_allowed") is not False
        or oct9.get("expected_returns_calculated") is not False
    ):
        raise ValueError("9 October official stock close source changed")
    original = old.get("key_mechanical_context", {}).get("INOXGREEN")
    if not isinstance(original, dict):
        raise ValueError("HG005 original INOXGREEN payoff source missing")
    close_oct1 = _price(original.get("close_price_inr"), "Oct 1 official close")
    old_fd_cap = _price(
        original.get("reported_fd_market_cap_inr_crore"), "old FD market cap"
    )
    close_oct9 = _price(
        oct9.get("case_prices_inr", {}).get("INOXGREEN"), "Oct 9 official close"
    )
    if (
        close_oct1 != 159.0
        or close_oct9 != 128.92
        or oct9.get("official_bhavcopy_sha256") != (
            "8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c"
        )
        or not math.isclose(
            old_fd_cap, MARCH_2026_FD_SHARES * close_oct1 / INR_CRORE,
            abs_tol=1e-8,
        )
    ):
        raise ValueError("old market denominator or official Oct 9 source drifted")
    old_lane = original.get("lanes", {}).get("ACQUISITION_ECONOMICS", {})
    old_consideration = _price(
        old_lane.get("stated_consideration_inr_crore"), "WWIL stated consideration"
    )
    if (
        old_consideration != 550.0
        or not math.isclose(
            old_lane.get("consideration_to_reported_fd_market_cap"),
            old_consideration / old_fd_cap,
            abs_tol=1e-12,
        )
    ):
        raise ValueError("HG005 frozen payoff fraction does not reconcile")

    issued = qip.get("source_page_text_provenance")
    if not isinstance(issued, dict):
        raise ValueError("QIP original three-page issuer source evidence absent")
    if (
        issued.get("issuer_reported_date") != "2026-09-30"
        or issued.get("qip_allotment_date") != "2026-09-29"
        or issued.get("qip_allotted_shares") != QIP_ISSUE_SHARES
        or issued.get("pre_qip_issued_shares") != MARCH_2026_BASIC_SHARES
        or issued.get("post_qip_issued_shares") != SEP29_ISSUED_SHARES
        or issued.get("qip_issue_price_inr") != 165.65
        or issued.get("qip_total_consideration_inr") != 2_999_999_852.45
        or issued.get("current_fully_diluted_shares_verified") is not False
        or issued.get("current_esop_outstanding_verified") is not False
        or issued.get("page_count") != 3
    ):
        raise ValueError("original NSE issuer QIP allotted capital counts changed")
    if MARCH_2026_BASIC_SHARES + MARCH_2026_REPORTED_ESOP != MARCH_2026_FD_SHARES:
        raise ValueError("March shareholding FD/basic/options identity mismatch")
    if MARCH_2026_BASIC_SHARES + QIP_ISSUE_SHARES != SEP29_ISSUED_SHARES:
        raise ValueError("post-QIP original allotted-share arithmetic failed")
    if SEP29_ISSUED_SHARES <= MARCH_2026_FD_SHARES:
        raise ValueError("old March FD must understate post-QIP issued basic shares")

    # Both share-base and price dates are explicit; prices are observations,
    # not execution fills, and the QIP is legally allotted on Sep 29 even
    # though the shares are first admitted to BSE trading from October 5.
    cap_oct1_basic = SEP29_ISSUED_SHARES * close_oct1 / INR_CRORE
    cap_oct9_basic = SEP29_ISSUED_SHARES * close_oct9 / INR_CRORE
    # This is an *illustration only*. Mar options have not been reverified.
    hypothetical_fd = SEP29_ISSUED_SHARES + MARCH_2026_REPORTED_ESOP
    cap_oct1_hypo_fd = hypothetical_fd * close_oct1 / INR_CRORE
    cap_oct9_hypo_fd = hypothetical_fd * close_oct9 / INR_CRORE

    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": (
            "POST_QIP_DATED_BASIC_MARKET_DENOMINATOR_CORRECTION_NOT_FD_OR_TARGET_PRICE"
        ),
        "symbol": "INOXGREEN",
        "isin": "INE510W01014",
        "prepared_date_ist": "2026-10-10",
        "source_provenance": provenance,
        "march_31_2026_official_issuer_shareholding_url": OFFICIAL_MARCH_SHP,
        "march_31_2026_official_shareholding_reference": {
            "report_date": "2026-03-31",
            "issued_basic_shares": MARCH_2026_BASIC_SHARES,
            "reported_outstanding_esop_shares": MARCH_2026_REPORTED_ESOP,
            "reported_fully_diluted_shares": MARCH_2026_FD_SHARES,
            "march_report_is_not_a_sep_or_oct_shareholding_confirmation": True,
        },
        "original_september_2026_nse_qip": {
            "allotment_date": "2026-09-29",
            "issuer_disclosure_date": "2026-09-30",
            "qip_new_issued_shares": QIP_ISSUE_SHARES,
            "pre_qip_issued_shares": MARCH_2026_BASIC_SHARES,
            "post_qip_issued_basic_shares": SEP29_ISSUED_SHARES,
            "issuer_reported_issue_price_inr": 165.65,
            "issuer_reported_gross_issue_proceeds_inr_crore": (
                issued["qip_total_consideration_inr"] / INR_CRORE
            ),
            "first_bse_admission_date_reported_separately": "2026-10-05",
            "current_fully_diluted_share_count_verified": False,
        },
        "frozen_hg005_oct1_historical_result_not_modified": {
            "source_price_session": "2026-10-01",
            "raw_close_inr": close_oct1,
            "march_fd_shares_used": MARCH_2026_FD_SHARES,
            "reported_old_market_cap_inr_crore": old_fd_cap,
            "old_550cr_consideration_to_reported_fd_cap": (
                old_consideration / old_fd_cap
            ),
            "current_fd_capitalization_label_is_stale_after_sep29_qip": True,
        },
        "post_qip_basic_share_capital_sensitivities": {
            "2026-10-01": {
                "raw_nse_close_inr": close_oct1,
                "post_sep29_issued_basic_shares": SEP29_ISSUED_SHARES,
                "implied_post_qip_basic_market_cap_inr_crore": cap_oct1_basic,
                "old_hg005_market_cap_shortfall_against_post_qip_basic_inr_crore": (
                    cap_oct1_basic - old_fd_cap
                ),
                "old_hg005_denominator_understatement_vs_new_basic_pct": (
                    100 * (cap_oct1_basic / old_fd_cap - 1)
                ),
                "reported_550cr_purchase_consideration_to_basic_cap": (
                    old_consideration / cap_oct1_basic
                ),
            },
            "2026-10-09": {
                "raw_nse_close_inr": close_oct9,
                "price_source_original_udiff_sha256": oct9["official_bhavcopy_sha256"],
                "post_sep29_issued_basic_shares": SEP29_ISSUED_SHARES,
                "implied_post_qip_basic_market_cap_inr_crore": cap_oct9_basic,
                "reported_550cr_purchase_consideration_to_basic_cap": (
                    old_consideration / cap_oct9_basic
                ),
                "oct1_to_oct9_raw_unadjusted_reference_price_change_pct": (
                    100 * (close_oct9 / close_oct1 - 1)
                ),
            },
        },
        "non_authoritative_same_march_esop_count_scenario": {
            "assumption": (
                "ONLY_IF all 2,467,620 March outstanding ESOP shares still remained "
                "outstanding after the Sep29 QIP, with no intervening changes"
            ),
            "assumed_qip_plus_march_options_shares": hypothetical_fd,
            "oct1_hypothetical_fd_market_cap_inr_crore": cap_oct1_hypo_fd,
            "oct9_hypothetical_fd_market_cap_inr_crore": cap_oct9_hypo_fd,
            "scenario_is_a_verified_current_fd_market_cap": False,
        },
        "remaining_share_and_enterprise_value_blockers": [
            "CURRENT_AS_OF_SEP29_OR_LATER_ESOP_AND_OTHER_CONVERTIBLE_SHARE_COUNTS",
            "POST_QIP_REGULATION_31_SHAREHOLDING_PATTERN_OR_TRANSFER_AGENT_CONFIRMATION",
            "ANY_POST_SEP29_ADDITIONAL_ISSUANCE_OR_EXERCISE_EVENTS",
            "QIP_NET_PROCEEDS_ALLOCATIONS_FEES_AND_ACTUAL_CASH_POSITION",
            "WWIL_ACQUISITION_FUNDING_AND_THIRD_PARTY_RECOURSE_CONSOLIDATION",
            "LOAN_CONVERSION_CLASS_PRICE_CONTROL_AND_MINORITIES_AT_VIBHAV",
            "INDEPENDENT_HORIZON_SHARE_ACTION_DIVIDEND_ADJUSTMENTS",
        ],
        "price_basis": "RAW_OFFICIAL_NSE_OBSERVATION_NOT_EXECUTABLE_FILL",
        "current_issued_shares_as_of_oct9_independently_reverified": False,
        "current_esop_and_option_balance_reverified": False,
        "post_qip_fully_diluted_market_cap_authorized": False,
        "cash_adjusted_enterprise_value_authorized": False,
        "valuation_multiple_or_target_price_authorized": False,
        "stock_expected_returns_calculated": False,
        "prospective_return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def current_denominator_required(report: dict[str, Any]) -> None:
    """Never substitute a dated basic-share observation for post-QIP FD."""
    if report.get("audit_id") != AUDIT_ID:
        raise ValueError("unexpected HG007 QIP denominator research report")
    if (
        report.get("post_qip_fully_diluted_market_cap_authorized") is not True
        or report.get("current_esop_and_option_balance_reverified") is not True
        or report.get("cash_adjusted_enterprise_value_authorized") is not True
    ):
        raise ValueError("post-QIP company FD/enterprise value remains source-blocked")
    raise ValueError("P008 is a dated capitalization correction, not FD/EV approval")
