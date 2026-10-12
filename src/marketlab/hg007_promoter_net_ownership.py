"""Verify whether INOXGREEN's promoter percentage decline was basic-share dilution.

Use two immutable original NSE shareholding XBRLs, not vendor holdings tables.
This is *net reported shares across two as-of filings*, never proof that
no gross transactions occurred between dates or that today is unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from marketlab.gf001_governance import parse_current_governance_xbrl
from marketlab.hg005_context import parse_shareholding_counts

AUDIT_ID = "HG007-P040-INOXGREEN-PROMOTER-NET-HOLDINGS-QIP-DILUTION-v1"
SOURCE_FILES = {
    "june_original": (
        ("research/hg007/outside-u001-governance-2026-10-04/raw/sha256/"
         "fcb8910121252da982dc38937f3b3fd012c15c51e43ea494a4342f7a4d7e3c47.xml"),
        "fcb8910121252da982dc38937f3b3fd012c15c51e43ea494a4342f7a4d7e3c47",
        "2026-06-30",
        ("https://nsearchives.nseindia.com/corporate/xbrl/"
         "SHP_1706948_03082026041959_WEB.xml"),
    ),
    "september_qip_original": (
        ("research/hg007/inoxgreen-post-qip-special/raw/"
         "6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822.xml"),
        "6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822",
        "2026-09-29",
        ("https://nsearchives.nseindia.com/corporate/xbrl/"
         "SHP_1734551_08102026065442_WEB.xml"),
    ),
}
LEDGER_FILES = {
    "oct4_original_governance": (
        ("research/hg007/outside-u001-governance-2026-10-04/"
         "28-original-governance-v1.json"),
        "e1947ee234e0044c9974dacdf290d75c4021c5cc",
    ),
    "sept29_primary_pledge": (
        "research/hg007/inoxgreen-post-qip-special/original-promoter-pledge-v1.json",
        "8a7d9efc1975b0790726663953ac2dd8ee5e67f0",
    ),
    "first_seen_chronology": (
        "research/hg007/hg007-p039-inoxgreen-governance-first-seen-timeline-v1.json",
        "6fce44950c409e3c77d7625ce6dbc5c5657768c5",
    ),
}
GROUP_CTX = "ShareholdingOfPromoterAndPromoterGroup_ContextI"
TOTAL_CTX = "ShareholdingPattern_ContextI"
GROUP_SHARES = 225_317_291
JUNE_BASIC = 401_492_045
SEPT_BASIC = 419_602_518
QIP_NEW_SHARES = 18_110_473
PLEDGED_SEPT = 4_900_000
JUNE_FD = 403_959_665
SEPT_FD = 422_070_138


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _originals(root: Path) -> tuple[dict[str, dict], dict[str, Any]]:
    filings = {}
    receipts = {}
    for key, (path, expected_sha, report_date, url) in SOURCE_FILES.items():
        original = (root / path).read_bytes()
        sha = hashlib.sha256(original).hexdigest()
        if sha != expected_sha:
            raise ValueError(f"{key}: original NSE XBRL content SHA changed")
        try:
            root_element = ET.fromstring(original)
        except ET.ParseError as exc:
            raise ValueError(f"{key}: original XBRL structurally invalid") from exc
        symbols = {
            (element.text or "").strip().upper()
            for element in root_element.iter()
            if _local(element.tag) == "Symbol" and (element.text or "").strip()
        }
        if symbols != {"INOXGREEN"}:
            raise ValueError(f"{key}: source-listed symbol differs from INOXGREEN")
        for ctx in (GROUP_CTX, TOTAL_CTX):
            contexts = [
                element for element in root_element.iter()
                if _local(element.tag).lower() == "context"
                and element.attrib.get("id") == ctx
            ]
            if len(contexts) != 1:
                raise ValueError(f"{key}: expected one verified context {ctx}")
            dates = [
                (element.text or "").strip()
                for element in contexts[0].iter()
                if _local(element.tag).lower() == "instant"
            ]
            if dates != [report_date]:
                raise ValueError(f"{key}: as-of date/context mismatch")

        def numeric_fact(
            concept: str, context: str, *, required: bool = True,
            bound_root: ET.Element = root_element, source_label: str = key,
        ) -> int | None:
            matched = [
                element for element in bound_root.iter()
                if _local(element.tag) == concept
                and element.attrib.get("contextRef") == context
            ]
            if not matched and not required:
                return None
            if len(matched) != 1:
                raise ValueError(
                    f"{source_label}: expected one {concept} fact for {context}"
                )
            element = matched[0]
            if element.attrib.get("unitRef") != "shares":
                raise ValueError(f"{source_label}: share-count unit not verified")
            try:
                number = int((element.text or "").strip().replace(",", ""))
            except ValueError as exc:
                raise ValueError(f"{source_label}: noninteger XBRL share count") from exc
            if number < 0:
                raise ValueError(f"{source_label}: negative share count")
            return number

        promoter = numeric_fact("NumberOfShares", GROUP_CTX)
        promoter_paid = numeric_fact("NumberOfFullyPaidUpEquityShares", GROUP_CTX)
        total_issued = numeric_fact("NumberOfShares", TOTAL_CTX)
        total_paid = numeric_fact("NumberOfFullyPaidUpEquityShares", TOTAL_CTX)
        group_pledged = numeric_fact(
            "NumberOfSharesEncumberedUnderPledged", GROUP_CTX, required=False
        )
        paid_counts = parse_shareholding_counts(original, symbol="INOXGREEN")
        governance = parse_current_governance_xbrl(
            original, symbol="INOXGREEN", report_date=report_date,
            source_url=url,
        )
        if governance["parser_status"] != "CORE_READY":
            raise ValueError(f"{key}: original governance source is not fully interpretable")
        if (
            promoter != promoter_paid or total_paid != total_issued
            or paid_counts["fully_paid_shares"] != total_issued
        ):
            raise ValueError(f"{key}: original aggregate/group basic share mismatch")
        filings[key] = {
            "report_date": report_date,
            "promoter_group_number_of_shares": promoter,
            "issuer_issued_basic_shares": total_issued,
            "issuer_fully_diluted_shares": paid_counts["fully_diluted_shares"],
            "promoter_percent_original_report": governance["promoter_percentage"],
            "promoter_group_pledge_boolean": governance["promoter_encumbrance"]["pledge"],
            "promoter_group_pledged_shares_when_explicit": group_pledged,
            "original_xbrl_sha256": sha,
            "original_xbrl_url": url,
        }
        receipts[key] = {
            "original_source_path": path,
            "original_xbrl_sha256": sha,
            "raw_byte_count": len(original),
        }
    for key, (path, git_expected) in LEDGER_FILES.items():
        raw = (root / path).read_bytes()
        if _git_blob(raw) != git_expected:
            raise ValueError(f"{key}: immutable source-ledger Git blob drifted")
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise TypeError(f"{key}: source ledger must be an object")
        receipts[key] = {
            "path": path,
            "source_git_blob_sha": git_expected,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        filings[key] = obj
    return filings, receipts


def build_primary_promoter_reconciliation(root: Path) -> dict[str, Any]:
    sources, receipts = _originals(root)
    june = sources["june_original"]
    sept = sources["september_qip_original"]
    original = sources["oct4_original_governance"]
    pledge = sources["sept29_primary_pledge"]
    chronology = sources["first_seen_chronology"]

    if not (
        june["promoter_group_number_of_shares"] == GROUP_SHARES
        and sept["promoter_group_number_of_shares"] == GROUP_SHARES
        and june["issuer_issued_basic_shares"] == JUNE_BASIC
        and sept["issuer_issued_basic_shares"] == SEPT_BASIC
        and sept["issuer_issued_basic_shares"] - june["issuer_issued_basic_shares"]
        == QIP_NEW_SHARES
        and june["issuer_fully_diluted_shares"] == JUNE_FD
        and sept["issuer_fully_diluted_shares"] == SEPT_FD
        and june["promoter_group_pledge_boolean"] is False
        and sept["promoter_group_pledge_boolean"] is True
        and sept["promoter_group_pledged_shares_when_explicit"] == PLEDGED_SEPT
    ):
        raise ValueError("exact issuer original capital/pledge assertions changed")
    old_row = next(
        (item for item in original.get("company_rows", [])
         if item.get("symbol") == "INOXGREEN"), None
    )
    if (
        not isinstance(old_row, dict)
        or old_row.get("latest_source", {}).get("source_xbrl_sha256")
        != june["original_xbrl_sha256"]
        or original.get("original_snapshot_cutoff_utc")
        != "2026-10-04T12:58:38.956448Z"
    ):
        raise ValueError("Oct4 original June source/lookahead timeline changed")
    if (
        pledge.get("original_xbrl_sha256") != sept["original_xbrl_sha256"]
        or pledge.get("promoter_group_total_shares") != GROUP_SHARES
        or pledge.get("promoter_group_total_pledged_shares") != PLEDGED_SEPT
        or pledge.get("original_filing_public_broadcast_utc")
        != "2026-10-08T13:24:47Z"
        or pledge.get("live_capital_allowed") is not False
    ):
        raise ValueError("primary named September pledge document changed")
    earlier = chronology.get("oct4_lookahead_correct_source")
    later = chronology.get("oct8_later_primary_governance_publication")
    if (
        not isinstance(earlier, dict) or not isinstance(later, dict)
        or earlier.get("knows_september29_exceptional_filing") is not False
        or later.get("original_first_public_utc")
        != pledge["original_filing_public_broadcast_utc"]
        or chronology.get("live_capital_allowed") is not False
    ):
        raise ValueError("source availability / initial evidence boundary changed")

    old_exact_fraction = GROUP_SHARES / JUNE_BASIC
    new_exact_fraction = GROUP_SHARES / SEPT_BASIC
    reported_old = june["promoter_percent_original_report"]
    reported_new = sept["promoter_percent_original_report"]
    if not (
        abs(old_exact_fraction * 100 - reported_old) < 0.006
        and abs(new_exact_fraction * 100 - reported_new) < 0.006
    ):
        raise ValueError("issuer published ownership percents do not reconcile to shares")
    return {
        "schema_version": 1,
        "review_id": AUDIT_ID,
        "classification": (
            "EXACT_NET_PROMOTER_GROUP_SHARE_IDENTITY_ACROSS_TWO_PUBLIC_FILINGS_NOT_TRADES"
        ),
        "assembled_on_ist_date": "2026-10-12",
        "original_source_receipts": receipts,
        "original_report_dates": ["2026-06-30", "2026-09-29"],
        "june_original": june,
        "september_special_original": sept,
        "promoter_group_reported_shares_june": GROUP_SHARES,
        "promoter_group_reported_shares_sept29": GROUP_SHARES,
        "net_change_in_reported_promoter_group_shares_between_filings": 0,
        "total_issued_basic_shares_june": JUNE_BASIC,
        "total_issued_basic_shares_sept29": SEPT_BASIC,
        "qip_issued_basic_share_increase": QIP_NEW_SHARES,
        "exact_june_promoter_group_percentage": old_exact_fraction * 100,
        "exact_sept29_promoter_group_percentage": new_exact_fraction * 100,
        "published_june_promoter_pct": reported_old,
        "published_sept29_promoter_pct": reported_new,
        "percentage_point_change_from_fixed_promoter_shares_and_new_issued_base": (
            100 * (new_exact_fraction - old_exact_fraction)
        ),
        "published_percentage_point_change": reported_new - reported_old,
        "published_promoter_percentage_change_explained_by_denominator_within_rounding": True,
        "gross_promoter_sales_and_purchases_during_interval_excluded": False,
        "promoter_group_pledge_boolean_june": False,
        "promoter_group_pledge_boolean_sept29": True,
        "promoter_group_pledged_shares_reported_sept29": PLEDGED_SEPT,
        "new_pledge_creation_date_verified": False,
        "pledge_borrowing_cost_security_and_lender_verified": False,
        "oct4_research_could_use_sept29_filing": False,
        "first_public_sept29_filing_utc": "2026-10-08T13:24:47Z",
        "official_sept29_pledge_and_shareholding_current_as_of_oct12_verified": False,
        "company_current_fd_and_net_debt_verified": False,
        "stock_expected_returns_calculated": False,
        "case_completion_probability_published": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
