from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_announcements import normalize_announcement_payload
from marketlab.ss001_census import parse_equity_security_master
from marketlab.ss002_special_situations import (
    CATEGORY_TOKENS,
    approved_attachment_url,
    classify_special_situation,
)

CAPTURE_ID = "SS002-P001-v1"
FIRST_SOURCE_DATE = date(2026, 10, 5)
IST = ZoneInfo("Asia/Kolkata")
ANNOUNCEMENT_SOURCE_URL = "https://www.nseindia.com/api/corporate-announcements"
EQUITY_MASTER_SOURCE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


def raw_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deterministic_gzip(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)


def classify_capture_lag(day: date, *, observed_at_utc: str) -> str:
    try:
        stamp = datetime.fromisoformat(observed_at_utc)
    except ValueError as exc:
        raise AlphaContractError("P001 invalid acquisition timestamp") from exc
    if stamp.tzinfo is None:
        raise AlphaContractError("P001 acquisition timestamp needs timezone")
    local_day = stamp.astimezone(IST).date()
    if day < FIRST_SOURCE_DATE:
        raise AlphaContractError("P001 source date predates frozen October 5 boundary")
    if day >= local_day:
        raise AlphaContractError("P001 requires the full India-local source day to finish")
    return (
        "NEXT_DAY_SOURCE_CAPTURE"
        if (local_day - day).days == 1
        else "HISTORICAL_BACKFILL_CAPTURED_LATER"
    )


def _check_source_payload(raw: bytes, decoded: object, name: str) -> None:
    if not raw:
        raise AlphaContractError(f"P001 {name} raw source is empty")
    try:
        loaded = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AlphaContractError(f"P001 {name} raw JSON unreadable") from exc
    if loaded != decoded:
        raise AlphaContractError(f"P001 {name} payload differs from raw source")


def build_daily_capture(
    *,
    source_day: date,
    announcement_payload: object,
    announcement_raw: bytes,
    equity_master_raw: bytes,
    acquired_at_utc: str,
) -> dict[str, Any]:
    lag_state = classify_capture_lag(source_day, observed_at_utc=acquired_at_utc)
    _check_source_payload(announcement_raw, announcement_payload, "announcement")

    rows = normalize_announcement_payload(
        announcement_payload,
        requested_start=source_day,
        requested_end=source_day,
    )
    security_master = parse_equity_security_master(equity_master_raw)
    by_symbol = {member.symbol: member for member in security_master}
    master_sha = raw_sha256(equity_master_raw)
    announcement_sha = raw_sha256(announcement_raw)
    master_zip = deterministic_gzip(equity_master_raw)
    announcement_zip = deterministic_gzip(announcement_raw)

    all_announcements = []
    candidates = []
    category_counts: Counter[str] = Counter()
    states: Counter[str] = Counter()

    for row in rows:
        symbol = str(row["symbol"]).upper()
        master = by_symbol.get(symbol)
        mapping_state = (
            "SYMBOL_IN_EQ_MASTER_AT_CAPTURE"
            if master is not None
            else "ARCHIVAL_OR_UNMATCHED_AT_CAPTURE"
        )
        all_announcements.append(row)
        category_hints = classify_special_situation(row)
        if not category_hints:
            continue
        for category in category_hints:
            if category not in CATEGORY_TOKENS:
                raise AlphaContractError("P001 taxonomy drift")
            category_counts[category] += 1

        original_url = row.get("attchmntFile")
        approved_url = approved_attachment_url(original_url)
        attachment_state = (
            "OFFICIAL_URL"
            if approved_url is not None
            else "INVALID_OR_NONOFFICIAL_URL"
            if str(original_url or "").strip()
            else "ABSENT"
        )
        states[mapping_state] += 1
        candidates.append(
            {
                **row,
                "category_hints_only": category_hints,
                "economic_relevance_verified": False,
                "mapping_state": mapping_state,
                "current_eq_isin_at_capture": master.isin if master else None,
                "current_eq_name_at_capture": master.company_name if master else None,
                "attachment_state": attachment_state,
                "approved_attachment_url": approved_url,
                "source_raw_sha256": announcement_sha,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    out = {
        "schema_version": 1,
        "capture_id": f"SS002-P001-{source_day.isoformat()}-v1",
        "contract_id": CAPTURE_ID,
        "classification": "SOURCE_ONLY_DAILY_ANNOUNCEMENT_CAPTURE_NOT_INVESTMENT_SIGNAL",
        "source_day_ist": source_day.isoformat(),
        "acquired_at_utc": acquired_at_utc,
        "source_lag_state": lag_state,
        "sources": {
            "announcement": {
                "url": ANNOUNCEMENT_SOURCE_URL,
                "query": {
                    "index": "equities",
                    "from_date": source_day.strftime("%d-%m-%Y"),
                    "to_date": source_day.strftime("%d-%m-%Y"),
                },
                "raw_sha256": announcement_sha,
                "raw_byte_count": len(announcement_raw),
                "gzip_sha256": raw_sha256(announcement_zip),
                "gzip_byte_count": len(announcement_zip),
                "relative_path": (
                    f"research/prospective/ss002-p001/raw/announcements/"
                    f"{announcement_sha}.json.gz"
                ),
            },
            "eq_master": {
                "url": EQUITY_MASTER_SOURCE_URL,
                "as_of": "ACQUISITION_TIME_NOT_SOURCE_DAY",
                "raw_sha256": master_sha,
                "raw_byte_count": len(equity_master_raw),
                "gzip_sha256": raw_sha256(master_zip),
                "gzip_byte_count": len(master_zip),
                "relative_path": (
                    f"research/prospective/ss002-p001/raw/equity-master/"
                    f"{master_sha}.csv.gz"
                ),
            },
        },
        "eq_master_identity_count_at_capture": len(security_master),
        "announcement_count": len(rows),
        "candidate_event_count": len(candidates),
        "candidate_current_eq_event_count": sum(
            row["mapping_state"] == "SYMBOL_IN_EQ_MASTER_AT_CAPTURE" for row in candidates
        ),
        "category_hint_counts": dict(sorted(category_counts.items())),
        "candidate_mapping_state_counts": dict(sorted(states.items())),
        "announcements": all_announcements,
        "candidate_events": candidates,
        "model_inference_executed": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    if len({row["announcement_id"] for row in all_announcements}) != len(rows):
        raise AlphaContractError("P001 duplicate announcement identity")
    if not all(row["announcement_id"] in {p["announcement_id"] for p in rows} for row in candidates):
        raise AlphaContractError("P001 candidate not found in canonical announcements")
    out["capture_sha256"] = digest(out)
    return out
