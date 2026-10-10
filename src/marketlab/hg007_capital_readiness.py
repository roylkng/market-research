"""Conservative capital-basis overlay on immutable 28-stock HG007 casework.

Original HG005/HG007 research results are never rewritten. A newer,
SHA-pinned INOXGREEN QIP denominator report marks its old March FD
market capitalization STALE, not as a newly verified fully diluted EV.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from marketlab.hg007_casework import build_casework_board, load_exact_sources

OVERLAY_ID = "HG007-P009-POST-QIP-28-CASE-CAPITAL-READINESS-v1"
QIP_AUDIT_ID = "HG007-P008-INOXGREEN-QIP-DATED-CAPITALIZATION-v1"
QIP_REPORT_PATH = Path(
    "research/hg007/inoxgreen-sep2026-qip/post-qip-market-cap-audit-v1.json"
)
QIP_REPORT_GIT_BLOB = "e31efd712fdfae378d7be8263883c521f1411d43"
QIP_ORIGINAL_PDF_SHA = (
    "cd1bee4fe84805e2ecbb274ebfedc74b632ad1c50907e694e58ba2f6d43470ee"
)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_casework_with_qip(root: Path) -> tuple[dict, dict, dict]:
    sources, originals = load_exact_sources(root)
    board = build_casework_board(sources, originals)
    raw = (root / QIP_REPORT_PATH).read_bytes()
    if _git_blob(raw) != QIP_REPORT_GIT_BLOB:
        raise ValueError("source-pinned HG007 P008 QIP capitalization changed")
    qip = json.loads(raw)
    if not isinstance(qip, dict):
        raise TypeError("QIP P008 report must be a JSON mapping")
    provenance = {
        "qip_audit_path": str(QIP_REPORT_PATH),
        "qip_audit_git_blob_sha": QIP_REPORT_GIT_BLOB,
        "qip_audit_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "hg007_original_source_count": len(originals),
    }
    return board, qip, provenance


def build_capital_readiness_overlay(
    board: dict[str, Any],
    qip: dict[str, Any],
    *,
    source_receipts: dict[str, Any],
) -> dict[str, Any]:
    if board.get("casework_id") != "HG007-P001-EVIDENCE-ACQUISITION-BOARD-v1":
        raise ValueError("original HG007 28-stock casework identity changed")
    cases = board.get("casework")
    if not isinstance(cases, list) or len(cases) != 28:
        raise ValueError("HG007 source casework must contain the original 28 stocks")
    originals = [case["symbol"] for case in cases]
    if len(set(originals)) != 28 or originals.count("INOXGREEN") != 1:
        raise ValueError("original 28-stock membership changed")
    if (
        qip.get("audit_id") != QIP_AUDIT_ID
        or qip.get("symbol") != "INOXGREEN"
        or qip.get("post_qip_fully_diluted_market_cap_authorized") is not False
        or qip.get("current_esop_and_option_balance_reverified") is not False
        or qip.get("cash_adjusted_enterprise_value_authorized") is not False
        or qip.get("stock_expected_returns_calculated") is not False
        or qip.get("live_capital_allowed") is not False
        or qip.get("source_provenance", {}).get("qip_original_pdf", {}).get("sha256")
        != QIP_ORIGINAL_PDF_SHA
    ):
        raise ValueError("post-QIP evidence cannot claim current FD/enterprise value")
    old = qip.get("frozen_hg005_oct1_historical_result_not_modified")
    dates = qip.get("post_qip_basic_share_capital_sensitivities")
    if not isinstance(old, dict) or not isinstance(dates, dict):
        raise TypeError("dated QIP source denominator must be present")
    oct1 = dates.get("2026-10-01")
    oct9 = dates.get("2026-10-09")
    if not isinstance(oct1, dict) or not isinstance(oct9, dict):
        raise TypeError("both 1 Oct and 9 Oct source price denominators required")
    corrected = oct1.get("implied_post_qip_basic_market_cap_inr_crore")
    newer = oct9.get("implied_post_qip_basic_market_cap_inr_crore")
    old_cap = old.get("reported_old_market_cap_inr_crore")
    if any(
        type(item) not in (int, float) or not math.isfinite(item) or item <= 0
        for item in (corrected, newer, old_cap)
    ):
        raise ValueError("verified dated QIP denominator values must be finite positive")
    if not (
        math.isclose(old_cap, 6422.9586735, abs_tol=1e-8)
        and math.isclose(corrected, 6671.6800362, abs_tol=1e-8)
        and math.isclose(newer, 5409.515662056, abs_tol=1e-8)
        and oct1.get("post_sep29_issued_basic_shares") == 419_602_518
        and oct9.get("post_sep29_issued_basic_shares") == 419_602_518
    ):
        raise ValueError("new QIP denominator must be exact source-derived P008")

    recorded_cases = []
    for case in cases:
        case_copy = deepcopy(case)
        if case["symbol"] == "INOXGREEN":
            if (
                case.get("price_reference_session") != "2026-10-01"
                or not math.isclose(
                    case.get("reported_fd_cap_reference_inr_cr_not_current"),
                    old_cap, abs_tol=1e-8
                )
                or case.get("economic_sensitivity_state")
                != "PAYOFF_FRAMEWORK_BLOCKED_SOURCE_PARTIAL"
            ):
                raise ValueError("original INOXGREEN casework source no longer agrees")
            case_copy["capital_basis_correction"] = {
                "status": "STALE_MARCH_FD_DENOMINATOR_AFTER_SEPTEMBER_QIP",
                "source_qip_audit_id": QIP_AUDIT_ID,
                "legacy_march_fd_cap_reference_at_oct1_inr_crore": old_cap,
                "sep29_post_qip_issued_basic_shares": 419_602_518,
                "oct1_same_price_post_qip_basic_cap_reference_inr_crore": corrected,
                "oct9_price_post_qip_basic_cap_reference_inr_crore": newer,
                "legacy_current_fd_reference_may_be_used_for_new_underwriting": False,
                "corrected_oct1_basic_reference_is_proven_current_fd": False,
                "corrected_oct9_basic_reference_is_proven_current_fd": False,
                "equity_and_cash_enterprise_valuation_allowed": False,
            }
        else:
            case_copy["capital_basis_correction"] = {
                "status": "NOT_REEVALUATED_UNDER_HG007_P009",
                "does_not_mean_current_capital_count_verified": True,
                "equity_and_cash_enterprise_valuation_allowed": False,
            }
        case_copy["stock_expected_returns_calculated"] = False
        case_copy["portfolio_eligibility_allowed"] = False
        case_copy["live_capital_allowed"] = False
        recorded_cases.append(case_copy)

    return {
        "schema_version": 1,
        "overlay_id": OVERLAY_ID,
        "classification": "28_CASE_SOURCE_READYNESS_OVERLAY_NOT_CURRENT_VALUATION_OR_ALPHA",
        "reference_date_ist": "2026-10-10",
        "source_receipts": source_receipts,
        "original_hg007_cohort_count_preserved": 28,
        "original_stock_selection_or_payoff_inputs_modified": False,
        "capital_denominator_stale_case_count": 1,
        "capital_denominator_stale_symbols": ["INOXGREEN"],
        "capital_denominator_unreviewed_others": 27,
        "casework_with_capital_readiness": recorded_cases,
        "company_probabilities_published": 0,
        "investment_opportunities_ranked": False,
        "company_expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
