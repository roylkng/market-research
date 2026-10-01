from __future__ import annotations

from datetime import date
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_d010_sources import PROBE_DATES

D010_P2_ID = "AE001-D010-P2-v1"
SLB_ARCHIVE_PATTERN = (
    "https://nsearchives.nseindia.com/archives/slbs/open_pos/"
    "slb_openpos_{ddmmyyyy}.csv"
)


def slb_archive_url(session_date: date) -> str:
    return SLB_ARCHIVE_PATTERN.format(
        ddmmyyyy=session_date.strftime("%d%m%Y")
    )


def summarize_p2(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {value.isoformat() for value in PROBE_DATES}
    if len(attempts) != len(PROBE_DATES):
        raise AlphaContractError(
            "D010 P2 requires exactly one SLB attempt per frozen date"
        )
    dates = {str(row.get("session_date") or "") for row in attempts}
    if dates != expected:
        raise AlphaContractError(
            "D010 P2 attempts do not match frozen probe dates"
        )
    ready = [
        row for row in attempts
        if row["response"]["status"] == "READY"
    ]
    headers = {
        tuple(row["response"]["header"] or ())
        for row in ready
    }
    if len(ready) == len(PROBE_DATES):
        if len(headers) != 1:
            status = "READY_ALL_SESSIONS_SCHEMA_UNSTABLE"
        else:
            status = "PROMOTE_P3_HISTORICAL_COVERAGE"
    else:
        status = "SLB_ARCHIVE_NOT_READY_ALL_FROZEN_SESSIONS"

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D010_P2_ID,
        "evidence_class": "SOURCE_DISCOVERY_NO_RETURN_OUTCOMES",
        "p1_report_sha256": (
            "fb815a3d26c1aea506fa4c956588f2563435e5b0a08729a6a8a3191fcd2978f6"
        ),
        "archive_pattern": SLB_ARCHIVE_PATTERN,
        "probe_sessions": [value.isoformat() for value in PROBE_DATES],
        "attempts": attempts,
        "ready_count": len(ready),
        "schema_count": len(headers),
        "schema": (
            list(next(iter(headers)))
            if len(headers) == 1
            else None
        ),
        "status": status,
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
