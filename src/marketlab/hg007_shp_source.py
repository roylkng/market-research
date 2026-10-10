"""Source-only NSE ownership audit for INOXGREEN, deliberately outside H023 U001.

Separates quarter-end Reg31 ownership filings from special post-QIP capital
events. A June 2026 XBRL is not evidence of October option/pledge state;
secondary market-data tables never become original exchange source facts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from marketlab.gf001_governance import parse_current_governance_xbrl
from marketlab.h023_acquisition import (
    H023AcquisitionError,
    discover_standard_quarter_sources,
)
from marketlab.hg005_context import parse_shareholding_counts

AUDIT_ID = "HG007-P010-INOXGREEN-POST-QIP-ORIGINAL-SHAREHOLDING-v1"
MASTER_URL = (
    "https://www.nseindia.com/api/"
    "corporate-share-holdings-master?index=equities&symbol=INOXGREEN"
)
SYMBOL = "INOXGREEN"
ISIN = "INE510W01014"
PREVIOUS_OFFICIAL_QUARTER = "2026-06-30"
POST_QIP_QUARTER = "2026-09-30"
QIP_DATE = "2026-09-29"
KNOWN_POST_QIP_BASIC = 419_602_518


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("NSE source timestamp must be a timezone-aware ISO string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("NSE source timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("source timestamp must have timezone")
    return parsed.astimezone(UTC)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def select_latest_official_filing(
    master_raw: bytes,
    *,
    captured_at_utc: str,
) -> dict[str, Any]:
    """Review an exact original NSE source master without retroactive visibility."""
    if not isinstance(master_raw, bytes) or not master_raw or len(master_raw) > 4_000_000:
        raise ValueError("original NSE master source bytes missing/too large")
    capture = _utc(captured_at_utc)
    try:
        original = json.loads(master_raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("original NSE shareholding master is not valid JSON") from exc
    if not isinstance(original, list) or any(not isinstance(row, dict) for row in original):
        raise TypeError("NSE shareholding master must be original list of object rows")
    try:
        sources = discover_standard_quarter_sources(original, symbol=SYMBOL)
    except H023AcquisitionError as exc:
        raise ValueError("NSE standard-quarter source identity ambiguous/invalid") from exc
    nonstandard: list[dict[str, Any]] = []
    for row in original:
        value = str(row.get("date") or "").strip()
        if "SEP-2026" in value.upper() and not any(
            value.upper() == datetime.fromisoformat(s["report_date"]).strftime("%d-%b-%Y").upper()
            for s in sources
        ):
            # Discovery context only. No non-standard capital event can be
            # substituted for a published and checked Reg31 XBRL.
            nonstandard.append({
                "date_text": value,
                "record_id": str(row.get("recordId") or ""),
                "broadcast_text": str(row.get("broadcastDate") or ""),
                "original_master_row_sha256": _sha(
                    json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)
                    .encode("utf-8")
                ),
                "qip_special_event_not_standard_reg31": True,
            })
    eligible = [
        source for source in sources
        if _utc(source["broadcast_at_utc"]) <= capture
        and source["report_date"] <= capture.date().isoformat()
    ]
    newest: dict[str, Any] | None = None
    if eligible:
        latest_date = max(source["report_date"] for source in eligible)
        same_day = [source for source in eligible if source["report_date"] == latest_date]
        max_broadcast = max(source["broadcast_at_utc"] for source in same_day)
        top = [s for s in same_day if s["broadcast_at_utc"] == max_broadcast]
        if len(top) != 1:
            raise ValueError("NSE same-day competing latest filing broadcast")
        newest = top[0]
    published_sep = [
        source for source in eligible if source["report_date"] == POST_QIP_QUARTER
    ]
    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "ORIGINAL_EXCHANGE_SOURCE_DISCOVERY_NOT_INVESTMENT_SIGNAL",
        "issuer": SYMBOL,
        "isin": ISIN,
        "captured_at_utc": capture.isoformat().replace("+00:00", "Z"),
        "master_url": MASTER_URL,
        "original_master_sha256": _sha(master_raw),
        "original_master_byte_count": len(master_raw),
        "master_row_count": len(original),
        "standard_quarter_candidate_count": len(sources),
        "visible_by_capture_quarter_count": len(eligible),
        "special_nonstandard_september_event_rows": nonstandard,
        "original_latest_visible_standard_quarter": newest,
        "sept30_quarter_filing_visible_at_capture": bool(published_sep),
        "asof_sep30_esop_balance_source_verified": False,
        "asof_sep30_promoter_pledge_source_verified": False,
        "full_oct11_current_fd_certified": False,
        "legacy_h023_source_ledger_reused": False,
        "return_outcomes_opened": False,
        "company_target_price_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def review_original_xbrl(
    master: dict[str, Any],
    raw_xml: bytes,
    *,
    retrieved_at_utc: str,
) -> dict[str, Any]:
    """Parse one published official Reg31 XBRL; preserve exact as-of date."""
    if master.get("audit_id") != AUDIT_ID:
        raise ValueError("unrecognized source discovery")
    source = master.get("original_latest_visible_standard_quarter")
    if not isinstance(source, dict):
        raise TypeError("no official standard-quarter XBRL identified")
    if not isinstance(raw_xml, bytes) or not raw_xml or len(raw_xml) > 5_000_000:
        raise ValueError("original XBRL bytes missing or outside bounded source limit")
    retrieved = _utc(retrieved_at_utc)
    if retrieved < _utc(master.get("captured_at_utc")):
        raise ValueError("XBRL retrieved before the original source master")
    report_date = source["report_date"]
    stock = parse_shareholding_counts(raw_xml, symbol=SYMBOL)
    gov = parse_current_governance_xbrl(
        raw_xml,
        symbol=SYMBOL,
        report_date=report_date,
        source_url=source["xbrl_url"],
    )
    paid, diluted = stock["fully_paid_shares"], stock["fully_diluted_shares"]
    if paid <= 0 or diluted < paid:
        raise ValueError("official Reg31 share counts inconsistent")
    is_sep = report_date == POST_QIP_QUARTER
    # A mismatch with the original Sep29 QIP is a source conflict, not
    # permission to overwrite the frozen Sep29 issuer allotment.
    conflict = is_sep and paid != KNOWN_POST_QIP_BASIC
    governance_ready = gov.get("parser_status") == "CORE_READY"
    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "ORIGINAL_REPORTED_QUARTER_END_FACTS_NOT_LATER_DATE_CONFIRMED_FD",
        "symbol": SYMBOL,
        "isin": ISIN,
        "report_date": report_date,
        "master_sha256": master["original_master_sha256"],
        "master_xbrl_url": source["xbrl_url"],
        "master_source_record_id": source["record_id"],
        "master_source_broadcast_at_utc": source["broadcast_at_utc"],
        "xbrl_retrieved_at_utc": retrieved.isoformat().replace("+00:00", "Z"),
        "original_xbrl_sha256": _sha(raw_xml),
        "original_xbrl_byte_count": len(raw_xml),
        "fully_paid_issued_shares_in_filing": paid,
        "reported_fully_diluted_shares_in_filing": diluted,
        "outstanding_options_convertibles_delta_to_basic": diluted-paid,
        "sept29_qip_original_issued_count": KNOWN_POST_QIP_BASIC,
        "sept30_basic_consistent_with_qip": bool(is_sep and not conflict),
        "issuer_basic_qip_xbrl_conflict": conflict,
        "promoter_percentage_as_of_report": (
            gov["promoter_percentage"] if governance_ready else None
        ),
        "promoter_pledge_declared_as_of_report": (
            gov["promoter_encumbrance"]["pledge"] if governance_ready else None
        ),
        "governance_parser_status": gov["parser_status"],
        "governance_failure_reason": gov.get("core_failure_reason"),
        "sept30_options_balance_independently_sourced": bool(is_sep and not conflict),
        "sept30_promoter_pledge_independently_sourced": bool(
            is_sep and not conflict and governance_ready
        ),
        "claimed_sept29_to_oct11_share_changes_ruled_out": False,
        "actual_pledged_share_quantity_verified": False,
        "current_oct11_fully_diluted_shares_verified": False,
        "old_march_fd_figure_permitted_as_oct_cap": False,
        "stock_expected_returns_calculated": False,
        "company_target_price_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
