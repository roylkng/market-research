"""Project first-party INOXGREEN dilution/pledge into 28-company casework.

Never rewrite the historical HG007 P001/P009 casework or infer unreviewed
ownership/valuation quality for other 27 companies. P012 is a dated
source-evidence integrity overlay, not an investment ranking.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

ID = "HG007-P012-28-CASE-OFFICIAL-OWNERSHIP-RECONCILIATION-v1"
P009_PATH = Path("research/hg007/hg007-p009-28-case-capital-readiness-overlay-v1.json")
P011_PATH = Path("research/hg007/inoxgreen-post-qip-reg31/sep29-reported-fd-promoter-pledge-v1.json")
P009_GIT_BLOB = "a502a582e93b408baba38dca7b95532836646700"
P011_GIT_BLOB = "f84025b2be5d7d2790f0e0e8b2374879c95bae00"
ORIGINAL_REG31_XML_SHA = (
    "6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822"
)


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_exact_case_sources(root: Path) -> tuple[dict, dict, dict[str, dict]]:
    sources = {}
    receipts = {}
    for name, path, expected in (
        ("p009_all_28", P009_PATH, P009_GIT_BLOB),
        ("p011_original_sep29", P011_PATH, P011_GIT_BLOB),
    ):
        raw = (root / path).read_bytes()
        if _blob(raw) != expected:
            raise ValueError(f"{name} original archived research source changed")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TypeError(f"{name} must be original JSON object")
        sources[name] = data
        receipts[name] = {
            "path": str(path),
            "original_git_blob_sha": expected,
            "original_raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return sources["p009_all_28"], sources["p011_original_sep29"], receipts


def build_ownership_case_overlay(p009: dict, p011: dict, sources: dict) -> dict:
    rows = p009.get("casework_with_capital_readiness")
    if (
        p009.get("overlay_id") != "HG007-P009-POST-QIP-28-CASE-CAPITAL-READINESS-v1"
        or p009.get("original_hg007_cohort_count_preserved") != 28
        or p009.get("capital_denominator_stale_symbols") != ["INOXGREEN"]
        or p009.get("capital_denominator_stale_case_count") != 1
        or p009.get("live_capital_allowed") is not False
        or not isinstance(rows, list)
        or len(rows) != 28
    ):
        raise ValueError("original 28-company casework or capital-readiness state changed")
    index: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("casework must contain source objects")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in index:
            raise ValueError("casework has duplicate/invalid issuer symbol")
        if (
            row.get("stock_valuation_ready") is not False
            or row.get("live_capital_allowed") is not False
            or row.get("portfolio_eligibility_allowed") is not False
        ):
            raise ValueError(f"{symbol}: historical casework was capital-promoted")
        index[symbol] = row
    if len(index) != 28 or "INOXGREEN" not in index:
        raise ValueError("original HG007 mechanically selected 28 are not intact")

    ino = index["INOXGREEN"]
    historical = ino.get("capital_basis_correction")
    if not isinstance(historical, dict) or (
        historical.get("status") != "STALE_MARCH_FD_DENOMINATOR_AFTER_SEPTEMBER_QIP"
    ):
        raise ValueError("original INOXGREEN stale March reference missing")
    if (
        p011.get("review_id") != "HG007-P011-INOXGREEN-SEP29-ORIGINAL-FD-AND-PLEDGE-v1"
        or p011.get("shareholding_report_date") != "2026-09-29"
        or p011.get("shareholding_first_broadcast_utc") != "2026-10-08T13:24:47Z"
        or p011.get("original_nse_raw_xbrl_sha256") != ORIGINAL_REG31_XML_SHA
        or p011.get("reported_paid_issued_shares") != 419_602_518
        or p011.get("reported_fully_diluted_shares_including_esop") != 422_070_138
        or p011.get("reported_outstanding_esop_shares") != 2_467_620
        or p011.get("no_other_convertibles_or_warrants_reported") is not True
        or p011.get("reported_promoter_shares") != 225_317_291
        or p011.get("reported_promoter_pledged_shares") != 4_900_000
        or p011.get("pledge_lender_collateral_terms_and_creation_date_verified") is not False
        or p011.get("oct12_current_fd_share_count_independently_verified") is not False
        or p011.get("live_capital_allowed") is not False
    ):
        raise ValueError("original issuer Sep29 shareholdings or source vintage changed")
    if not math.isclose(p011.get("reported_promoter_ownership_pct"), 53.7):
        raise ValueError("original issuer promoter ownership differs from Reg31")
    if not math.isclose(p011.get("reported_promoter_pledge_pct_promoter_shares"), 2.17):
        raise ValueError("original NSE share pledge percentage differs")
    reported = p011.get("original_cash_purchased_price_reference_dates")
    if not isinstance(reported, dict):
        raise TypeError("original reported FD dated research is missing")
    if (
        not math.isclose(
            reported["2026-10-01"]["sep29_reported_fd_market_cap_inr_crore"],
            6710.9151942,
            abs_tol=1e-8,
        )
        or reported["2026-10-01"]["source_reg31_filing_was_public_at_price_close"] is not False
        or not math.isclose(
            reported["2026-10-09"]["sep29_reported_fd_market_cap_inr_crore"],
            5441.328219096,
            abs_tol=1e-8,
        )
        or reported["2026-10-09"]["source_reg31_filing_was_public_at_price_close"] is not True
        or not math.isclose(
            historical["oct9_price_post_qip_basic_cap_reference_inr_crore"],
            5409.515662056,
            abs_tol=1e-8,
        )
    ):
        raise ValueError("new original FD values disagree with frozen basic-cap source")

    members = []
    for symbol in sorted(index):
        older = index[symbol]
        if symbol == "INOXGREEN":
            evidence = {
                "evidence_state": "OFFICIAL_SEP29_REPORTED_FD_AND_PROMOTER_PLEDGE_RECONCILED",
                "source_report_date_ist": "2026-09-29",
                "source_broadcast_at_utc": "2026-10-08T13:24:47Z",
                "original_nse_xbrl_sha256": ORIGINAL_REG31_XML_SHA,
                "fully_paid_issued_shares_asof_report": 419_602_518,
                "fully_diluted_shares_including_esop_asof_report": 422_070_138,
                "issued_vs_fd_increment_equals_reported_esop": True,
                "outstanding_esop_shares_asof_report": 2_467_620,
                "promoter_reported_percentage": 53.7,
                "promoter_pledged_shares_asof_report": 4_900_000,
                "promoter_pledged_shares_percentage_of_promoter_holdings": 2.17,
                "promoter_pledge_is_a_diligence_risk_not_an_auto_sell_signal": True,
                "dated_oct1_reported_fd_cap_inr_crore_retrospective": 6710.9151942,
                "oct1_source_not_yet_published": True,
                "dated_oct9_reported_fd_cap_inr_crore_not_current_12oct": 5441.328219096,
                "original_stale_march_fd_cap_cannot_be_current": True,
                "current_oct12_fd_shares_verified": False,
                "pledge_lender_and_effective_dates_verified": False,
                "consolidated_net_cash_debt_verified": False,
                "wwil_target_normalized_free_cashflow_verified": False,
                "issuer_live_transaction_close_verified": False,
                "risk_adjusted_shareholder_expected_return_published": False,
            }
        else:
            if older.get("capital_basis_correction", {}).get("status") != (
                "NOT_REEVALUATED_UNDER_HG007_P009"
            ):
                raise ValueError("non-INOXGREEN company capital basis unexpectedly reviewed")
            evidence = {
                "evidence_state": "NOT_REVIEWED_UNDER_P012",
                "current_ownership_and_pledge_verified_by_this_review": False,
                "no_pledge_or_equity_dilution_is_not_established": True,
                "current_market_capitalization_verified_by_this_review": False,
            }
        members.append({
            "symbol": symbol,
            "hg003_original_transaction_state": older.get("hg003_thread_state"),
            "original_evidence_acquisition_route": older.get("evidence_acquisition_route"),
            "source_date_of_old_market_context": older.get("price_reference_session"),
            "additional_post_qip_original_ownership_review": evidence,
            "fundamental_underwriting_completed": False,
            "current_buy_recommendation_authorized": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        })

    return {
        "schema_version": 1,
        "casebook_id": ID,
        "classification": "SOURCE_RECONCILIATION_AND_GOVERNANCE_RISK_NOT_EQUITY_ALPHA",
        "prepared_date_ist": "2026-10-12",
        "source_provenance": sources,
        "original_hg007_28_member_count": 28,
        "source_verified_new_dilution_pledge_cases": ["INOXGREEN"],
        "unreviewed_company_count": 27,
        "promoter_pledge_does_not_imply_a_verified_default": True,
        "september_original_report_not_proof_of_oct12_current_status": True,
        "casework": members,
        "selected_stocks_changed": False,
        "stock_level_alpha_trials_claimed": 0,
        "expected_returns_calculated": False,
        "investment_recommendations_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
