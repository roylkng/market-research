"""As-of disclosure timeline: October 4 GF001 vs October 8 INOXGREEN QIP filing.

An NSE report's as-of date is NOT its first public timestamp. This prevents
retroactive attribution of September 29 pledge facts to October 1/4, and
does not interpret promoter percentage dilution as a proved promoter sale.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ORIGINALS = {
    "GF001_28_AS_OF_OCT04": (
        "research/hg007/outside-u001-governance-2026-10-04/28-original-governance-v1.json",
        "e1947ee234e0044c9974dacdf290d75c4021c5cc",
    ),
    "HG007_P013_POST_QIP_CASES": (
        "research/hg007/hg007-p013-28-case-sept29-fd-pledge-overlay-v1.json",
        "c5b542e56ec79c0a47afb4359e57c1638d3c0086",
    ),
    "HG007_P012_NAMED_PROMOTER_PLEDGE": (
        "research/hg007/inoxgreen-post-qip-special/original-promoter-pledge-v1.json",
        "8a7d9efc1975b0790726663953ac2dd8ee5e67f0",
    ),
    "HG007_P011_NSE_SPECIAL_RECEIPT": (
        "research/hg007/inoxgreen-post-qip-special/original-receipt-v1.json",
        "8990da5ab2d56c07b2f05942210861fab2eb17ba",
    ),
}
REPORT_ID = "HG007-P039-2026-10-04-TO-10-08-INOXGREEN-SOURCE-CHRONOLOGY-v1"
EXPECTED_PUBLIC_TIME = "2026-10-08T13:24:47Z"
SOURCE_ASOF_DATE = "2026-09-29"
OLD_CAPTURE_MAX = "2026-10-06T00:00:00Z"
NEXT_KNOWN_MARKET_OPEN = "2026-10-09T03:45:00Z"


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _timestamp(raw: object) -> datetime:
    if not isinstance(raw, str):
        raise TypeError("official public-source timestamp must be string")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError("official source timestamp must include timezone")
    return parsed.astimezone(UTC)


def load_original_source_states(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    inputs = {}
    provenance = {}
    for label, (path, expected_sha) in ORIGINALS.items():
        raw = (root / path).read_bytes()
        if _git_blob(raw) != expected_sha:
            raise ValueError(f"{label}: source Git blob changed")
        j = json.loads(raw)
        if not isinstance(j, dict) or j.get("live_capital_allowed") is not False:
            raise ValueError(f"{label}: source cannot authorize investments")
        inputs[label] = j
        provenance[label] = {
            "path": path,
            "original_git_blob_sha": expected_sha,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return inputs, provenance


def reconcile_gov_publication_timeline(
    sources: dict[str, dict],
    provenance: dict[str, dict],
) -> dict[str, Any]:
    if set(sources) != set(ORIGINALS) or set(provenance) != set(ORIGINALS):
        raise ValueError("exact four original governance sources required")
    old = sources["GF001_28_AS_OF_OCT04"]
    newer = sources["HG007_P013_POST_QIP_CASES"]
    pledge = sources["HG007_P012_NAMED_PROMOTER_PLEDGE"]
    master = sources["HG007_P011_NSE_SPECIAL_RECEIPT"]
    first = _timestamp(old.get("original_snapshot_cutoff_utc"))
    announced = _timestamp(newer.get("original_nse_xbrl_public_at_utc"))
    if not (
        first < _timestamp(OLD_CAPTURE_MAX) < announced
        < _timestamp(NEXT_KNOWN_MARKET_OPEN)
    ):
        raise ValueError("original public-information timeline reversed/violated")
    rows = old.get("company_rows")
    newer_rows = newer.get("company_cases")
    if (
        old.get("audit_id") != "HG007-P038-28-COMPANY-OCT04-GOVERNANCE-SOURCE-v1"
        or not isinstance(rows, list) or len(rows) != 28
        or old.get("original_oct04_core_ready_count") != 28
        or old.get("original_oct04_pledge_boolean_true_symbols") != []
        or newer.get("audit_id") != "HG007-P013-SEPT29-FD-PLEDGE-PUBLICATION-OVERLAY-v1"
        or not isinstance(newer_rows, list) or len(newer_rows) != 28
        or newer.get("original_nse_xbrl_asof_date") != SOURCE_ASOF_DATE
        or newer.get("original_nse_xbrl_public_at_utc") != EXPECTED_PUBLIC_TIME
        or newer.get("verified_current_oct11_fully_diluted_share_counts") != 0
        or newer.get("revised_case_count") != 1
    ):
        raise ValueError("28 original source company memberships or cutoff changed")
    names = {row["symbol"] for row in rows}
    new_names = {row["symbol"] for row in newer_rows}
    if len(names) != 28 or names != new_names or "INOXGREEN" not in names:
        raise ValueError("original 28-stock economic shortlist changed")
    june = next(row for row in rows if row["symbol"] == "INOXGREEN")
    latest = june.get("latest_source")
    if (
        not isinstance(latest, dict)
        or latest.get("report_date") != "2026-06-30"
        or latest.get("promoter_encumbrance_boolean", {}).get("pledge") is not False
        or latest.get("source_xbrl_sha256")
        != "fcb8910121252da982dc38937f3b3fd012c15c51e43ea494a4342f7a4d7e3c47"
        or not math.isclose(latest.get("promoter_group_pct"), 56.12, abs_tol=1e-8)
        or not math.isclose(latest.get("public_pct"), 43.88, abs_tol=1e-8)
    ):
        raise ValueError("original 30 June issuer governance state changed")
    special = next(row for row in newer_rows if row["symbol"] == "INOXGREEN")
    dated = special.get("asof_29sep_exchange_source_update")
    if not isinstance(dated, dict) or dated.get("status") != (
        "ORIGINAL_NSE_QIP_SPECIAL_XBRL_CONFIRMED_AS_OF_SEP29"
    ):
        raise ValueError("original September 29 special allotment-source status changed")
    own = master.get("original_master")
    facts = master.get("parsed_special_facts")
    if (
        master.get("status") != "ORIGINAL_QIP_SPECIAL_XBRL_SHARE_COUNTS_PARSED"
        or not isinstance(own, dict)
        or not isinstance(facts, dict)
        or own.get("special_not_standard_september_quarter") is not True
        or own.get("exchange_first_public_broadcast_at_utc") != EXPECTED_PUBLIC_TIME
        or own.get("as_of_allotment_date") != SOURCE_ASOF_DATE
        or master.get("original_xbrl_sha256")
        != "6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822"
        or own.get("issuer_master_promoter_percentage") != 53.7
        or own.get("issuer_master_public_percentage") != 46.3
        or facts.get("promoter_pledge_boolean_as_of_report") is not True
    ):
        raise ValueError("special September 29 NSE XBRL or publication metadata changed")
    if (
        pledge.get("audit_id") != "HG007-P012-INOXGREEN-EXACT-SEPT29-PLEDGE-AND-FD-v1"
        or pledge.get("original_filing_public_broadcast_utc") != EXPECTED_PUBLIC_TIME
        or pledge.get("issuer_asof_date") != SOURCE_ASOF_DATE
        or pledge.get("reference_june_original_pledge_boolean") is not False
        or pledge.get("sept29_original_pledge_boolean") is not True
        or pledge.get("named_promoter_pledged_shares") != 4_900_000
        or pledge.get("promoter_group_total_pledged_shares") != 4_900_000
        or pledge.get("promoter_group_total_shares") != 225_317_291
        or pledge.get("listed_company_total_basic_shares") != 419_602_518
        or pledge.get("exact_date_pledge_created_verified") is not False
        or pledge.get("no_post_sep29_pledge_changes_verified") is not False
    ):
        raise ValueError("original named promoter pledged-share source changed")
    if dated.get("pledged_shares_at_sep29") != pledge["named_promoter_pledged_shares"]:
        raise ValueError("HG007 pledge quantity source conflict")

    original_promoter_pct = latest["promoter_group_pct"]
    later_promoter_pct = own["issuer_master_promoter_percentage"]
    basic_prior = 401_492_045
    basic_after = pledge["listed_company_total_basic_shares"]
    prior_promoter_implied = basic_prior * original_promoter_pct / 100
    alternate_promoter_pct_if_same_shares = 100 * prior_promoter_implied / basic_after
    if not math.isclose(
        alternate_promoter_pct_if_same_shares, later_promoter_pct, abs_tol=0.02
    ):
        raise ValueError("capital dilution alone no longer reconciles rounded percentages")
    # We do NOT have proof that promoters' exact share count stayed constant
    # across the two reports. Percentages rounded; this is a possible
    # accounting explanation, never a claim that no promoter traded.
    return {
        "schema_version": 1,
        "event_review_id": REPORT_ID,
        "classification": "ASOF_GOVERNANCE_RECONCILIATION_NO_UNVERIFIED_PROMOTER_SALE_INFERENCE",
        "source_provenance": provenance,
        "original_outside_u001_28_count": 28,
        "original_case_selection_modified": False,
        "historical_oct4_source_pledge_boolean_true_count": 0,
        "oct4_lookahead_correct_source": {
            "source_observation_utc": first.isoformat().replace("+00:00", "Z"),
            "report_date": latest["report_date"],
            "original_nse_broadcast_utc": latest["source_broadcast_utc"],
            "INOXGREEN_promoter_group_pct": original_promoter_pct,
            "INOXGREEN_public_pct": latest["public_pct"],
            "INOXGREEN_pledge_boolean": False,
            "knows_september29_exceptional_filing": False,
        },
        "oct8_later_primary_governance_publication": {
            "original_first_public_utc": EXPECTED_PUBLIC_TIME,
            "issuer_capital_asof_date": SOURCE_ASOF_DATE,
            "regular_2026_sep30_quarter_filing": False,
            "INOXGREEN_promoter_group_pct": later_promoter_pct,
            "INOXGREEN_public_pct": own["issuer_master_public_percentage"],
            "INOXGREEN_promoter_named_pledged_shares": 4_900_000,
            "INOXGREEN_promoter_pledge_boolean": True,
            "pledge_security_lender_loan_date_verified": False,
            "current_oct11_pledge_status_verified": False,
        },
        "conditional_promoter_fraction_reconciliation": {
            "june_old_basic_shares": basic_prior,
            "sept29_qip_issued_basic_shares": basic_after,
            "june_reported_promoter_pct": original_promoter_pct,
            "sept29_reported_promoter_pct": later_promoter_pct,
            "percentage_point_difference": later_promoter_pct - original_promoter_pct,
            "hypothetical_pct_if_same_june_promoter_share_count_after_qip": alternate_promoter_pct_if_same_shares,
            "consistent_with_issue_denominator_dilution_within_reported_pct_rounding": True,
            "promoter_sold_or_bought_shares_proven": False,
            "exact_june_promoter_share_count_source_verified_here": False,
        },
        "other_27_current_ownership_and_pledge_reviewed": False,
        "new_research_observations_are_portfolio_signals": False,
        "share_target_price_or_expected_return_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
