"""First-seen NSE announcement *discovery* clock, never a stage forecast.

HG008's five historical transaction-stage baselines require future
independently reviewed ORIGINAL PDF milestones within 8 hours of initial
public disclosure. Next-day SS002 P001 collection cannot guarantee this.
Hourly original announcement snapshots only queue possible source events.
No announcement keyword establishes a first-ever stage or stock alpha.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha_announcements import (
    HISTORICAL_COLLAPSE_EXACT_CANONICAL,
    normalize_announcement_payload,
)
from marketlab.ss002_special_situations import (
    approved_attachment_url,
    classify_special_situation,
)

PILOT_ID = "HG008-P002-INTRADAY-ORIGINAL-NSE-ANNOUNCEMENT-CLOCK-v1"
OFFICIAL_SOURCE_URL = "https://www.nseindia.com/api/corporate-announcements"
START_UTC = datetime(2026, 10, 14, tzinfo=UTC)
END_UTC = datetime(2026, 11, 14, tzinfo=UTC)
MAX_HOURS_FOR_STAGE_FORECAST = 8
MAX_ORIGINAL_BYTES = 8_000_000
MAX_ORIGINAL_ROWS = 3_500
IST = ZoneInfo("Asia/Kolkata")


def _utc(raw: object) -> datetime:
    if not isinstance(raw, str):
        raise TypeError("source observation needs ISO timestamp")
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("invalid original NSE observation timestamp") from exc
    if stamp.tzinfo is None:
        raise ValueError("NSE observation timestamp must include timezone")
    return stamp.astimezone(UTC)


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            allow_nan=False, ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def expected_window(now_utc: str) -> tuple[date, date]:
    observed = _utc(now_utc)
    if not START_UTC <= observed < END_UTC:
        raise ValueError("outside frozen HG008 first-seen source-intake pilot")
    local_day = observed.astimezone(IST).date()
    return local_day - timedelta(days=1), local_day


def _verify_json_bytes(raw: bytes, decoded: object) -> None:
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_ORIGINAL_BYTES:
        raise ValueError("original NSE source bytes missing or out of bound")
    try:
        original = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("original NSE announcement source not valid UTF-8 JSON") from exc
    if original != decoded:
        raise ValueError("decoded NSE source differs from exact original JSON bytes")
    if isinstance(original, list):
        rows = original
    elif isinstance(original, dict):
        if isinstance(original.get("data"), list):
            rows = original["data"]
        elif isinstance(original.get("records"), list):
            rows = original["records"]
        else:
            raise ValueError("NSE payload does not contain explicit announcement rows")
    else:
        raise TypeError("original NSE announcement source must be row array/envelope")
    if len(rows) > MAX_ORIGINAL_ROWS or any(not isinstance(row, dict) for row in rows):
        raise ValueError("original NSE announcement rows are malformed or unbounded")


def build_intraday_discovery(
    *,
    source: object,
    original_raw: bytes,
    request_start: date,
    request_end: date,
    observed_at_utc: str,
) -> dict[str, Any]:
    observed = _utc(observed_at_utc)
    expected_from, expected_to = expected_window(observed_at_utc)
    if (request_start, request_end) != (expected_from, expected_to):
        raise ValueError("NSE query date window does not equal predeclared intraday window")
    _verify_json_bytes(original_raw, source)
    events = normalize_announcement_payload(
        source,
        requested_start=request_start,
        requested_end=request_end,
        duplicate_policy=HISTORICAL_COLLAPSE_EXACT_CANONICAL,
    )
    raw_sha = hashlib.sha256(original_raw).hexdigest()
    candidates = []
    clock_counts = {
        "POSSIBLE_STAGE_REVIEW_WITHIN_8H_NOT_VERIFIED": 0,
        "SOURCE_CAPTURE_AFTER_8H_NO_FIRST_SEEN_FORECAST": 0,
        "BEFORE_PROSPECTIVE_START": 0,
        "EXCHANGE_TIMESTAMP_AFTER_OBSERVATION_BLOCKED": 0,
    }
    for row in events:
        categories = classify_special_situation(row)
        if not categories:
            continue
        publication = _utc(row["exchange_published_at_utc"])
        lag = int((observed - publication).total_seconds())
        if publication < START_UTC:
            state = "BEFORE_PROSPECTIVE_START"
        elif lag < 0:
            state = "EXCHANGE_TIMESTAMP_AFTER_OBSERVATION_BLOCKED"
        elif lag > MAX_HOURS_FOR_STAGE_FORECAST * 3600:
            state = "SOURCE_CAPTURE_AFTER_8H_NO_FIRST_SEEN_FORECAST"
        else:
            state = "POSSIBLE_STAGE_REVIEW_WITHIN_8H_NOT_VERIFIED"
        clock_counts[state] += 1
        url = approved_attachment_url(row.get("attchmntFile"))
        candidates.append({
            "symbol": row["symbol"],
            "source_announcement_id": row["announcement_id"],
            "nse_sequence_id": row["seq_id"],
            "exchange_reported_announcement_utc": row["exchange_published_at_utc"],
            "original_source_observed_at_utc": observed_at_utc,
            "source_observation_lag_seconds": lag,
            "nse_description": row["desc"],
            "nse_attachment_text": row["attchmntText"],
            "source_original_pdf_url_if_approved": url,
            "source_original_pdf_sha256": None,
            "category_text_hints_only": categories,
            "source_clock_state": state,
            "same_security_prior_stage_search_completed": False,
            "first_stage_public_time_independently_verified": False,
            "current_company_isin_from_official_source_verified": False,
            "source_original_pdf_pages_independently_reviewed": False,
            "stage_semantic_review_approved": False,
            "selected_event_family_and_track_verified": False,
            "candidate_eligible_for_hg008_forecast": False,
            "company_stock_return_predicted": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        })
    packet: dict[str, Any] = {
        "schema_version": 1,
        "discovery_id": PILOT_ID,
        "classification": "EXCHANGE_SOURCE_CLOCK_REVIEW_QUEUE_NO_STAGE_PROBABILITIES",
        "source_query": {
            "url": OFFICIAL_SOURCE_URL,
            "index": "equities",
            "from_date": request_start.strftime("%d-%m-%Y"),
            "to_date": request_end.strftime("%d-%m-%Y"),
        },
        "source_observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
        "source_original_raw_sha256": raw_sha,
        "source_original_raw_bytes": len(original_raw),
        "full_source_event_count": len(events),
        "category_candidate_count": len(candidates),
        "source_clock_states": clock_counts,
        "candidates": candidates,
        "original_pdf_bytes_acquired": False,
        "first_seen_stage_independently_certified_count": 0,
        "hg008_valid_forecasts_frozen": 0,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = _digest(packet)
    return packet


def validate_discovery_packet(packet: dict[str, Any]) -> None:
    if (
        packet.get("discovery_id") != PILOT_ID
        or packet.get("live_capital_allowed") is not False
        or packet.get("portfolio_eligibility_allowed") is not False
        or packet.get("hg008_valid_forecasts_frozen") != 0
        or packet.get("first_seen_stage_independently_certified_count") != 0
        or packet.get("return_outcomes_opened") is not False
    ):
        raise ValueError("HG008 discovery may not promote a source candidate to forecast")
    sha = packet.get("packet_sha256")
    if not isinstance(sha, str) or sha != _digest({
        k: v for k, v in packet.items() if k != "packet_sha256"
    }):
        raise ValueError("NSE intraday source-clock packet altered")
    for candidate in packet.get("candidates", []):
        if candidate.get("candidate_eligible_for_hg008_forecast") is not False:
            raise ValueError("keyword observation cannot count as a first-seen stage forecast")
        if candidate.get("source_original_pdf_sha256") is not None:
            raise ValueError("unfetched original PDF cannot acquire source SHA")
        if candidate.get("live_capital_allowed") is not False:
            raise ValueError("source queue cannot authorize capital")
