from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date
from typing import Any

from marketlab.alpha import AlphaContractError, digest

D010_DIAGNOSTIC_ID = "AE001-D010-P0-v1"
PROBE_DATES = (
    date(2026, 9, 25),
    date(2026, 9, 24),
    date(2025, 9, 1),
)

SHORT_PATTERNS = (
    "https://nsearchives.nseindia.com/products/content/shortselling_{ddmmyyyy}.csv",
    "https://nsearchives.nseindia.com/content/equities/shortselling_{ddmmyyyy}.csv",
    "https://nsearchives.nseindia.com/content/cm/shortselling_{ddmmyyyy}.csv",
    "https://nsearchives.nseindia.com/content/shortselling/shortselling_{ddmmyyyy}.csv",
)

SLB_PATTERNS = (
    "https://nsearchives.nseindia.com/content/slbs/slb_openpos_{ddmmyyyy}.csv",
    "https://nsearchives.nseindia.com/content/slb/slb_openpos_{ddmmyyyy}.csv",
    "https://nsearchives.nseindia.com/products/content/slb_openpos_{ddmmyyyy}.csv",
    "https://nsearchives.nseindia.com/content/SLBS/slb_openpos_{ddmmyyyy}.csv",
)

SOURCE_FAMILIES = {
    "CM_SHORT_SELLING": SHORT_PATTERNS,
    "SLB_DAILY_OPEN_POSITIONS": SLB_PATTERNS,
}


@dataclass(frozen=True)
class ProbeResponse:
    status_code: int
    content_type: str
    body: bytes


def render_url(pattern: str, session_date: date) -> str:
    return pattern.format(ddmmyyyy=session_date.strftime("%d%m%Y"))


def _looks_like_html(body: bytes, content_type: str) -> bool:
    prefix = body.lstrip()[:256].lower()
    return (
        "text/html" in content_type.lower()
        or prefix.startswith((b"<!doctype html", b"<html"))
    )


def inspect_csv_response(
    response: ProbeResponse,
    *,
    url: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "url": url,
        "status_code": int(response.status_code),
        "content_type": str(response.content_type or ""),
        "byte_length": len(response.body),
        "raw_sha256": (
            hashlib.sha256(response.body).hexdigest()
            if response.body
            else None
        ),
        "header": None,
        "data_row_count": None,
        "status": "HTTP_NOT_READY",
    }
    if response.status_code != 200:
        return result
    if not response.body:
        result["status"] = "EMPTY_BODY"
        return result
    if _looks_like_html(response.body, response.content_type):
        result["status"] = "HTML_RESPONSE"
        return result
    try:
        text = response.body.decode("utf-8-sig")
    except UnicodeDecodeError:
        result["status"] = "NON_UTF8_RESPONSE"
        return result

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        result["status"] = "EMPTY_CSV"
        return result
    normalized = [str(value).strip() for value in header]
    if not any(normalized):
        result["status"] = "EMPTY_HEADER"
        return result
    row_count = 0
    try:
        for row in reader:
            if any(str(value).strip() for value in row):
                row_count += 1
    except csv.Error:
        result["status"] = "CSV_PARSE_ERROR"
        return result

    result["header"] = normalized
    result["data_row_count"] = row_count
    result["status"] = "READY"
    return result


def summarize_discovery(
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    if not attempts:
        raise AlphaContractError("D010 discovery attempts cannot be empty")

    by_family: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        family = str(attempt.get("family") or "")
        pattern_index = attempt.get("pattern_index")
        session_date = str(attempt.get("session_date") or "")
        if family not in SOURCE_FAMILIES:
            raise AlphaContractError(f"unknown D010 source family: {family}")
        if (
            isinstance(pattern_index, bool)
            or not isinstance(pattern_index, int)
            or pattern_index < 0
            or pattern_index >= len(SOURCE_FAMILIES[family])
        ):
            raise AlphaContractError("invalid D010 pattern index")
        date.fromisoformat(session_date)
        by_family.setdefault(family, []).append(attempt)

    family_results = {}
    for family, patterns in SOURCE_FAMILIES.items():
        family_attempts = by_family.get(family, [])
        ready_patterns = []
        pattern_diagnostics = []
        for pattern_index, pattern in enumerate(patterns):
            rows = [
                row
                for row in family_attempts
                if row["pattern_index"] == pattern_index
            ]
            dates = {str(row["session_date"]) for row in rows}
            ready_dates = {
                str(row["session_date"])
                for row in rows
                if row["response"]["status"] == "READY"
            }
            complete = dates == {value.isoformat() for value in PROBE_DATES}
            ready_all = (
                complete
                and ready_dates
                == {value.isoformat() for value in PROBE_DATES}
            )
            if ready_all:
                ready_patterns.append(pattern_index)
            pattern_diagnostics.append(
                {
                    "pattern_index": pattern_index,
                    "pattern": pattern,
                    "probe_count": len(rows),
                    "ready_count": len(ready_dates),
                    "ready_all_frozen_sessions": ready_all,
                }
            )

        if len(ready_patterns) == 1:
            status = "PROMOTE_P1"
            selected_index = ready_patterns[0]
        elif not ready_patterns:
            status = "NO_PATTERN_READY_ALL_SESSIONS"
            selected_index = None
        else:
            status = "AMBIGUOUS_MULTIPLE_READY_PATTERNS"
            selected_index = None

        family_results[family] = {
            "status": status,
            "selected_pattern_index": selected_index,
            "selected_pattern": (
                None if selected_index is None else patterns[selected_index]
            ),
            "patterns": pattern_diagnostics,
        }

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D010_DIAGNOSTIC_ID,
        "evidence_class": "SOURCE_DISCOVERY_NO_RETURN_OUTCOMES",
        "probe_sessions": [value.isoformat() for value in PROBE_DATES],
        "attempt_count": len(attempts),
        "families": family_results,
        "all_families_promote_p1": all(
            value["status"] == "PROMOTE_P1"
            for value in family_results.values()
        ),
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
