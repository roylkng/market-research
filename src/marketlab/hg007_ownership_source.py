"""Reconcile issuer-specific NSE ownership filing source without lookahead.

NSE's standard-quarter-only H023 filter can miss a *special* allotment-
dated Regulation 31 report. HG007 looks at all actual dated original NSE
master records, then binds the latest as-of source to its original XBRL.

This is a source-integrity diagnostic, NOT a current FD share claim,
governance score, investment ranking, or capital authorization.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from marketlab.gf001_governance import parse_current_governance_xbrl
from marketlab.h023_ownership import BROADCAST_FORMAT, REPORT_DATE_FORMAT
from marketlab.hg005_context import parse_shareholding_counts

AUDIT_ID = "HG007-P010-INOXGREEN-OFFICIAL-POST-QIP-OWNERSHIP-SOURCE-v1"
SYMBOL = "INOXGREEN"
ISIN = "INE510W01014"
ISSUED_QIP_SHARES = 419_602_518
POST_QIP_DATE = date(2026, 9, 29)
IST = ZoneInfo("Asia/Kolkata")
NSE_MASTER_URL = (
    "https://www.nseindia.com/api/corporate-share-holdings-master"
    "?index=equities&symbol=INOXGREEN"
)
READY_STATES = frozenset({
    "POST_QIP_XBRL_SHARE_COUNT_AND_GOVERNANCE_RECONCILED",
    "POST_QIP_XBRL_SHARE_COUNT_RECONCILED_GOVERNANCE_INCOMPLETE",
    "POST_QIP_XBRL_SHARE_COUNT_DISAGREES_WITH_QIP",
    "POST_QIP_XBRL_UNPARSEABLE",
    "PRE_QIP_ONLY_OFFICIAL_SHAREHOLDING_SOURCE",
})


def _instant(text: object) -> datetime:
    if not isinstance(text, str):
        raise TypeError("source retrieval timestamp must be ISO UTC with timezone")
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if result.tzinfo is None:
        raise ValueError("naive source timestamp prohibited")
    return result.astimezone(UTC)


def _archive_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"nsearchives.nseindia.com", "archives.nseindia.com"}
        and parsed.port in (None, 443)
        and parsed.username is None
        and parsed.password is None
        and parsed.path.startswith("/corporate/")
        and not parsed.fragment
        and not parsed.query
    )


def _nse_master_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    q = parse_qs(parsed.query, keep_blank_values=True)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "www.nseindia.com"
        and parsed.path == "/api/corporate-share-holdings-master"
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
        and parsed.port in (None, 443)
        and q == {"index": ["equities"], "symbol": ["INOXGREEN"]}
    )


def _validated_master_rows(raw: bytes, *, captured_at_utc: str) -> list[dict[str, Any]]:
    captured = _instant(captured_at_utc)
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise ValueError("original NSE shareholding master JSON invalid") from exc
    # The endpoint may return a root list or an explicit data/records array
    # envelope. Never mistake an error/status object for a clean empty list.
    if isinstance(payload, dict):
        if (
            any(key in payload for key in ("error", "errors", "exception"))
            or payload.get("status") in (False, "error", "failed", "failure")
        ):
            raise ValueError("NSE corporate master returned a structured error")
        if isinstance(payload.get("data"), list):
            payload = payload["data"]
        elif isinstance(payload.get("records"), list):
            payload = payload["records"]
        else:
            raise TypeError("original NSE master object lacks data/records list")
    if not isinstance(payload, list):
        raise TypeError("original NSE master must contain an explicit dated list")
    records = []
    for row in payload:
        if not isinstance(row, dict):
            raise TypeError("NSE master has non-object source record")
        reported = str(row.get("symbol") or "").upper().strip()
        if reported not in ("", SYMBOL):
            raise ValueError("original NSE master contains foreign issuer")
        report_raw = row.get("date")
        broadcast_raw = row.get("broadcastDate")
        if not isinstance(report_raw, str) or not isinstance(broadcast_raw, str):
            raise TypeError("NSE master report-date/broadcastDate missing")
        try:
            day = datetime.strptime(report_raw.upper(), REPORT_DATE_FORMAT).date()
            broadcast = (
                datetime.strptime(broadcast_raw.upper(), BROADCAST_FORMAT)
                .replace(tzinfo=IST).astimezone(UTC)
            )
        except ValueError as exc:
            raise ValueError("NSE original master has invalid dated source") from exc
        if broadcast > captured or day > captured.astimezone(IST).date():
            raise ValueError("NSE original master source comes from the future")
        url = row.get("xbrl")
        if not _archive_url(url):
            raise ValueError("original NSE shareholding record has unapproved XBRL")
        record_id = str(row.get("recordId") or "").strip()
        if not record_id:
            raise ValueError("original NSE master source lacks record ID")
        records.append({
            "record_id": record_id,
            "symbol": SYMBOL,
            "report_date": day.isoformat(),
            "broadcast_at_utc": broadcast.isoformat().replace("+00:00", "Z"),
            "xbrl_url": url,
            "master_row_sha256": hashlib.sha256(
                json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)
                .encode("utf-8")
            ).hexdigest(),
            "quarter_end": day.month in (3, 6, 9, 12)
            and day.day == {3: 31, 6: 30, 9: 30, 12: 31}[day.month],
            "allotment_date_or_nonstandard_report": (day.month, day.day)
            not in {(3, 31), (6, 30), (9, 30), (12, 31)},
        })
    if not records:
        raise ValueError("NSE shareholding master contains no issuer source records")
    ids = [x["record_id"] for x in records]
    if len(ids) != len(set(ids)):
        raise ValueError("reused NSE master record ID; cannot choose source")
    return records


def select_latest_dated_master_source(
    raw: bytes, *, captured_at_utc: str
) -> dict[str, Any]:
    """Latest disclosed report as of capture, including special allotment dates."""
    records = _validated_master_rows(raw, captured_at_utc=captured_at_utc)
    latest_report = max(x["report_date"] for x in records)
    same_date = [x for x in records if x["report_date"] == latest_report]
    latest_broadcast = max(x["broadcast_at_utc"] for x in same_date)
    latest_rows = [x for x in same_date if x["broadcast_at_utc"] == latest_broadcast]
    if len(latest_rows) != 1:
        raise ValueError("ambiguous latest NSE revision broadcast; no source guess")
    selected = latest_rows[0]
    return {
        "selected_source": selected,
        "original_master_sha256": hashlib.sha256(raw).hexdigest(),
        "master_record_count": len(records),
        "distinct_report_dates": sorted({x["report_date"] for x in records}),
        "original_capture_utc": _instant(captured_at_utc).isoformat().replace("+00:00", "Z"),
        "source_is_post_qip_as_of_report_date": (
            date.fromisoformat(selected["report_date"]) >= POST_QIP_DATE
        ),
        "source_is_a_special_allotment_date_not_standard_quarter": (
            selected["allotment_date_or_nonstandard_report"]
        ),
    }


def evaluate_source_xbrl(
    selected: dict[str, Any],
    raw_xbrl: bytes,
    *,
    xbrl_captured_at_utc: str,
) -> dict[str, Any]:
    if not isinstance(selected, dict):
        raise TypeError("selected NSE master record missing")
    info = selected.get("selected_source")
    if not isinstance(info, dict) or not _archive_url(info.get("xbrl_url")):
        raise ValueError("unapproved source XBRL URL")
    capture = _instant(xbrl_captured_at_utc)
    if capture < _instant(selected.get("original_capture_utc")):
        raise ValueError("NSE XML capture predates master source selection")
    digest = hashlib.sha256(raw_xbrl).hexdigest()
    report_date = info["report_date"]
    record: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "OFFICIAL_SOURCE_ASOF_REPORT_DATE_NOT_CURRENT_INVESTMENT_CLEARANCE",
        "symbol": SYMBOL,
        "isin": ISIN,
        "original_master": selected,
        "original_xbrl_url": info["xbrl_url"],
        "original_xbrl_sha256": digest,
        "xbrl_capture_utc": capture.isoformat().replace("+00:00", "Z"),
        "source_report_date": report_date,
        "post_qip_allotment_count_reference": ISSUED_QIP_SHARES,
        "source_report_is_post_qip": selected["source_is_post_qip_as_of_report_date"],
        "original_reported_issued_basic_shares": None,
        "original_reported_fully_diluted_shares": None,
        "original_reported_option_and_other_instruments_difference": None,
        "official_reported_promoter_percentage": None,
        "official_reported_promoter_pledge_boolean": None,
        "official_reported_promoter_non_disposal_boolean": None,
        "official_reported_other_promoter_encumbrance_boolean": None,
        "official_reported_raw_pledged_share_count": None,
        "issuer_original_share_count_reconciled": False,
        "independent_reg31_row_semantic_review_complete": False,
        "source_status": None,
        "source_parse_error": None,
        "current_fully_diluted_market_cap_verified": False,
        "subsequent_issue_and_share_action_audit_complete": False,
        "current_promoter_pledge_quantity_verified": False,
        "independent_governance_investment_review_complete": False,
        "company_completion_probability_calculated": False,
        "expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    try:
        issued = parse_shareholding_counts(raw_xbrl, symbol=SYMBOL)
    except (ValueError, TypeError, ET.ParseError) as exc:
        record["source_status"] = "POST_QIP_XBRL_UNPARSEABLE"
        record["source_parse_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        return record
    basic = issued["fully_paid_shares"]
    diluted = issued["fully_diluted_shares"]
    record.update(
        original_reported_issued_basic_shares=basic,
        original_reported_fully_diluted_shares=diluted,
        original_reported_option_and_other_instruments_difference=diluted - basic,
    )
    if not selected["source_is_post_qip_as_of_report_date"]:
        record["source_status"] = "PRE_QIP_ONLY_OFFICIAL_SHAREHOLDING_SOURCE"
        return record
    if basic != ISSUED_QIP_SHARES:
        record["source_status"] = "POST_QIP_XBRL_SHARE_COUNT_DISAGREES_WITH_QIP"
        return record
    # Binding the master date to the XML aggregate context prevents a
    # newer filename being passed off as an old XBRL shareholding state.
    try:
        root = ET.fromstring(raw_xbrl)
    except ET.ParseError as exc:
        raise ValueError("original NSE shareholding XML structure invalid") from exc
    aggregates = [
        item for item in root.iter()
        if item.tag.rsplit("}", 1)[-1] == "context"
        and item.attrib.get("id") == "ShareholdingPattern_ContextI"
    ]
    if len(aggregates) != 1:
        raise ValueError("XBRL lacks unique aggregate shareholding period")
    dates = [
        (child.text or "").strip() for child in aggregates[0].iter()
        if child.tag.rsplit("}", 1)[-1] == "instant"
    ]
    if dates != [report_date]:
        raise ValueError("XBRL aggregate as-of date disagrees with original NSE master")
    record["issuer_original_share_count_reconciled"] = True
    governance = parse_current_governance_xbrl(
        raw_xbrl, symbol=SYMBOL, report_date=report_date, source_url=info["xbrl_url"]
    )
    if governance.get("parser_status") == "CORE_READY":
        pledge = governance["promoter_encumbrance"]
        record.update(
            official_reported_promoter_percentage=governance["promoter_percentage"],
            official_reported_promoter_pledge_boolean=pledge["pledge"],
            official_reported_promoter_non_disposal_boolean=pledge["non_disposal_undertaking"],
            official_reported_other_promoter_encumbrance_boolean=pledge["other_encumbrance"],
            source_status="POST_QIP_XBRL_SHARE_COUNT_AND_GOVERNANCE_RECONCILED",
        )
    else:
        record.update(
            source_status="POST_QIP_XBRL_SHARE_COUNT_RECONCILED_GOVERNANCE_INCOMPLETE",
            source_parse_error=governance.get("core_failure_reason"),
        )
    return record


def validated_receipt(payload: dict[str, Any]) -> None:
    if payload.get("audit_id") != AUDIT_ID or payload.get("source_status") not in READY_STATES:
        raise ValueError("unknown source report or ownership state")
    for key in (
        "current_fully_diluted_market_cap_verified",
        "subsequent_issue_and_share_action_audit_complete",
        "current_promoter_pledge_quantity_verified",
        "independent_governance_investment_review_complete",
        "company_completion_probability_calculated",
        "expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if payload.get(key) is not False:
            raise ValueError(f"unreviewed ownership data cannot authorize {key}")
