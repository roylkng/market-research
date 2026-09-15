from __future__ import annotations

import math
import statistics
from datetime import UTC, datetime
from typing import Any

from marketlab.h024_acquisition import canonical_hash
from marketlab.h024_prospective import (
    PROTOCOL_ID,
    H024ProspectiveError,
    evidence_by_source,
    source_by_id,
    source_first_seen,
    validate_evidence_ledger,
    validate_signal_ledger,
    validate_source_ledger,
)

EVENT_LEDGER_VERSION = 1
LIQUIDITY_MEDIAN_20D_MIN_INR = 20_000_000.0
MIN_PRICE_HISTORY_SESSIONS = 60
PRIMARY_EVENT_STATUS = "PRIMARY_ELIGIBLE"
EXCLUDED_EVENT_STATUS = "EXCLUDED"
EVENT_STATUSES = frozenset({PRIMARY_EVENT_STATUS, EXCLUDED_EVENT_STATUS})
EXCLUSION_REASONS = frozenset(
    {
        "REVISION_BLOCKED",
        "LATE_EVENT_FREEZE",
        "SECURITY_MASTER_BLOCKED",
        "INSUFFICIENT_60_SESSION_PRICE_HISTORY",
        "LIQUIDITY_BELOW_H004_PRIMARY",
        "MARKET_EVIDENCE_UNRESOLVED",
    }
)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise H024ProspectiveError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H024ProspectiveError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H024ProspectiveError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise H024ProspectiveError("timestamp must include timezone")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _record_hash(record: dict[str, Any], field: str) -> str:
    return canonical_hash({key: value for key, value in record.items() if key != field})


def _ledger_hash(ledger: dict[str, Any]) -> str:
    return canonical_hash({key: value for key, value in ledger.items() if key != "ledger_sha256"})


def new_event_ledger() -> dict[str, Any]:
    ledger = {
        "schema_version": EVENT_LEDGER_VERSION,
        "protocol_id": PROTOCOL_ID,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def event_id(symbol: str, planned_entry_session: str) -> str:
    clean_symbol = str(symbol).strip().upper()
    if not clean_symbol or not planned_entry_session:
        raise H024ProspectiveError("H024 event identity is incomplete")
    return canonical_hash(
        {
            "protocol_id": PROTOCOL_ID,
            "symbol": clean_symbol,
            "planned_entry_session": str(planned_entry_session),
        }
    )


def _validate_market_session_evidence(rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        raise H024ProspectiveError("H024 market session evidence must be a non-empty list")
    prior_date: str | None = None
    seen_dates: set[str] = set()
    for row in rows:
        required = {
            "session_date",
            "source_url",
            "raw_sha256",
            "symbol_row_status",
            "isin",
            "traded_value_inr",
        }
        if not isinstance(row, dict) or not required.issubset(row):
            raise H024ProspectiveError("H024 market session evidence row is incomplete")
        session_date = str(row["session_date"])
        if session_date in seen_dates:
            raise H024ProspectiveError("duplicate H024 market session evidence date")
        if prior_date is not None and session_date >= prior_date:
            raise H024ProspectiveError(
                "H024 market session evidence must be reverse chronological"
            )
        seen_dates.add(session_date)
        prior_date = session_date
        if not _is_sha256(row["raw_sha256"]):
            raise H024ProspectiveError("H024 market artifact hash is invalid")
        if not isinstance(row["source_url"], str) or not row["source_url"].startswith(
            "https://"
        ):
            raise H024ProspectiveError("H024 market artifact URL is invalid")
        status = row["symbol_row_status"]
        if status not in {"MATCHING_ENTRY_ISIN", "OTHER_ISIN", "MISSING_EQ_ROW"}:
            raise H024ProspectiveError("H024 market session row status is invalid")
        if status == "MISSING_EQ_ROW":
            if row["isin"] is not None or float(row["traded_value_inr"]) != 0.0:
                raise H024ProspectiveError(
                    "H024 missing market row must have null ISIN and zero traded value"
                )
        else:
            if not isinstance(row["isin"], str) or not row["isin"]:
                raise H024ProspectiveError("H024 market row ISIN is invalid")
            value = float(row["traded_value_inr"])
            if not math.isfinite(value) or value < 0:
                raise H024ProspectiveError("H024 traded value is invalid")


def validate_investability_evidence(evidence: dict[str, Any]) -> None:
    required = {
        "status",
        "reason",
        "symbol",
        "planned_entry_session",
        "entry_isin",
        "security_master_source_url",
        "security_master_sha256",
        "security_master_fields",
        "same_isin_prior_session_count",
        "prior_20_median_traded_value_inr",
        "liquidity_floor_inr",
        "market_session_evidence",
        "market_session_evidence_sha256",
    }
    if not isinstance(evidence, dict) or not required.issubset(evidence):
        raise H024ProspectiveError("H024 investability evidence is incomplete")
    status = evidence["status"]
    reason = evidence["reason"]
    if status not in {"ELIGIBLE", "BLOCKED"}:
        raise H024ProspectiveError("H024 investability status is invalid")
    if status == "ELIGIBLE" and reason is not None:
        raise H024ProspectiveError("eligible H024 investability evidence has a reason")
    if status == "BLOCKED" and (not isinstance(reason, str) or not reason):
        raise H024ProspectiveError("blocked H024 investability evidence lacks a reason")
    if not _is_sha256(evidence["security_master_sha256"]):
        raise H024ProspectiveError("H024 security-master hash is invalid")
    if not isinstance(evidence["security_master_source_url"], str) or not evidence[
        "security_master_source_url"
    ].startswith("https://"):
        raise H024ProspectiveError("H024 security-master URL is invalid")
    if not isinstance(evidence["security_master_fields"], dict):
        raise H024ProspectiveError("H024 security-master fields are invalid")
    _validate_market_session_evidence(evidence["market_session_evidence"])
    if evidence["market_session_evidence_sha256"] != canonical_hash(
        evidence["market_session_evidence"]
    ):
        raise H024ProspectiveError("H024 market session evidence digest mismatch")
    count = evidence["same_isin_prior_session_count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise H024ProspectiveError("H024 price-history count is invalid")
    median = evidence["prior_20_median_traded_value_inr"]
    if median is not None and (not math.isfinite(float(median)) or float(median) < 0):
        raise H024ProspectiveError("H024 prior-20 traded-value median is invalid")
    if float(evidence["liquidity_floor_inr"]) != LIQUIDITY_MEDIAN_20D_MIN_INR:
        raise H024ProspectiveError("H024 liquidity floor drifted")


def build_investability_evidence(
    *,
    symbol: str,
    planned_entry_session: str,
    security_master_source_url: str,
    security_master_sha256: str,
    security_master_fields: dict[str, Any] | None,
    prior_sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    clean_symbol = str(symbol).strip().upper()
    if not clean_symbol:
        raise H024ProspectiveError("H024 investability symbol is empty")
    if not _is_sha256(security_master_sha256):
        raise H024ProspectiveError("H024 security-master hash is invalid")

    master_fields = (
        {}
        if security_master_fields is None
        else {str(key): value for key, value in sorted(security_master_fields.items())}
    )
    entry_isin = str(master_fields.get("ISIN") or "").strip() or None
    master_eligible = bool(master_fields) and (
        str(master_fields.get("TckrSymb") or "").strip().upper() == clean_symbol
        and str(master_fields.get("SctySrs") or "").strip().upper() == "EQ"
        and str(master_fields.get("SctyTpFlg") or "").strip().upper() in {"EQ", "0"}
        and entry_isin is not None
        and str(master_fields.get("PrtdToTrad") or "").strip() == "1"
        and str(master_fields.get("SctyStsNrmlMkt") or "").strip()
        in {"1", "2", "4", "5", "6"}
        and str(master_fields.get("ElgbltyNrmlMkt") or "").strip() == "1"
        and str(master_fields.get("DelFlg") or "").strip().upper() in {"", "N"}
        and str(master_fields.get("CallAuctnInd") or "").strip() != "5"
        and str(master_fields.get("Xchg") or "").strip().upper() in {"", "NSE"}
    )

    normalized: list[dict[str, Any]] = []
    same_isin_count = 0
    for row in prior_sessions:
        raw_hash = row.get("raw_sha256")
        if not _is_sha256(raw_hash):
            raise H024ProspectiveError("H024 prior-session raw hash is invalid")
        row_isin_raw = row.get("isin")
        row_isin = None if row_isin_raw is None else str(row_isin_raw).strip()
        if entry_isin and row_isin == entry_isin:
            row_status = "MATCHING_ENTRY_ISIN"
            same_isin_count += 1
            traded_value = float(row.get("traded_value_inr") or 0.0)
        elif row_isin:
            row_status = "OTHER_ISIN"
            traded_value = 0.0
        else:
            row_status = "MISSING_EQ_ROW"
            traded_value = 0.0
        if not math.isfinite(traded_value) or traded_value < 0:
            raise H024ProspectiveError("H024 prior-session traded value is invalid")
        normalized.append(
            {
                "session_date": str(row["session_date"]),
                "source_url": str(row["source_url"]),
                "raw_sha256": raw_hash,
                "symbol_row_status": row_status,
                "isin": row_isin,
                "traded_value_inr": traded_value,
            }
        )
    normalized.sort(key=lambda row: row["session_date"], reverse=True)
    median_20 = (
        statistics.median(float(row["traded_value_inr"]) for row in normalized[:20])
        if len(normalized) >= 20
        else None
    )

    if not master_eligible:
        reason = "SECURITY_MASTER_BLOCKED"
    elif same_isin_count < MIN_PRICE_HISTORY_SESSIONS:
        reason = "INSUFFICIENT_60_SESSION_PRICE_HISTORY"
    elif median_20 is None:
        reason = "MARKET_EVIDENCE_UNRESOLVED"
    elif median_20 < LIQUIDITY_MEDIAN_20D_MIN_INR:
        reason = "LIQUIDITY_BELOW_H004_PRIMARY"
    else:
        reason = None

    evidence = {
        "status": "ELIGIBLE" if reason is None else "BLOCKED",
        "reason": reason,
        "symbol": clean_symbol,
        "planned_entry_session": str(planned_entry_session),
        "entry_isin": entry_isin,
        "security_master_source_url": security_master_source_url,
        "security_master_sha256": security_master_sha256,
        "security_master_fields": master_fields,
        "same_isin_prior_session_count": same_isin_count,
        "prior_20_median_traded_value_inr": median_20,
        "liquidity_floor_inr": LIQUIDITY_MEDIAN_20D_MIN_INR,
        "market_session_evidence": normalized,
        "market_session_evidence_sha256": canonical_hash(normalized),
    }
    validate_investability_evidence(evidence)
    return evidence


def pending_event_keys(
    *, signal_ledger: dict[str, Any], event_ledger: dict[str, Any]
) -> list[tuple[str, str]]:
    validate_signal_ledger(signal_ledger)
    validate_event_ledger(event_ledger)
    existing = {
        (str(row["symbol"]), str(row["planned_entry_session"]))
        for row in event_ledger["records"]
    }
    candidates = {
        (str(row["symbol"]), str(row["planned_entry_session"]))
        for row in signal_ledger["records"]
        if row["status"] == "QUALIFYING"
    }
    return sorted(candidates - existing, key=lambda item: (item[1], item[0]))


def due_event_keys(
    *,
    signal_ledger: dict[str, Any],
    event_ledger: dict[str, Any],
    planned_entry_session: str,
) -> list[tuple[str, str]]:
    return [
        key
        for key in pending_event_keys(signal_ledger=signal_ledger, event_ledger=event_ledger)
        if key[1] == planned_entry_session
    ]


def _candidate_signals(
    signal_ledger: dict[str, Any], *, symbol: str, planned_entry_session: str
) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in signal_ledger["records"]
        if row["status"] == "QUALIFYING"
        and str(row["symbol"]) == symbol
        and str(row["planned_entry_session"]) == planned_entry_session
    ]
    return sorted(
        rows,
        key=lambda row: (
            str(row["exchange_disseminated_at_utc"]),
            str(row["source_id"]),
        ),
    )


def build_event_record(
    *,
    source_ledger: dict[str, Any],
    evidence_ledger: dict[str, Any],
    signal_ledger: dict[str, Any],
    symbol: str,
    planned_entry_session: str,
    investability: dict[str, Any],
    frozen_at_utc: str,
) -> dict[str, Any]:
    validate_source_ledger(source_ledger)
    validate_evidence_ledger(evidence_ledger)
    validate_signal_ledger(signal_ledger)
    validate_investability_evidence(investability)
    clean_symbol = str(symbol).strip().upper()
    candidates = _candidate_signals(
        signal_ledger,
        symbol=clean_symbol,
        planned_entry_session=planned_entry_session,
    )
    if not candidates:
        raise H024ProspectiveError(
            f"{clean_symbol}/{planned_entry_session}: no qualifying H024 source signals"
        )
    entry_opens = {str(row["planned_entry_open_utc"]) for row in candidates}
    if len(entry_opens) != 1:
        raise H024ProspectiveError("H024 event candidates disagree on entry open")
    entry_open_text = next(iter(entry_opens))
    entry_open = _timestamp(entry_open_text, field="event.entry_open")
    frozen = _timestamp(frozen_at_utc, field="event.frozen_at_utc")

    revisions = [
        row
        for row in source_ledger["records"]
        if row["source"]["symbol"] == clean_symbol
        and row["source"]["submission_type"] == "Revision"
    ]
    blocked_ids: list[str] = []
    revision_ids: set[str] = set()
    blockers_by_source: dict[str, list[str]] = {}
    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_time = _timestamp(
            candidate["exchange_disseminated_at_utc"], field="candidate.disseminated"
        )
        blockers = sorted(
            {
                str(row["source"]["source_id"])
                for row in revisions
                if candidate_time
                < _timestamp(
                    row["source"]["exchange_disseminated_at_utc"],
                    field="revision.disseminated",
                )
                < entry_open
                and _timestamp(row["first_seen_at_utc"], field="revision.first_seen")
                <= frozen
            }
        )
        source_id = str(candidate["source_id"])
        if blockers:
            blocked_ids.append(source_id)
            blockers_by_source[source_id] = blockers
            revision_ids.update(blockers)
        else:
            eligible.append(candidate)

    if frozen >= entry_open:
        exclusion_reason: str | None = "LATE_EVENT_FREEZE"
    elif not eligible:
        exclusion_reason = "REVISION_BLOCKED"
    elif investability["status"] != "ELIGIBLE":
        investability_reason = str(investability["reason"])
        exclusion_reason = (
            investability_reason
            if investability_reason in EXCLUSION_REASONS
            else "MARKET_EVIDENCE_UNRESOLVED"
        )
    else:
        exclusion_reason = None

    candidate_ids = sorted(str(row["source_id"]) for row in candidates)
    eligible_ids = sorted(str(row["source_id"]) for row in eligible)
    evidence_rows: list[dict[str, Any]] = []
    for source_id in eligible_ids:
        evidence = evidence_by_source(evidence_ledger, source_id)
        if evidence is None or evidence["status"] != "READY":
            raise H024ProspectiveError(
                f"{source_id}: eligible H024 source is missing READY evidence"
            )
        evidence_rows.append(evidence)

    actor_names = sorted(
        {
            str(name)
            for evidence in evidence_rows
            for name in evidence.get("direct_market_purchase_names", [])
        }
    )
    actor_categories = sorted(
        {
            str(category)
            for evidence in evidence_rows
            for category in evidence.get("direct_market_purchase_categories", [])
        }
    )
    sources = [source_by_id(source_ledger, source_id) for source_id in candidate_ids]
    record: dict[str, Any] = {
        "event_id": event_id(clean_symbol, planned_entry_session),
        "symbol": clean_symbol,
        "planned_entry_session": planned_entry_session,
        "planned_entry_open_utc": entry_open_text,
        "status": PRIMARY_EVENT_STATUS if exclusion_reason is None else EXCLUDED_EVENT_STATUS,
        "exclusion_reason": exclusion_reason,
        "h024_direct_market_purchase": 1 if exclusion_reason is None else 0,
        "candidate_source_ids": candidate_ids,
        "eligible_source_ids": eligible_ids,
        "revision_blocked_source_ids": sorted(blocked_ids),
        "revision_source_ids": sorted(revision_ids),
        "revision_blockers_by_source": {
            key: blockers_by_source[key] for key in sorted(blockers_by_source)
        },
        "app_ids": sorted({str(source["app_id"]) for source in sources}),
        "prev_app_ids": sorted(
            {str(source["prev_app_id"]) for source in sources if str(source["prev_app_id"])}
        ),
        "first_exchange_disseminated_at_utc": min(
            str(row["exchange_disseminated_at_utc"]) for row in candidates
        ),
        "first_repository_observed_at_utc": min(
            source_first_seen(source_ledger, source_id) for source_id in candidate_ids
        ),
        "qualifying_filing_count": len(eligible_ids),
        "qualifying_transaction_count": sum(
            int(evidence["direct_market_purchase_count"]) for evidence in evidence_rows
        ),
        "direct_market_purchase_value_inr": sum(
            float(evidence["direct_market_purchase_value_inr"])
            for evidence in evidence_rows
        ),
        "direct_market_purchase_quantity": sum(
            int(evidence["direct_market_purchase_quantity"]) for evidence in evidence_rows
        ),
        "direct_market_purchase_ownership_delta_pp": sum(
            float(evidence["direct_market_purchase_ownership_delta_pp"])
            for evidence in evidence_rows
        ),
        "direct_market_purchase_actor_count": len(actor_names),
        "direct_market_purchase_categories": actor_categories,
        "direct_market_purchase_names": actor_names,
        "xbrl_sha256s": sorted(
            {
                str(evidence["xbrl_sha256"])
                for evidence in evidence_rows
                if _is_sha256(evidence.get("xbrl_sha256"))
            }
        ),
        "investability": investability,
        "event_frozen_at_utc": _utc_text(frozen),
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    record["event_record_sha256"] = _record_hash(record, "event_record_sha256")
    validate_event_record(record)
    return record


def validate_event_record(record: dict[str, Any]) -> None:
    required = {
        "event_id",
        "symbol",
        "planned_entry_session",
        "planned_entry_open_utc",
        "status",
        "exclusion_reason",
        "h024_direct_market_purchase",
        "candidate_source_ids",
        "eligible_source_ids",
        "revision_blocked_source_ids",
        "revision_source_ids",
        "revision_blockers_by_source",
        "app_ids",
        "prev_app_ids",
        "first_exchange_disseminated_at_utc",
        "first_repository_observed_at_utc",
        "qualifying_filing_count",
        "qualifying_transaction_count",
        "direct_market_purchase_value_inr",
        "direct_market_purchase_quantity",
        "direct_market_purchase_ownership_delta_pp",
        "direct_market_purchase_actor_count",
        "direct_market_purchase_categories",
        "direct_market_purchase_names",
        "xbrl_sha256s",
        "investability",
        "event_frozen_at_utc",
        "outcome_data_attached",
        "live_capital_allowed",
        "event_record_sha256",
    }
    if not isinstance(record, dict) or not required.issubset(record):
        raise H024ProspectiveError("H024 event record is incomplete")
    if record["event_id"] != event_id(
        str(record["symbol"]), str(record["planned_entry_session"])
    ):
        raise H024ProspectiveError("H024 event identity mismatch")
    if record["status"] not in EVENT_STATUSES:
        raise H024ProspectiveError("H024 event status is invalid")
    reason = record["exclusion_reason"]
    if record["status"] == PRIMARY_EVENT_STATUS:
        if reason is not None or record["h024_direct_market_purchase"] != 1:
            raise H024ProspectiveError("H024 primary event status is inconsistent")
        if record["investability"]["status"] != "ELIGIBLE":
            raise H024ProspectiveError("H024 primary event is not investable")
        if not record["eligible_source_ids"]:
            raise H024ProspectiveError("H024 primary event has no eligible source")
    elif reason not in EXCLUSION_REASONS or record["h024_direct_market_purchase"] != 0:
        raise H024ProspectiveError("H024 excluded event status is inconsistent")

    if not isinstance(record["candidate_source_ids"], list) or not record[
        "candidate_source_ids"
    ]:
        raise H024ProspectiveError("H024 event has no candidate sources")
    for field in (
        "candidate_source_ids",
        "eligible_source_ids",
        "revision_blocked_source_ids",
        "revision_source_ids",
        "xbrl_sha256s",
    ):
        values = record[field]
        if not isinstance(values, list) or values != sorted(set(values)):
            raise H024ProspectiveError(f"H024 event {field} is not canonical")
        if any(not _is_sha256(value) for value in values):
            raise H024ProspectiveError(f"H024 event {field} contains invalid hashes")
    eligible = set(record["eligible_source_ids"])
    blocked = set(record["revision_blocked_source_ids"])
    if eligible | blocked != set(record["candidate_source_ids"]):
        raise H024ProspectiveError("H024 event candidate partition is inconsistent")
    if eligible & blocked:
        raise H024ProspectiveError("H024 event candidate partition overlaps")
    for field in (
        "app_ids",
        "prev_app_ids",
        "direct_market_purchase_categories",
        "direct_market_purchase_names",
    ):
        values = record[field]
        if not isinstance(values, list) or values != sorted(set(values)):
            raise H024ProspectiveError(f"H024 event {field} is not canonical")
    blockers = record["revision_blockers_by_source"]
    if not isinstance(blockers, dict) or list(blockers) != sorted(blockers):
        raise H024ProspectiveError("H024 event revision blocker map is not canonical")
    if set(blockers) != blocked:
        raise H024ProspectiveError("H024 event revision blocker map is inconsistent")
    if any(
        not isinstance(values, list)
        or values != sorted(set(values))
        or any(not _is_sha256(value) for value in values)
        for values in blockers.values()
    ):
        raise H024ProspectiveError("H024 event revision blocker values are invalid")
    if record["qualifying_filing_count"] != len(record["eligible_source_ids"]):
        raise H024ProspectiveError("H024 event filing count mismatch")
    if record["direct_market_purchase_actor_count"] != len(
        record["direct_market_purchase_names"]
    ):
        raise H024ProspectiveError("H024 event actor count mismatch")
    if any(
        not math.isfinite(float(record[field]))
        for field in (
            "direct_market_purchase_value_inr",
            "direct_market_purchase_ownership_delta_pp",
        )
    ):
        raise H024ProspectiveError("H024 event numeric evidence is non-finite")
    if (
        not isinstance(record["direct_market_purchase_quantity"], int)
        or record["direct_market_purchase_quantity"] < 0
        or not isinstance(record["qualifying_transaction_count"], int)
        or record["qualifying_transaction_count"] < 0
    ):
        raise H024ProspectiveError("H024 event count/quantity is invalid")

    first_exchange = _timestamp(
        record["first_exchange_disseminated_at_utc"], field="event.first_exchange"
    )
    first_seen = _timestamp(
        record["first_repository_observed_at_utc"], field="event.first_seen"
    )
    frozen = _timestamp(record["event_frozen_at_utc"], field="event.frozen")
    entry_open = _timestamp(record["planned_entry_open_utc"], field="event.entry_open")
    if first_seen < first_exchange:
        raise H024ProspectiveError("H024 event first-seen precedes dissemination")
    if reason != "LATE_EVENT_FREEZE" and frozen >= entry_open:
        raise H024ProspectiveError("H024 timely event was frozen at/after entry open")
    if reason == "LATE_EVENT_FREEZE" and frozen < entry_open:
        raise H024ProspectiveError("H024 late event was frozen before entry open")
    validate_investability_evidence(record["investability"])
    if record["outcome_data_attached"] is not False or record["live_capital_allowed"] is not False:
        raise H024ProspectiveError("H024 event attached prohibited outcome/capital state")
    if record["event_record_sha256"] != _record_hash(record, "event_record_sha256"):
        raise H024ProspectiveError("H024 event record digest mismatch")


def validate_event_ledger(ledger: dict[str, Any]) -> None:
    if not isinstance(ledger, dict):
        raise TypeError("H024 event ledger must be an object")
    if (
        ledger.get("schema_version") != EVENT_LEDGER_VERSION
        or ledger.get("protocol_id") != PROTOCOL_ID
    ):
        raise H024ProspectiveError("H024 event ledger header is invalid")
    if not isinstance(ledger.get("records"), list):
        raise H024ProspectiveError("H024 event ledger records must be a list")
    if ledger.get("record_count") != len(ledger["records"]):
        raise H024ProspectiveError("H024 event ledger record count mismatch")
    if ledger.get("ledger_sha256") != _ledger_hash(ledger):
        raise H024ProspectiveError("H024 event ledger digest mismatch")
    seen: set[str] = set()
    prior_key: tuple[str, str] | None = None
    for record in ledger["records"]:
        validate_event_record(record)
        identity = str(record["event_id"])
        if identity in seen:
            raise H024ProspectiveError("duplicate H024 event")
        seen.add(identity)
        key = (str(record["planned_entry_session"]), str(record["symbol"]))
        if prior_key is not None and key < prior_key:
            raise H024ProspectiveError("H024 event ledger is not canonical-sorted")
        prior_key = key


def append_event(ledger: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    validate_event_ledger(ledger)
    validate_event_record(record)
    identity = str(record["event_id"])
    existing = [row for row in ledger["records"] if row["event_id"] == identity]
    if existing:
        if existing[0] != record:
            raise H024ProspectiveError(f"{identity}: H024 event is immutable")
        return ledger
    records = [dict(row) for row in ledger["records"]] + [record]
    records.sort(key=lambda row: (str(row["planned_entry_session"]), str(row["symbol"])))
    result = dict(ledger)
    result["records"] = records
    result["record_count"] = len(records)
    result["ledger_sha256"] = _ledger_hash(result)
    validate_event_ledger(result)
    return result
