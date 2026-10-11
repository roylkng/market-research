"""Exact NSE post-QIP INOXGREEN Reg31 shareholding evidence, never a buy signal.

The 29-Sep-2026 QIP changed basic issued shares to 419,602,518. Only a
source-broadcast-after-allotment Reg31 XML may resolve subsequent diluted
equity; a third-party September percentage table cannot do so. A missing
official master/XML is an explicit blocker, not March options carried forward.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from marketlab.gf001_governance import GF001GovernanceError, parse_current_governance_xbrl
from marketlab.hg005_context import parse_shareholding_counts

REPORT_ID = "HG007-P010-INOXGREEN-OFFICIAL-POST-QIP-SHAREHOLDING-v1"
SYMBOL = "INOXGREEN"
ISIN = "INE510W01014"
MASTER_URL = "https://www.nseindia.com/api/corporate-share-holdings-master"
ALLOWED_XML_HOSTS = frozenset({"nsearchives.nseindia.com", "archives.nseindia.com"})
QIP_ALLOTMENT_DATE = date(2026, 9, 29)
QIP_BASIC_ISSUED_SHARES = 419_602_518
MARCH_FD_SHARES = 403_959_665
IST = ZoneInfo("Asia/Kolkata")
MAX_MASTER_BYTES = 5_000_000
MAX_XBRL_BYTES = 10_000_000


def utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be ISO offset-aware")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("timestamp is not valid ISO") from exc
    if stamp.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return stamp.astimezone(UTC)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _official_xbrl_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parts = urlsplit(value)
        return (
            parts.scheme == "https"
            and parts.hostname in ALLOWED_XML_HOSTS
            and parts.username is None
            and parts.password is None
            and parts.port in (None, 443)
            and parts.path.lower().endswith((".xml", ".html", ".xhtml"))
            and not parts.fragment
        )
    except ValueError:
        return False


def _filing_date(value: object) -> date:
    if not isinstance(value, str):
        raise TypeError("filing date missing")
    try:
        return datetime.strptime(value.strip().upper(), "%d-%b-%Y").date()
    except ValueError as exc:
        raise ValueError("filing date is not official dd-Mon-yyyy") from exc


def _broadcast(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("filing broadcast timestamp missing")
    try:
        return datetime.strptime(
            value.strip().upper(), "%d-%b-%Y %H:%M:%S"
        ).replace(tzinfo=IST).astimezone(UTC)
    except ValueError as exc:
        raise ValueError("filing broadcast timestamp invalid") from exc


def choose_post_qip_filing(
    raw_master: bytes, *, observed_at_utc: str
) -> dict[str, Any] | None:
    """Choose only *already published* post-allotment original Reg31 records."""
    now = utc(observed_at_utc)
    if not isinstance(raw_master, bytes) or not 2 <= len(raw_master) <= MAX_MASTER_BYTES:
        raise ValueError("original NSE master response missing or over-size")
    try:
        rows = json.loads(raw_master)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("official NSE master JSON cannot be parsed") from exc
    if not isinstance(rows, list):
        raise TypeError("official NSE master response must be a list")

    candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            raise TypeError("NSE master list contains non-object item")
        record_symbol = item.get("symbol")
        if str(record_symbol or "").upper() not in ("", SYMBOL):
            continue
        if not item.get("date"):
            continue
        day = _filing_date(item["date"])
        if day < QIP_ALLOTMENT_DATE or day > now.astimezone(IST).date():
            continue
        record_id = str(item.get("recordId") or "").strip()
        link = item.get("xbrl")
        if not record_id or not _official_xbrl_url(link):
            raise ValueError("post-QIP NSE recordId or exact XBRL URL invalid")
        if record_id in seen_ids:
            raise ValueError("post-QIP NSE recordId duplicated")
        seen_ids.add(record_id)
        published = _broadcast(item.get("broadcastDate"))
        if published > now:
            continue  # later publication may not be used retrospectively
        if published < datetime(2026, 9, 29, tzinfo=UTC):
            raise ValueError("post-QIP shareholding report predates allotment")
        candidates.append({
            "symbol": SYMBOL,
            "record_id": record_id,
            "report_date": day.isoformat(),
            "broadcast_at_utc": published.isoformat().replace("+00:00", "Z"),
            "xbrl_url": link,
            "original_master_row_sha256": _hash(
                json.dumps(
                    item, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
            ),
        })

    if not candidates:
        return None
    candidates.sort(key=lambda x: (
        x["report_date"], x["broadcast_at_utc"], x["record_id"]
    ))
    latest_date = candidates[-1]["report_date"]
    latest_broadcast = max(
        item["broadcast_at_utc"] for item in candidates if item["report_date"] == latest_date
    )
    latest = [
        item for item in candidates
        if item["report_date"] == latest_date and item["broadcast_at_utc"] == latest_broadcast
    ]
    if len(latest) != 1:
        raise ValueError("same-date latest original NSE filing revision ambiguous")
    return latest[0]


def build_post_qip_shareholding_evidence(
    *,
    master_raw: bytes | None,
    xbrl_raw: bytes | None,
    master_status: str,
    xbrl_status: str,
    observed_at_utc: str,
    source_message: str,
) -> dict[str, Any]:
    """An official filing may validate share counts; it cannot prove current EV."""
    instant = utc(observed_at_utc)
    if instant < datetime(2026, 9, 29, tzinfo=UTC):
        raise ValueError("observation precedes original QIP")
    if master_status not in ("OK", "BLOCKED", "FETCH_FAILED"):
        raise ValueError("unknown master source status")
    if xbrl_status not in ("OK", "BLOCKED", "NOT_ATTEMPTED", "FETCH_FAILED"):
        raise ValueError("unknown XBRL source status")
    if not isinstance(source_message, str) or not source_message:
        raise ValueError("source outcome requires explicit reason")
    if (master_status == "OK") != (isinstance(master_raw, bytes) and bool(master_raw)):
        raise ValueError("master source state and original bytes inconsistent")
    if (xbrl_status == "OK") != (isinstance(xbrl_raw, bytes) and bool(xbrl_raw)):
        raise ValueError("XBRL source state and original bytes inconsistent")

    selected = (
        choose_post_qip_filing(master_raw, observed_at_utc=observed_at_utc)
        if master_raw is not None else None
    )
    if selected is None and xbrl_status != "NOT_ATTEMPTED":
        raise ValueError("no post-QIP official candidate permits an XBRL fetch")
    share_counts: dict | None = None
    ownership: dict | None = None
    outcome = "NO_ELIGIBLE_POST_QIP_ORIGINAL_REG31_FILING"
    if master_raw is None:
        outcome = "MASTER_SOURCE_BLOCKED"
    elif selected is not None and xbrl_raw is None:
        outcome = "ORIGINAL_XML_NOT_AVAILABLE"
    elif selected is not None and xbrl_raw is not None:
        try:
            share_counts = parse_shareholding_counts(xbrl_raw, symbol=SYMBOL)
        except (ValueError, TypeError) as exc:
            outcome = "BLOCKED_ORIGINAL_XML_SHARE_COUNTS_UNPARSABLE"
            source_message = f"{source_message}; {type(exc).__name__}"
        else:
            if share_counts["fully_paid_shares"] < QIP_BASIC_ISSUED_SHARES:
                outcome = "BLOCKED_ORIGINAL_SHARE_COUNT_BELOW_COMPLETED_QIP"
            elif share_counts["fully_paid_shares"] == QIP_BASIC_ISSUED_SHARES:
                outcome = "ORIGINAL_REPORTED_POST_QIP_SHARE_COUNTS_CAPTURED"
            else:
                outcome = "ORIGINAL_REPORTED_LATER_SHARE_COUNT_CAPTURED"
            try:
                ownership = parse_current_governance_xbrl(
                    xbrl_raw,
                    symbol=SYMBOL,
                    report_date=selected["report_date"],
                    source_url=selected["xbrl_url"],
                )
            except (GF001GovernanceError, ValueError, TypeError):
                ownership = None
    if share_counts is not None and (
        type(share_counts.get("fully_paid_shares")) is not int
        or type(share_counts.get("fully_diluted_shares")) is not int
    ):
        raise TypeError("NSE XBRL share-count parser returned invalid types")
    if share_counts is not None and (
        share_counts["fully_paid_shares"] <= 0
        or share_counts["fully_diluted_shares"] < share_counts["fully_paid_shares"]
    ):
        raise ValueError("NSE XBRL share-count identity mathematically invalid")
    share_increment = (
        share_counts["fully_diluted_shares"] - share_counts["fully_paid_shares"]
        if share_counts is not None else None
    )
    output: dict[str, Any] = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "symbol": SYMBOL,
        "isin": ISIN,
        "classification": "OFFICIAL_POST_QIP_SHAREHOLDING_SOURCE_NOT_VALUATION",
        "observed_at_utc": instant.isoformat().replace("+00:00", "Z"),
        "source_query_url": MASTER_URL + "?index=equities&symbol=INOXGREEN",
        "master_source_state": master_status,
        "master_original_raw_sha256": _hash(master_raw) if master_raw is not None else None,
        "master_original_byte_count": len(master_raw) if master_raw is not None else None,
        "selected_original_filing": selected,
        "xbrl_source_state": xbrl_status,
        "xbrl_original_raw_sha256": _hash(xbrl_raw) if xbrl_raw is not None else None,
        "xbrl_original_byte_count": len(xbrl_raw) if xbrl_raw is not None else None,
        "evidence_status": outcome,
        "reported_share_counts": share_counts,
        "reported_dilution_instruments_increment_not_necessarily_esop": share_increment,
        "reported_promoter_and_pledge_context": ownership,
        "pre_qip_march_reported_fd_shares": MARCH_FD_SHARES,
        "29sep_qip_reported_issued_shares": QIP_BASIC_ISSUED_SHARES,
        "source_message": source_message,
        "source_is_current_as_of_future_investment_decision": False,
        "full_post_qip_equity_market_cap_approved": False,
        "cash_adjusted_enterprise_value_approved": False,
        "promoter_pledge_independently_document_reviewed": False,
        "source_complete_wwil_income_and_cashflows": False,
        "equity_expected_return_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["record_sha256"] = _hash(
        json.dumps(output, sort_keys=True, allow_nan=False, ensure_ascii=False).encode()
    )
    return output


def require_independently_verified_enterprise_value(report: dict[str, Any]) -> None:
    if report.get("report_id") != REPORT_ID:
        raise ValueError("wrong NSE original Reg31 risk protocol")
    for field in ("full_post_qip_equity_market_cap_approved",
                  "cash_adjusted_enterprise_value_approved"):
        if report.get(field) is not True:
            raise ValueError("post-QIP stock fair-value and net cash basis still blocked")
    raise ValueError("this is source discovery, not approved stock valuation")
