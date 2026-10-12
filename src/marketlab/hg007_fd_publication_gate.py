"""Time-aware original NSE Sep-29 fully diluted shareholdings for INOXGREEN.

A dated issuer report is never assumed public at its report date. The exact
Sep29 original XBRL first became public Oct8, so no earlier investment
selection may use it. Sept-dated FD is NOT confirmed unchanged on Oct13.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.hg005_context import parse_shareholding_counts

AUDIT_ID = "HG007-P044-INOXGREEN-DATED-ORIGINAL-FD-PUBLICATION-GATE-v1"
FROZEN_SOURCES = {
    "P008_OCT_CAP": (
        "research/hg007/inoxgreen-sep2026-qip/post-qip-market-cap-audit-v1.json",
        "e31efd712fdfae378d7be8263883c521f1411d43",
    ),
    "P040_PROMOTER_GOVERNANCE": (
        "research/hg007/hg007-p040-net-promoter-share-reconciliation-v1.json",
        "67cb75745c408e48c5910a2ce83a3733e965f6ac",
    ),
}
SEPT_ORIGINAL_XBRL = (
    "research/hg007/inoxgreen-post-qip-special/raw/"
    "6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822.xml"
)
SEPT_ORIGINAL_SHA256 = (
    "6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822"
)
SEPT_ORIGINAL_PUBLIC_UTC = "2026-10-08T13:24:47Z"
SEPT_ORIGINAL_REPORT_DATE = "2026-09-29"
FD_SHARES = 422_070_138
BASIC_SHARES = 419_602_518
INR_CRORE = 10_000_000


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _require_date_timestamp(text: str) -> datetime:
    if not isinstance(text, str):
        raise TypeError("UTC date-time required")
    stamp = datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        raise ValueError("time-aware ISO UTC timestamp required")
    return stamp.astimezone(UTC)


def load_time_bound_sources(root: Path) -> tuple[dict, dict, dict, dict]:
    sources: dict[str, dict] = {}
    receipts: dict[str, dict] = {}
    for name, (relpath, expected_blob) in FROZEN_SOURCES.items():
        raw = (root / relpath).read_bytes()
        found = _git_blob(raw)
        if found != expected_blob:
            raise ValueError(f"{name}: source Git blob drift")
        j = json.loads(raw)
        if not isinstance(j, dict):
            raise TypeError("dated research source is not a JSON object")
        sources[name] = j
        receipts[name] = {
            "path": relpath,
            "source_git_blob": found,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    original = (root / SEPT_ORIGINAL_XBRL).read_bytes()
    if hashlib.sha256(original).hexdigest() != SEPT_ORIGINAL_SHA256:
        raise ValueError("original issuer shareholding XBRL SHA mismatch")
    raw_counts = parse_shareholding_counts(original, symbol="INOXGREEN")
    if raw_counts != {
        "fully_paid_shares": BASIC_SHARES,
        "fully_diluted_shares": FD_SHARES,
    }:
        raise ValueError("original issuer XBRL Sep29 FD and basic counts changed")
    receipts["SEPT_ORIGINAL_NSE_XBRL"] = {
        "path": SEPT_ORIGINAL_XBRL,
        "original_sha256": SEPT_ORIGINAL_SHA256,
        "byte_count": len(original),
    }
    return (
        sources["P008_OCT_CAP"],
        sources["P040_PROMOTER_GOVERNANCE"],
        raw_counts,
        receipts,
    )


def build_publication_safe_fd_reference(
    p008: dict[str, Any],
    p040: dict[str, Any],
    original_counts: dict[str, int],
    *,
    source_receipts: dict[str, dict],
) -> dict[str, Any]:
    if (
        p008.get("audit_id") != "HG007-P008-INOXGREEN-QIP-DATED-CAPITALIZATION-v1"
        or p008.get("post_qip_fully_diluted_market_cap_authorized") is not False
        or p008.get("live_capital_allowed") is not False
        or p008.get("post_qip_basic_share_capital_sensitivities") is None
    ):
        raise ValueError("original P008 QIP correction rule changed")
    if (
        p040.get("review_id")
        != "HG007-P040-INOXGREEN-PROMOTER-NET-HOLDINGS-QIP-DILUTION-v1"
        or p040.get("first_public_sept29_filing_utc") != SEPT_ORIGINAL_PUBLIC_UTC
        or p040.get("official_sept29_pledge_and_shareholding_current_as_of_oct12_verified")
        is not False
        or p040.get("portfolio_eligibility_allowed") is not False
        or p040.get("live_capital_allowed") is not False
    ):
        raise ValueError("P040 original first-public ownership timing changed")
    detail = p040.get("september_special_original")
    if not isinstance(detail, dict):
        raise TypeError("P040 original September source metadata missing")
    if (
        detail.get("report_date") != SEPT_ORIGINAL_REPORT_DATE
        or detail.get("original_xbrl_sha256") != SEPT_ORIGINAL_SHA256
        or detail.get("issuer_fully_diluted_shares") != FD_SHARES
        or detail.get("issuer_issued_basic_shares") != BASIC_SHARES
        or p040.get("promoter_group_pledged_shares_reported_sept29") != 4_900_000
        or p040.get("promoter_group_reported_shares_sept29") != 225_317_291
        or p040.get("net_change_in_reported_promoter_group_shares_between_filings") != 0
        or original_counts.get("fully_paid_shares") != BASIC_SHARES
        or original_counts.get("fully_diluted_shares") != FD_SHARES
    ):
        raise ValueError("XBRL and P040 source-original shareholding reconciliation mismatch")
    basic_refs = p008["post_qip_basic_share_capital_sensitivities"]
    legacy = p008.get("frozen_hg005_oct1_historical_result_not_modified", {})
    hypothetical = p008.get("non_authoritative_same_march_esop_count_scenario", {})
    if (
        hypothetical.get("assumed_qip_plus_march_options_shares") != FD_SHARES
        or p008.get("current_esop_and_option_balance_reverified") is not False
        or legacy.get("march_fd_shares_used") != 403_959_665
    ):
        raise ValueError("P008's earlier hypothetical diluted-count assumption changed")

    published = _require_date_timestamp(SEPT_ORIGINAL_PUBLIC_UTC)
    dates = [
        ("2026-10-01", "2026-10-01T10:00:00Z", "NOT_PUBLIC_AT_MARKET_CLOSE"),
        ("2026-10-09", "2026-10-09T10:00:00Z", "PUBLIC_BEFORE_MARKET_CLOSE"),
    ]
    observed: dict[str, dict] = {}
    for day, close_utc, chronology_state in dates:
        old_ref = basic_refs.get(day)
        if not isinstance(old_ref, dict):
            raise TypeError("dated original NSE basic price reference missing")
        close_price = old_ref.get("raw_nse_close_inr")
        if type(close_price) not in (int, float) or close_price <= 0:
            raise ValueError("original dated NSE price is missing/nonpositive")
        if day == "2026-10-01" and close_price != 159.0:
            raise ValueError("original October 1 price identity changed")
        if day == "2026-10-09" and close_price != 128.92:
            raise ValueError("original October 9 price identity changed")
        actual_chronology = (
            "PUBLIC_BEFORE_MARKET_CLOSE"
            if published <= _require_date_timestamp(close_utc)
            else "NOT_PUBLIC_AT_MARKET_CLOSE"
        )
        if actual_chronology != chronology_state:
            raise ValueError("XBRL source publication chronology failed")
        cap = FD_SHARES * close_price / INR_CRORE
        old_hypothetical = hypothetical.get(
            f"oct{1 if day == '2026-10-01' else 9}_hypothetical_fd_market_cap_inr_crore"
        )
        if not math.isclose(cap, old_hypothetical, rel_tol=1e-12, abs_tol=1e-8):
            raise ValueError("QIP previously hypothetical count/price does not match original source")
        observed[day] = {
            "raw_official_nse_close_inr": close_price,
            "issuer_sep29_fully_diluted_shares": FD_SHARES,
            "dated_market_cap_inr_crore_if_issued_count_unmodified_since_sep29": cap,
            "original_sept_filing_first_public_utc": SEPT_ORIGINAL_PUBLIC_UTC,
            "september_source_publication_at_this_price_close": actual_chronology,
            "could_original_sep29_fd_count_have_been_used_as_knowable_input": (
                chronology_state == "PUBLIC_BEFORE_MARKET_CLOSE"
            ),
            "any_interim_new_securities_or_exercises_checked": False,
            "this_is_a_verified_current_day_fully_diluted_market_cap": False,
            "this_is_an_executable_price_or_forward_return": False,
        }
    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "DATED_SOURCE_FD_PUBLICATION_TIME_RECONCILIATION_NOT_CURRENT_EV",
        "research_prepared_date_ist": "2026-10-13",
        "primary_source_receipts": source_receipts,
        "official_september_29_nse_xbrl_asof_report_date": SEPT_ORIGINAL_REPORT_DATE,
        "official_nse_first_public_timestamp_utc": SEPT_ORIGINAL_PUBLIC_UTC,
        "original_september_29_issued_basic_shares": BASIC_SHARES,
        "original_september_29_reported_fully_diluted_shares": FD_SHARES,
        "september_report_dilutive_difference_vs_basic_shares": FD_SHARES - BASIC_SHARES,
        "exact_instrument_class_breakdown_revalidated_under_this_audit": False,
        "september_report_group_promoter_shares": 225_317_291,
        "september_report_group_pledged_shares": 4_900_000,
        "pledge_origin_effective_date_or_current_balance_verified": False,
        "total_promoter_net_reported_share_change_june_to_sept29": 0,
        "dated_price_and_original_fd_count_reference": observed,
        "p008_original_hypothetical_label_changed_in_source": False,
        "p008_frozen_historical_inputs_modified": False,
        "independently_verified_current_october_13_fully_diluted_count": False,
        "post_qip_current_cash_or_enterprise_value_verified": False,
        "company_specific_expected_return_calculated": False,
        "buy_sell_or_hedge_recommendation_created": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
