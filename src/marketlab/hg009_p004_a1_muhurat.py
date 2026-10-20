"""NSE CMTR/76941 custody and conservative Nov 8 Muhurat calendar amendment.

Source is an Oct 19, 2026 official NSE capital-market circular, not a price
outcome. The original Oct 14 HG009 cohort/calendar protocol stays unchanged.
A derivative amendment is admitted only if original PDF bytes are archived,
its two-page text independently proves the actual session, and the first
real source observation occurs before the special session starts.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p004_clock import FIRST_ENTRY, load_p004_inputs
from marketlab.hg009_p004_clock import PROTOCOL_ID as ORIGINAL_PROTOCOL_ID

SOURCE_URL = "https://nsearchives.nseindia.com/content/circulars/CMTR76941.pdf"
SOURCE_CIRCULAR = "NSE/CMTR/76941"
SOURCE_ISSUED = "2026-10-19"
SPECIAL_DATE = "2026-11-08"
AMENDMENT_ID = "HG009-P004-A1-NOV08-2026-OFFICIAL-NSE-SPECIAL-SESSION-v1"
ORIGINAL_HG009_CLOCK_SHA = (
    "da4588603dd248fb434ce956f2e89e833854e1c4cd268599c0f755ac4fea8aa9"
)
ORIGINAL_CALENDAR_SHA = (
    "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
)
PDF_DIR = Path("research/hg009/p004-a1/originals")
AMENDMENT_PATH = Path("research/hg009/hg009-p004-a1-nov08-calendar-v1.json")
SAFE_AFTER_ALL_SESSIONS_UTC = "2026-11-08T10:45:00+00:00"  # 16:15 IST
FIRST_TRADE_UTC = "2026-11-08T08:50:00+00:00"  # 14:20 IST
CAS_LAST_TRADE_UTC = "2026-11-08T10:05:00+00:00"  # 15:35 IST
NONCAS_LAST_TRADE_UTC = "2026-11-08T10:00:00+00:00"  # 15:30 IST


def _utc(value: str, *, label: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise AlphaContractError(f"A1 invalid {label}") from exc
    if stamp.tzinfo is None:
        raise AlphaContractError(f"A1 {label} must have timezone")
    return stamp.astimezone(UTC)


def _pdf_text(raw: bytes) -> tuple[int, str]:
    if not raw.startswith(b"%PDF-") or len(raw) < 100:
        raise AlphaContractError("A1 source not a nonempty original PDF")
    if len(raw) > 3_000_000:
        raise AlphaContractError("A1 unexpected original circular size")
    try:
        pdf = PdfReader(io.BytesIO(raw), strict=True)
        pages = len(pdf.pages)
        text = " ".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise AlphaContractError("A1 original PDF not structurally readable") from exc
    return pages, text


def validate_original_nse_circular(raw: bytes) -> dict[str, Any]:
    count, original_text = _pdf_text(raw)
    if count != 2:
        raise AlphaContractError("A1 original circular requires exact 2 pages")
    text = re.sub(r"\s+", " ", original_text).casefold()
    essential = (
        "national stock exchange of india limited",
        "nse/cmtr/76941",
        "october 19, 2026",
        "november 08, 2026",
        "muhurat",
        "capital market segment",
        "14:20",
        "15:15",
        "15:30",
        "15:35",
        "16:15",
        "closing auction session",
        "non-cas",
        "all trades executed",
        "settlement obligations",
    )
    missing = [s for s in essential if s.casefold() not in text]
    if missing:
        raise AlphaContractError(
            f"A1 original circular content missing mandatory evidence: {missing}"
        )
    return {
        "pdf_pages": count,
        "raw_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "normalized_page_text_sha256": hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest(),
        "source_issue_date": SOURCE_ISSUED,
        "session_date": SPECIAL_DATE,
        "preopen_start_ist": "14:05",
        "continuous_trading_start_ist": "14:20",
        "closing_auction_continuous_market_close_ist": "15:15",
        "closing_auction_final_match_ist": "15:35",
        "non_auction_continuous_market_close_ist": "15:30",
        "last_trading_modification_ist": "16:15",
        "source_is_trade_fill_or_stock_return": False,
    }


def validate_circular_receipt(
    receipt: dict[str, Any], *, raw: bytes
) -> None:
    if (
        receipt.get("receipt_id") != "HG009-P004-A1-NSE-CIRCULAR-RECEIPT-v1"
        or receipt.get("source_url") != SOURCE_URL
        or receipt.get("source_state") != "ORIGINAL_CIRCULAR_ARCHIVED"
        or receipt.get("actual_http_status") != 200
        or receipt.get("original_pdf_sha256") != hashlib.sha256(raw).hexdigest()
        or receipt.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("A1 original source receipt not admissible")
    unsigned = copy.deepcopy(receipt)
    stored = unsigned.pop("receipt_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("A1 signed original source receipt altered")
    observed = _utc(receipt["captured_at_utc"], label="PDF actual retrieval")
    if not (
        _utc("2026-10-19T00:00:00Z", label="circular publication")
        <= observed
        < _utc(FIRST_TRADE_UTC, label="special first trade")
    ):
        raise AlphaContractError("A1 original source not captured prospectively")
    proven = validate_original_nse_circular(raw)
    if proven != receipt.get("original_circular_proof"):
        raise AlphaContractError("A1 stored source page proof differs from bytes")
    if receipt.get("original_pdf_repo_path") != str(
        PDF_DIR / f"CMTR76941-{proven['raw_sha256']}.pdf"
    ):
        raise AlphaContractError("A1 content-addressed PDF path mismatched")


def build_amendment(
    *,
    root: Path,
    receipt: dict[str, Any],
    original_pdf: bytes,
) -> dict[str, Any]:
    validate_circular_receipt(receipt, raw=original_pdf)
    calendar, original, selected, controls = load_p004_inputs(root)
    if calendar.sha256 != ORIGINAL_CALENDAR_SHA:
        raise AlphaContractError("A1 original calendar SHA changed")
    from marketlab.hg009_p004_clock import build_hg009_outcome_clock

    clock = build_hg009_outcome_clock(
        calendar=calendar,
        original=original,
        selected=selected,
        controls=controls,
    )
    if (
        clock["protocol_id"] != ORIGINAL_PROTOCOL_ID
        or clock["protocol_sha256"] != ORIGINAL_HG009_CLOCK_SHA
        or clock["planned_horizon_status"]["20"]["state"]
        != "UNRESOLVED_EXCHANGE_SPECIAL_SESSION_BLOCKS_RESULT"
        or list(calendar.unresolved_special_dates) != [SPECIAL_DATE]
        or SPECIAL_DATE in [row.session_date for row in calendar.sessions]
    ):
        raise AlphaContractError("A1 original immutable P004 blocker changed")

    original_dates = [session.session_date for session in calendar.sessions]
    if original_dates != sorted(original_dates):
        raise AlphaContractError("A1 original NSE regular dates out of order")
    amended = sorted([*original_dates, SPECIAL_DATE])
    if len(amended) != len(original_dates) + 1:
        raise AlphaContractError("A1 official special session inserted twice")
    i = amended.index(FIRST_ENTRY)
    h1 = amended[i : i + 1]
    h5 = amended[i : i + 5]
    h20 = amended[i : i + 20]
    if (
        h1 != clock["planned_horizon_status"]["1"]["date_scoped_holding_sessions"]
        or h5 != clock["planned_horizon_status"]["5"]["date_scoped_holding_sessions"]
        or h20[-1] != "2026-11-12"
        or SPECIAL_DATE not in h20
        or len(h20) != 20
    ):
        raise AlphaContractError("A1 original H1/H5 changed or H20 sequence wrong")
    if (
        clock["planned_horizon_status"]["60"]["state"]
        != "REQUIRES_NEW_OFFICIAL_FORWARD_CALENDAR"
    ):
        raise AlphaContractError("A1 2027 H60 cannot be retrospectively repaired")

    result: dict[str, Any] = {
        "schema_version": 1,
        "amendment_id": AMENDMENT_ID,
        "protocol_registration_date": receipt["captured_at_utc"],
        "original_oct14_P004_clock_sha256": ORIGINAL_HG009_CLOCK_SHA,
        "original_2026_calendar_sha256": ORIGINAL_CALENDAR_SHA,
        "original_oct15_100_plus_200_company_identity_set_unchanged": True,
        "source_circular": SOURCE_CIRCULAR,
        "source_circular_issued": SOURCE_ISSUED,
        "source_url": SOURCE_URL,
        "original_source_captured_at_utc": receipt["captured_at_utc"],
        "original_source_pdf_sha256": receipt["original_pdf_sha256"],
        "original_source_pdf_path": receipt["original_pdf_repo_path"],
        "original_receipt_sha256": receipt["receipt_sha256"],
        "prospective_special_session": {
            "session_date": SPECIAL_DATE,
            "is_sunday": True,
            "regular_trading_open_ist": "14:20",
            "closing_auction_matching_end_ist": "15:35",
            "non_CAS_regular_market_close_ist": "15:30",
            "market_last_modification_cutoff_ist": "16:15",
            "conservative_original_postmarket_source_minimum_utc": (
                SAFE_AFTER_ALL_SESSIONS_UTC
            ),
            "closing_prices_for_CAS_and_non_CAS_are_not_identical_inference": True,
            "official_original_UDiFF_price_required_after_special_session": True,
        },
        "h1_existing_original_dates_unchanged": h1,
        "h5_existing_original_dates_unchanged": h5,
        "original_H20_state_retained": (
            "UNRESOLVED_EXCHANGE_SPECIAL_SESSION_BLOCKS_RESULT"
        ),
        "amended_H20_20_exact_sessions": h20,
        "amended_H20_last_session": h20[-1],
        "H20_new_outcomes_observed_or_calculated": False,
        "H20_remains_awaiting_exact_original_NSE_EQ_and_index_source_bytes": True,
        "H20_share_actions_and_dividends_still_require_clearance": True,
        "H60_still_requires_official_2027_calendar": True,
        "original_Oct15_stock_selection_or_any_prior_outcome_changed": False,
        "no_backfilled_predictions_or_returns": True,
        "statistical_or_after_cost_alpha_claim": False,
        "live_capital_allowed": False,
    }
    result["amendment_sha256"] = digest(result)
    return result


def materialize_amendment(root: Path, receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads((root / receipt_path).read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise AlphaContractError("A1 original source receipt must be JSON object")
    raw_path = root / receipt["original_pdf_repo_path"]
    raw = raw_path.read_bytes()
    return build_amendment(root=root, receipt=receipt, original_pdf=raw)


def validate_amendment(
    packet: dict[str, Any], *, root: Path, receipt_path: Path
) -> None:
    unsigned = copy.deepcopy(packet)
    stored = unsigned.pop("amendment_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("A1 amendment packet SHA changed")
    if packet != materialize_amendment(root, receipt_path):
        raise AlphaContractError("A1 original NSE circular replay changed")
