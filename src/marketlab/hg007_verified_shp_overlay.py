"""Reconcile original Sept29 INOXGREEN FD/pledge into the 28-stock HG007 board.

This audit distinguishes public filing availability from as-of issuer
capital. The Sept29 exceptional XBRL was *published Oct8* and is NOT
an admissible public share count for an Oct1 point-in-time signal.

No current-Oct11 share count, enterprise value or return is established.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

AUDIT_ID = "HG007-P013-SEPT29-FD-PLEDGE-PUBLICATION-OVERLAY-v1"
SOURCES = {
    "old_28_casework": (
        "research/hg007/hg007-p009-28-case-capital-readiness-overlay-v1.json",
        "a502a582e93b408baba38dca7b95532836646700",
    ),
    "dated_qip_price_basis": (
        "research/hg007/inoxgreen-sep2026-qip/post-qip-market-cap-audit-v1.json",
        "e31efd712fdfae378d7be8263883c521f1411d43",
    ),
    "original_special_nse_shp": (
        "research/hg007/inoxgreen-post-qip-special/original-receipt-v1.json",
        "8990da5ab2d56c07b2f05942210861fab2eb17ba",
    ),
    "original_named_promoter_pledge": (
        "research/hg007/inoxgreen-post-qip-special/original-promoter-pledge-v1.json",
        "8a7d9efc1975b0790726663953ac2dd8ee5e67f0",
    ),
}
SOURCE_XBRL_SHA = (
    "6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822"
)
SOURCE_XBRL_PATH = Path(
    "research/hg007/inoxgreen-post-qip-special/raw/"
    + SOURCE_XBRL_SHA + ".xml"
)
ISSUED = 419_602_518
FD = 422_070_138
PLEDGED = 4_900_000
PRICE_OCT09 = 128.92
CRORE = 10_000_000


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_sources(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict]]:
    sources = {}
    provenance = {}
    for key, (path, sha) in SOURCES.items():
        raw = (root / path).read_bytes()
        if _git_blob(raw) != sha:
            raise ValueError(f"{key}: original Git source bytes have changed")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TypeError(f"{key}: expected source JSON object")
        sources[key] = data
        provenance[key] = {
            "path": path,
            "git_blob_sha": sha,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    raw_xbrl = (root / SOURCE_XBRL_PATH).read_bytes()
    if hashlib.sha256(raw_xbrl).hexdigest() != SOURCE_XBRL_SHA:
        raise ValueError("pinned original official September NSE XBRL was changed")
    provenance["original_nse_qip_xbrl"] = {
        "path": str(SOURCE_XBRL_PATH),
        "sha256": SOURCE_XBRL_SHA,
        "byte_count": len(raw_xbrl),
    }
    return sources, provenance


def build_asof_fd_governance_overlay(
    sources: dict[str, dict[str, Any]],
    receipts: dict[str, dict],
) -> dict[str, Any]:
    if set(sources) != set(SOURCES) or set(receipts) != set(SOURCES) | {
        "original_nse_qip_xbrl"
    }:
        raise ValueError("HG007-P013 needs four source reports and original XBRL")
    board = sources["old_28_casework"]
    qip = sources["dated_qip_price_basis"]
    orig = sources["original_special_nse_shp"]
    pledge = sources["original_named_promoter_pledge"]
    original_cases = board.get("casework_with_capital_readiness")
    if (
        board.get("overlay_id") != "HG007-P009-POST-QIP-28-CASE-CAPITAL-READINESS-v1"
        or board.get("capital_denominator_stale_symbols") != ["INOXGREEN"]
        or board.get("original_hg007_cohort_count_preserved") != 28
        or not isinstance(original_cases, list)
        or len(original_cases) != 28
        or board.get("live_capital_allowed") is not False
    ):
        raise ValueError("original source board membership/status invalid")
    symbols = [row.get("symbol") for row in original_cases]
    if len(set(symbols)) != 28 or symbols.count("INOXGREEN") != 1:
        raise ValueError("original 28-stock frozen selection changed")
    asof_original = orig.get("parsed_special_facts")
    if not isinstance(asof_original, dict):
        raise TypeError("original NSE shareholding XBRL fact block absent")
    if (
        orig.get("status") != "ORIGINAL_QIP_SPECIAL_XBRL_SHARE_COUNTS_PARSED"
        or orig.get("original_xbrl_sha256") != SOURCE_XBRL_SHA
        or asof_original.get("reported_issued_basic_shares_as_of_sep29") != ISSUED
        or asof_original.get("reported_fully_diluted_shares_as_of_sep29") != FD
        or asof_original.get("issuer_capital_date") != "2026-09-29"
        or asof_original.get("nse_public_broadcast_utc") != "2026-10-08T13:24:47Z"
        or asof_original.get("current_asof_oct11_fully_diluted_shares_confirmed") is not False
        or orig.get("live_capital_allowed") is not False
    ):
        raise ValueError("post-QIP original NSE time/FD facts changed")
    if (
        pledge.get("audit_id") != "HG007-P012-INOXGREEN-EXACT-SEPT29-PLEDGE-AND-FD-v1"
        or pledge.get("original_xbrl_sha256") != SOURCE_XBRL_SHA
        or pledge.get("listed_company_total_fully_diluted_shares") != FD
        or pledge.get("listed_company_total_basic_shares") != ISSUED
        or pledge.get("named_promoter_pledged_shares") != PLEDGED
        or pledge.get("promoter_group_total_pledged_shares") != PLEDGED
        or pledge.get("source_pledging_named_promoter") != "Inox Wind Limited"
        or pledge.get("reference_june_original_pledge_boolean") is not False
        or pledge.get("sept29_original_pledge_boolean") is not True
        or pledge.get("no_post_sep29_pledge_changes_verified") is not False
        or pledge.get("exact_date_pledge_created_verified") is not False
        or pledge.get("live_capital_allowed") is not False
    ):
        raise ValueError("official pledged-share quantity or as-of timeline differs")
    if (
        qip.get("audit_id") != "HG007-P008-INOXGREEN-QIP-DATED-CAPITALIZATION-v1"
        or qip.get("post_qip_fully_diluted_market_cap_authorized") is not False
        or qip.get("stock_expected_returns_calculated") is not False
    ):
        raise ValueError("original dated market-cap baseline changed")
    prices = qip.get("post_qip_basic_share_capital_sensitivities")
    if not isinstance(prices, dict) or not isinstance(prices.get("2026-10-09"), dict):
        raise TypeError("original official 9 Oct NSE close reference absent")
    oct9 = prices["2026-10-09"]
    if (
        not math.isclose(oct9.get("raw_nse_close_inr"), PRICE_OCT09, abs_tol=1e-12)
        or oct9.get("post_sep29_issued_basic_shares") != ISSUED
        or not math.isclose(
            oct9.get("implied_post_qip_basic_market_cap_inr_crore"),
            PRICE_OCT09 * ISSUED / CRORE,
            abs_tol=1e-8,
        )
    ):
        raise ValueError("frozen NSE Oct9 price/basic share denominator mismatch")

    time_public = "2026-10-08T13:24:47Z"
    reference_fd_oct9 = PRICE_OCT09 * FD / CRORE
    reference_extra = reference_fd_oct9 - oct9[
        "implied_post_qip_basic_market_cap_inr_crore"
    ]
    patched = []
    for row in original_cases:
        cloned = deepcopy(row)
        symbol = cloned["symbol"]
        if symbol == "INOXGREEN":
            if cloned.get("capital_basis_correction", {}).get("status") != (
                "STALE_MARCH_FD_DENOMINATOR_AFTER_SEPTEMBER_QIP"
            ):
                raise ValueError("original stale-price warning must be maintained")
            cloned["asof_29sep_exchange_source_update"] = {
                "status": "ORIGINAL_NSE_QIP_SPECIAL_XBRL_CONFIRMED_AS_OF_SEP29",
                "original_first_public_broadcast_utc": time_public,
                "fully_diluted_shares_as_of_sep29": FD,
                "issued_basic_shares_as_of_sep29": ISSUED,
                "outstanding_dilutive_shares_as_of_sep29": FD-ISSUED,
                "named_pledging_promoter": "Inox Wind Limited",
                "pledged_shares_at_sep29": PLEDGED,
                "pledged_percent_of_promoter_group": pledge[
                    "pledged_percent_of_promoter_group"
                ],
                "pledged_percent_of_all_issued_shares": pledge[
                    "pledged_percent_of_all_issued"
                ],
                "reference_oct9_source_price_inr": PRICE_OCT09,
                "sept29_fd_shares_at_oct9_price_inr_crore": reference_fd_oct9,
                "reference_delta_above_basic_valuation_inr_crore": reference_extra,
                "oct1_use_as_publicly_visible_fd_denominator_allowed": False,
                "oct9_reference_proves_no_interim_capital_changes": False,
                "oct11_current_issued_and_fd_verified": False,
                "pledge_creation_date_and_loan_terms_verified": False,
                "current_fair_value_or_forward_returns_permitted": False,
            }
        else:
            cloned["asof_29sep_exchange_source_update"] = {
                "status": "NOT_REVIEWED_IN_P013",
                "does_not_mean_no_promoter_pledge_or_share_dilution": True,
                "current_fair_value_or_forward_returns_permitted": False,
            }
        cloned["stock_valuation_ready"] = False
        cloned["portfolio_eligibility_allowed"] = False
        cloned["live_capital_allowed"] = False
        patched.append(cloned)
    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "ASOF_SHAREHOLDING_AND_GOVERNANCE_NOT_ALPHA_OR_CURRENT_EV",
        "prepared_date_ist": "2026-10-11",
        "original_28_case_count": len(patched),
        "revised_case_count": 1,
        "unreviewed_other_issuer_count": 27,
        "original_frozen_selection_or_company_payoffs_revised": False,
        "original_nse_xbrl_asof_date": "2026-09-29",
        "original_nse_xbrl_public_at_utc": time_public,
        "forward_usable_only_after_original_first_public_broadcast": True,
        "source_receipts": receipts,
        "company_cases": patched,
        "case_specific_completion_probabilities_published": 0,
        "verified_current_oct11_fully_diluted_share_counts": 0,
        "portfolio_eligibility_allowed": False,
        "stock_expected_returns_calculated": False,
        "live_capital_allowed": False,
    }
