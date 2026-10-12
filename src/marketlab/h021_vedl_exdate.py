"""Prospectively verify VEDL's October dividend ex-date from original NSE data.

Original October 8 issuer PDF proves INR5 and October14 RECORD date, but
does not explicitly establish the EX date or a hypothetical holder's cash
entitlement. This source probe may verify the NSE action-calendar ex-date
without inventing a trade, entitlement, total-return series or alpha.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXDATE_ID = "H021-P021-2026-10-14-VEDL-OFFICIAL-EXDATE-v1"
EXACT_NSE_API = (
    "https://www.nseindia.com/api/corporates-corporateActions"
    "?index=equities&symbol=VEDL&from_date=08-10-2026&to_date=16-10-2026"
)
EXPECTED_ISSUER_SOURCE_RECEIPT = Path(
    "research/prospective/h021/dividend-evidence/vedl-2026-10-08/source-receipt-v1.json"
)
EXPECTED_ISSUER_RECEIPT_GIT_BLOB = "de2d9889ec303067404ba62c136cd221288ac0ad"
EXPECTED_ISSUER_PDF_SHA = "abdd026339469b9e51ab75fb2a37551be23812dcc037c875759cd79a8e6cb364"
EXPECTED_ISSUER_PDF = Path(
    "research/prospective/h021/dividend-evidence/vedl-2026-10-08/original/sha256/"
    + EXPECTED_ISSUER_PDF_SHA
    + ".pdf"
)
PREDECLARED_EX_DATE = "2026-10-14"
PREDECLARED_RECORD_DATE = "2026-10-14"
EXDATE_SESSION_OPEN_UTC = "2026-10-14T03:45:00Z"
MAX_JSON_BYTES = 1_500_000


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_sha(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\x00" + data,
        usedforsecurity=False,
    ).hexdigest()


def _packet_sha(packet: dict[str, Any]) -> str:
    return _sha(json.dumps(
        packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8"))


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("official ex-date original-source timestamp must be a string")
    try:
        when = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("official ex-date original-source timestamp invalid") from exc
    if when.tzinfo is None:
        raise ValueError("official ex-date source timestamp must include timezone")
    return when.astimezone(UTC)


def verified_issuer_dividend_source(root: Path) -> dict[str, Any]:
    original_receipt_bytes = (root / EXPECTED_ISSUER_SOURCE_RECEIPT).read_bytes()
    if _git_sha(original_receipt_bytes) != EXPECTED_ISSUER_RECEIPT_GIT_BLOB:
        raise ValueError("original issuer VEDL PDF receipt Git blob changed")
    receipt = json.loads(original_receipt_bytes)
    if not isinstance(receipt, dict):
        raise TypeError("VEDL original issuer receipt must be object")
    declared = receipt.get("issuer_reported_dividend_terms")
    if not isinstance(declared, dict):
        raise TypeError("original issuer cash dividend terms missing")
    if (
        receipt.get("source_id") != "H021-P012-VEDL-2026-10-08-ORIGINAL-NSE-DIVIDEND-v1"
        or receipt.get("original_pdf_sha256") != EXPECTED_ISSUER_PDF_SHA
        or receipt.get("symbol") != "VEDL"
        or receipt.get("isin") != "INE205A01025"
        or receipt.get("state") != (
            "OFFICIAL_PDF_BYTES_AND_ISSUER_TEXT_CAPTURED_NOT_ENTITLEMENT_AUDITED"
        )
        or declared.get("issuer_reported_dividend_per_share_inr") != 5
        or declared.get("issuer_reported_record_date_ist") != PREDECLARED_RECORD_DATE
        or declared.get("ex_date_confirmed_by_this_pdf") is not False
        or receipt.get("portfolio_eligibility_allowed") is not False
        or receipt.get("live_capital_allowed") is not False
    ):
        raise ValueError("issuer dividend declaration/record-date source identity changed")
    raw = (root / EXPECTED_ISSUER_PDF).read_bytes()
    if _sha(raw) != EXPECTED_ISSUER_PDF_SHA:
        raise ValueError("original preentry issuer PDF byte SHA changed")
    return {
        "original_issuer_receipt_git_blob": EXPECTED_ISSUER_RECEIPT_GIT_BLOB,
        "original_issuer_pdf_sha256": EXPECTED_ISSUER_PDF_SHA,
        "original_board_reported_dividend_inr": 5,
        "original_board_reported_record_date_ist": PREDECLARED_RECORD_DATE,
        "pre_entry_source_public": True,
    }


def _rows(raw: bytes) -> list[dict[str, Any]]:
    if not isinstance(raw, bytes) or not 2 <= len(raw) <= MAX_JSON_BYTES:
        raise ValueError("original NSE action raw JSON source absent or oversized")
    try:
        obj = json.loads(raw)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ValueError("original NSE corporate-action JSON failed decoding") from exc
    if isinstance(obj, list):
        items = obj
    elif isinstance(obj, dict) and isinstance(obj.get("data"), list):
        items = obj["data"]
    elif isinstance(obj, dict) and isinstance(obj.get("records"), list):
        items = obj["records"]
    else:
        raise TypeError("original NSE corporate-action source lacks an event-row list")
    if any(not isinstance(row, dict) for row in items):
        raise ValueError("original NSE corporate action rows include invalid entry")
    return items


def _date(text: object) -> str | None:
    if not isinstance(text, str):
        return None
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _is_dividend(value: str) -> bool:
    return "dividend" in value.casefold()


def _rs5(value: str) -> bool:
    return bool(re.search(r"(?:rs\.?|inr|₹)\s*5(?:\.0+)?\b", value.casefold()))


def build_official_vedl_exdate_packet(
    *,
    root: Path,
    raw: bytes | None,
    source_receipt: dict[str, Any],
) -> dict[str, Any]:
    original = verified_issuer_dividend_source(root)
    if not isinstance(source_receipt, dict):
        raise TypeError("NSE original API source receipt must be object")
    if source_receipt.get("url") != EXACT_NSE_API:
        raise ValueError("NSE official VEDL corporate-action URL changed")
    recorded = _utc(source_receipt.get("captured_at_utc"))
    status = source_receipt.get("status")
    code = source_receipt.get("http_status")
    candidate = None
    source_state = "BLOCKED_OFFICIAL_ACTION_SOURCE_NOT_CAPTURED"
    row_count = None
    result_sha = None

    if status == "OK":
        if (
            code != 200
            or not isinstance(raw, bytes)
            or not raw
            or _sha(raw) != source_receipt.get("raw_sha256")
        ):
            raise ValueError("NSE VEDL original action bytes and successful receipt disagree")
        result_sha = _sha(raw)
        rows = _rows(raw)
        row_count = len(rows)
        found = []
        contradictory = []
        for row in rows:
            symbol = row.get("symbol") or row.get("Symbol") or row.get("SYMBOL")
            if symbol != "VEDL":
                continue
            series = str(row.get("series") or row.get("Series") or "EQ").strip().upper()
            if series != "EQ":
                continue
            purpose = str(
                row.get("purpose") or row.get("Purpose") or row.get("subject") or ""
            ).strip()
            if not _is_dividend(purpose):
                continue
            ex_date = _date(
                row.get("exDate") or row.get("ex_date") or row.get("EX-DATE")
            )
            record_date = _date(
                row.get("recordDate") or row.get("recDate") or row.get("record_date")
            )
            if (
                _rs5(purpose)
                and ex_date == PREDECLARED_EX_DATE
                and record_date in (None, PREDECLARED_RECORD_DATE)
            ):
                found.append({
                    "symbol": "VEDL",
                    "series": "EQ",
                    "nse_event_purpose": purpose,
                    "exchange_ex_date": ex_date,
                    "exchange_record_date_if_present": record_date,
                })
            else:
                contradictory.append({
                    "purpose": purpose,
                    "ex_date": ex_date,
                    "record_date": record_date,
                })
        if len(found) == 1 and not contradictory:
            source_state = "ORIGINAL_NSE_DIVIDEND_EXDATE_ROW_MATCHED"
            candidate = found[0]
        elif not found and not contradictory:
            source_state = "ORIGINAL_NSE_EXDATE_ROW_MISSING"
        else:
            source_state = "BLOCKED_AMBIGUOUS_OR_CONTRADICTORY_NSE_EVENT"
    else:
        if (
            status not in ("ACCESS_BLOCKED", "NOT_PUBLISHED", "FETCH_FAILED")
            or raw is not None
            or not isinstance(source_receipt.get("error"), str)
            or not source_receipt["error"]
        ):
            raise ValueError("invalid blocked NSE corporate-action capture receipt")
        if status == "ACCESS_BLOCKED" and code not in (401, 403, 429):
            raise ValueError("NSE access blocked must preserve original denial code")
        if status == "NOT_PUBLISHED" and code != 404:
            raise ValueError("NSE original source not-published requires 404")
        source_state = "BLOCKED_" + status

    pre_ex_date_source = status == "OK" and recorded < _utc(EXDATE_SESSION_OPEN_UTC)
    packet = {
        "schema_version": 1,
        "review_id": EXDATE_ID,
        "classification": "OFFICIAL_NSE_EVENT_DATE_EVIDENCE_NOT_DIVIDEND_RETURN_ENTITLEMENT",
        "selected_symbol": "VEDL",
        "selected_isin": "INE205A01025",
        "frozen_first_h021_entry_date": "2026-10-12",
        "original_issuer_source": original,
        "original_nse_action_source_url": EXACT_NSE_API,
        "source_captured_at_utc": recorded.isoformat().replace("+00:00", "Z"),
        "source_http_status": code,
        "source_state": source_state,
        "source_raw_sha256": result_sha,
        "source_original_event_row_count": row_count,
        "official_matching_row": candidate,
        "original_exchange_ex_date_verified": (
            source_state == "ORIGINAL_NSE_DIVIDEND_EXDATE_ROW_MATCHED"
        ),
        "source_retrieved_before_oct14_ex_open": pre_ex_date_source,
        "dividend_cash_per_share_from_original_issuer_inr": 5,
        "issuer_reported_record_date_ist": PREDECLARED_RECORD_DATE,
        "hypothetical_oct12_open_is_actual_trade": False,
        "dividend_cash_entitlement_assessed_or_paid": False,
        "all_h021_ten_company_actions_exhaustively_audited": False,
        "index_total_return_and_equity_dividends_comparable": False,
        "twenty_sixty_session_outcomes_opened": False,
        "stock_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = _packet_sha(packet)
    return packet
