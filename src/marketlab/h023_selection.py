from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from marketlab.h023_ownership import previous_quarter_end
from marketlab.h023_prospective import (
    PROSPECTIVE_START_UTC,
    H023ProspectiveError,
    build_event_record,
    validate_source_ledger,
)


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise H023ProspectiveError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H023ProspectiveError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H023ProspectiveError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def strict_primary_current_source(
    ledger: dict[str, Any], *, symbol: str, report_date: str
) -> dict[str, Any] | None:
    validate_source_ledger(ledger)
    wanted = symbol.strip().upper()
    matches = [
        row["source"]
        for row in ledger["records"]
        if row["source"]["symbol"] == wanted
        and row["source"]["report_date"] == report_date
    ]
    if not matches:
        return None
    by_time: dict[datetime, list[dict[str, Any]]] = {}
    for source in matches:
        broadcast = _timestamp(
            source["broadcast_at_utc"], field=f"{source['source_id']}.broadcast_at_utc"
        )
        by_time.setdefault(broadcast, []).append(source)
    first_time = min(by_time)
    first = by_time[first_time]
    if len(first) != 1:
        ids = sorted(str(source["source_id"]) for source in first)
        raise H023ProspectiveError(
            f"{wanted}/{report_date}: ambiguous first official broadcast: {ids}"
        )
    return dict(first[0])


def strict_prior_source_at_event(
    ledger: dict[str, Any],
    *,
    symbol: str,
    current_report_date: str,
    current_broadcast_at_utc: str,
) -> dict[str, Any] | None:
    validate_source_ledger(ledger)
    wanted = symbol.strip().upper()
    prior_date = previous_quarter_end(current_report_date)
    current_time = _timestamp(
        current_broadcast_at_utc, field="current_broadcast_at_utc"
    )
    matches = [
        row["source"]
        for row in ledger["records"]
        if row["source"]["symbol"] == wanted
        and row["source"]["report_date"] == prior_date
        and _timestamp(
            row["source"]["broadcast_at_utc"],
            field=f"{row['source']['source_id']}.broadcast_at_utc",
        )
        <= current_time
    ]
    if not matches:
        return None
    by_time: dict[datetime, list[dict[str, Any]]] = {}
    for source in matches:
        broadcast = _timestamp(
            source["broadcast_at_utc"], field=f"{source['source_id']}.broadcast_at_utc"
        )
        by_time.setdefault(broadcast, []).append(source)
    latest_time = max(by_time)
    latest = by_time[latest_time]
    if len(latest) != 1:
        ids = sorted(str(source["source_id"]) for source in latest)
        raise H023ProspectiveError(
            f"{wanted}/{prior_date}: ambiguous latest prior broadcast at current event: {ids}"
        )
    return dict(latest[0])


def build_strict_event_record(
    *,
    source_ledger: dict[str, Any],
    symbol: str,
    report_date: str,
    frozen_at_utc: str,
    current_evidence: dict[str, Any] | None,
    prior_evidence: dict[str, Any] | None,
) -> dict[str, Any] | None:
    current = strict_primary_current_source(
        source_ledger, symbol=symbol, report_date=report_date
    )
    if current is None:
        return None
    if _timestamp(current["broadcast_at_utc"], field="current.broadcast_at_utc") < PROSPECTIVE_START_UTC:
        return None
    strict_prior = strict_prior_source_at_event(
        source_ledger,
        symbol=symbol,
        current_report_date=report_date,
        current_broadcast_at_utc=str(current["broadcast_at_utc"]),
    )
    record = build_event_record(
        source_ledger=source_ledger,
        symbol=symbol,
        report_date=report_date,
        frozen_at_utc=frozen_at_utc,
        current_evidence=current_evidence,
        prior_evidence=prior_evidence,
    )
    if record is None:
        return None
    if record["current_source"] != current:
        raise H023ProspectiveError("base event builder disagrees with strict current source")
    if record["status"] in {"SIGNAL", "PRIOR_SOURCE_BLOCKED"}:
        if record["prior_source"] != strict_prior:
            raise H023ProspectiveError("base event builder disagrees with strict prior source")
    elif record["status"] == "NO_SIGNAL_PRIOR_UNAVAILABLE" and strict_prior is not None:
        raise H023ProspectiveError("base event builder lost an available strict prior source")
    return record
