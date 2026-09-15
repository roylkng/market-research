from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.h024_acquisition import SOURCE_CONTRACT_ID, canonical_hash

PROTOCOL_ID = "H024-DIRECT-INSIDER-MARKET-PURCHASE-V1"
PROSPECTIVE_START_UTC = datetime(2026, 9, 15, 18, 30, tzinfo=UTC)
CALENDAR_PATH = "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json"
IST = ZoneInfo("Asia/Kolkata")
SOURCE_LEDGER_VERSION = 1
EVIDENCE_LEDGER_VERSION = 1
SIGNAL_LEDGER_VERSION = 1
SCAN_LEDGER_VERSION = 1


class H024ProspectiveError(ValueError):
    """Raised when H024 prospective state cannot advance without guessing."""


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


def _ledger_hash(ledger: dict[str, Any]) -> str:
    return canonical_hash({key: value for key, value in ledger.items() if key != "ledger_sha256"})


def _record_hash(record: dict[str, Any], field: str) -> str:
    return canonical_hash({key: value for key, value in record.items() if key != field})


def new_source_ledger() -> dict[str, Any]:
    ledger = {
        "schema_version": SOURCE_LEDGER_VERSION,
        "protocol_id": PROTOCOL_ID,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def new_evidence_ledger() -> dict[str, Any]:
    ledger = {
        "schema_version": EVIDENCE_LEDGER_VERSION,
        "protocol_id": PROTOCOL_ID,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def new_signal_ledger() -> dict[str, Any]:
    ledger = {
        "schema_version": SIGNAL_LEDGER_VERSION,
        "protocol_id": PROTOCOL_ID,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def new_scan_ledger() -> dict[str, Any]:
    ledger = {
        "schema_version": SCAN_LEDGER_VERSION,
        "protocol_id": PROTOCOL_ID,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_source(source: dict[str, Any]) -> None:
    required = {
        "source_id",
        "symbol",
        "company_name",
        "app_id",
        "prev_app_id",
        "submission_type",
        "revision_remark",
        "broadcast_at_utc",
        "exchange_disseminated_at_utc",
        "xml_url",
        "ixbrl_url",
        "discovery_row_sha256",
    }
    if not isinstance(source, dict) or not required.issubset(source):
        raise H024ProspectiveError("H024 source fields are incomplete")
    symbol = str(source["symbol"]).strip().upper()
    app_id = str(source["app_id"]).strip()
    submission_type = str(source["submission_type"])
    if not symbol or not app_id or submission_type not in {"Original", "Revision"}:
        raise H024ProspectiveError("H024 source identity is invalid")
    broadcast = _timestamp(source["broadcast_at_utc"], field="source.broadcast_at_utc")
    disseminated = _timestamp(
        source["exchange_disseminated_at_utc"], field="source.exchange_disseminated_at_utc"
    )
    if disseminated < broadcast:
        raise H024ProspectiveError("H024 exchange dissemination precedes broadcast")
    if not _is_sha256(source["discovery_row_sha256"]):
        raise H024ProspectiveError("H024 discovery row SHA-256 is invalid")
    expected_id = canonical_hash(
        {
            "source_contract_id": SOURCE_CONTRACT_ID,
            "symbol": symbol,
            "app_id": app_id,
            "submission_type": submission_type,
            "exchange_disseminated_at_utc": _utc_text(disseminated),
            "xml_url": str(source["xml_url"]),
        }
    )
    if source["source_id"] != expected_id:
        raise H024ProspectiveError("H024 source identity digest mismatch")


def validate_source_ledger(ledger: dict[str, Any]) -> None:
    _validate_ledger_header(ledger, SOURCE_LEDGER_VERSION, "source")
    seen_ids: set[str] = set()
    seen_app_ids: dict[tuple[str, str], str] = {}
    prior_key: tuple[str, str, str] | None = None
    for row in ledger["records"]:
        if not isinstance(row, dict) or not {"source", "first_seen_at_utc", "source_record_sha256"}.issubset(row):
            raise H024ProspectiveError("invalid H024 source ledger record")
        validate_source(row["source"])
        source = row["source"]
        source_id = str(source["source_id"])
        if source_id in seen_ids:
            raise H024ProspectiveError("duplicate H024 source id")
        seen_ids.add(source_id)
        key = (str(source["symbol"]), str(source["app_id"]))
        prior_id = seen_app_ids.get(key)
        if prior_id is not None and prior_id != source_id:
            raise H024ProspectiveError(f"{key[0]}/{key[1]}: H024 appId identity drift")
        seen_app_ids[key] = source_id
        first_seen = _timestamp(row["first_seen_at_utc"], field="source.first_seen_at_utc")
        disseminated = _timestamp(
            source["exchange_disseminated_at_utc"], field="source.exchange_disseminated_at_utc"
        )
        if first_seen < disseminated:
            raise H024ProspectiveError("H024 source first-seen precedes exchange dissemination")
        if row["source_record_sha256"] != _record_hash(row, "source_record_sha256"):
            raise H024ProspectiveError("H024 source record digest mismatch")
        sort_key = (
            str(source["exchange_disseminated_at_utc"]),
            str(source["symbol"]),
            source_id,
        )
        if prior_key is not None and sort_key < prior_key:
            raise H024ProspectiveError("H024 source ledger records are not canonical-sorted")
        prior_key = sort_key


def append_sources(
    ledger: dict[str, Any],
    sources: list[dict[str, Any]],
    *,
    first_seen_at_utc: str,
) -> dict[str, Any]:
    validate_source_ledger(ledger)
    first_seen = _timestamp(first_seen_at_utc, field="first_seen_at_utc")
    existing_ids = {str(row["source"]["source_id"]) for row in ledger["records"]}
    existing_by_app = {
        (str(row["source"]["symbol"]), str(row["source"]["app_id"])): str(
            row["source"]["source_id"]
        )
        for row in ledger["records"]
    }
    records = [dict(row) for row in ledger["records"]]
    for source in sources:
        validate_source(source)
        source_id = str(source["source_id"])
        if source_id in existing_ids:
            continue
        key = (str(source["symbol"]), str(source["app_id"]))
        prior_id = existing_by_app.get(key)
        if prior_id is not None and prior_id != source_id:
            raise H024ProspectiveError(f"{key[0]}/{key[1]}: H024 appId identity drift")
        disseminated = _timestamp(
            source["exchange_disseminated_at_utc"], field="source.exchange_disseminated_at_utc"
        )
        if first_seen < disseminated:
            raise H024ProspectiveError(f"{source_id}: first-seen precedes dissemination")
        row = {"source": source, "first_seen_at_utc": _utc_text(first_seen)}
        row["source_record_sha256"] = _record_hash(row, "source_record_sha256")
        records.append(row)
        existing_ids.add(source_id)
        existing_by_app[key] = source_id
    records.sort(
        key=lambda row: (
            str(row["source"]["exchange_disseminated_at_utc"]),
            str(row["source"]["symbol"]),
            str(row["source"]["source_id"]),
        )
    )
    result = dict(ledger)
    result["records"] = records
    result["record_count"] = len(records)
    result["ledger_sha256"] = _ledger_hash(result)
    validate_source_ledger(result)
    return result


def source_first_seen(ledger: dict[str, Any], source_id: str) -> str:
    validate_source_ledger(ledger)
    matches = [row for row in ledger["records"] if row["source"]["source_id"] == source_id]
    if len(matches) != 1:
        raise H024ProspectiveError(f"source not uniquely present in H024 ledger: {source_id}")
    return str(matches[0]["first_seen_at_utc"])


def source_by_id(ledger: dict[str, Any], source_id: str) -> dict[str, Any]:
    validate_source_ledger(ledger)
    matches = [row["source"] for row in ledger["records"] if row["source"]["source_id"] == source_id]
    if len(matches) != 1:
        raise H024ProspectiveError(f"source not uniquely present in H024 ledger: {source_id}")
    return dict(matches[0])


def _validate_evidence(evidence: dict[str, Any]) -> None:
    if not isinstance(evidence, dict):
        raise H024ProspectiveError("H024 evidence must be an object")
    status = evidence.get("status")
    if status not in {"READY", "PARSE_BLOCKED"}:
        raise H024ProspectiveError(f"unsupported H024 evidence status: {status}")
    if not _is_sha256(evidence.get("source_id")) or not _is_sha256(evidence.get("xbrl_sha256")):
        raise H024ProspectiveError("H024 evidence identity/hash is invalid")
    if status == "READY":
        count = evidence.get("direct_market_purchase_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise H024ProspectiveError("H024 direct purchase count is invalid")
        for field in (
            "direct_market_purchase_value_inr",
            "direct_market_purchase_ownership_delta_pp",
        ):
            try:
                value = float(evidence[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise H024ProspectiveError(f"invalid H024 evidence field: {field}") from exc
            if not math.isfinite(value):
                raise H024ProspectiveError(f"non-finite H024 evidence field: {field}")


def validate_evidence_ledger(ledger: dict[str, Any]) -> None:
    _validate_ledger_header(ledger, EVIDENCE_LEDGER_VERSION, "evidence")
    seen: set[str] = set()
    for row in ledger["records"]:
        if not isinstance(row, dict) or not {"evidence", "evidence_frozen_at_utc", "evidence_record_sha256"}.issubset(row):
            raise H024ProspectiveError("invalid H024 evidence ledger record")
        _validate_evidence(row["evidence"])
        source_id = str(row["evidence"]["source_id"])
        if source_id in seen:
            raise H024ProspectiveError("duplicate H024 evidence for source")
        seen.add(source_id)
        _timestamp(row["evidence_frozen_at_utc"], field="evidence_frozen_at_utc")
        if row["evidence_record_sha256"] != _record_hash(row, "evidence_record_sha256"):
            raise H024ProspectiveError("H024 evidence record digest mismatch")


def evidence_record_by_source(ledger: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    validate_evidence_ledger(ledger)
    matches = [row for row in ledger["records"] if row["evidence"]["source_id"] == source_id]
    if not matches:
        return None
    if len(matches) != 1:
        raise H024ProspectiveError("H024 source has duplicate evidence")
    return dict(matches[0])


def evidence_by_source(ledger: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    record = evidence_record_by_source(ledger, source_id)
    return None if record is None else dict(record["evidence"])


def append_evidence(
    ledger: dict[str, Any],
    source_ledger: dict[str, Any],
    evidence: dict[str, Any],
    *,
    frozen_at_utc: str,
) -> dict[str, Any]:
    validate_evidence_ledger(ledger)
    validate_source_ledger(source_ledger)
    _validate_evidence(evidence)
    source_id = str(evidence["source_id"])
    source_by_id(source_ledger, source_id)
    frozen = _timestamp(frozen_at_utc, field="evidence_frozen_at_utc")
    existing = [row for row in ledger["records"] if row["evidence"]["source_id"] == source_id]
    if existing:
        if existing[0]["evidence"] != evidence:
            raise H024ProspectiveError(f"{source_id}: H024 evidence is immutable")
        return ledger
    row = {"evidence": evidence, "evidence_frozen_at_utc": _utc_text(frozen)}
    row["evidence_record_sha256"] = _record_hash(row, "evidence_record_sha256")
    records = [dict(item) for item in ledger["records"]] + [row]
    records.sort(key=lambda item: str(item["evidence"]["source_id"]))
    result = dict(ledger)
    result["records"] = records
    result["record_count"] = len(records)
    result["ledger_sha256"] = _ledger_hash(result)
    validate_evidence_ledger(result)
    return result


def validate_calendar(calendar: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(calendar, dict) or not isinstance(calendar.get("sessions"), list):
        raise H024ProspectiveError("H024 calendar snapshot is invalid")
    sessions: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    prior_open: datetime | None = None
    for row in calendar["sessions"]:
        if not isinstance(row, dict) or not {"session_date", "open_timestamp_utc", "close_timestamp_utc"}.issubset(row):
            raise H024ProspectiveError("H024 calendar session is invalid")
        session_date = str(row["session_date"])
        opened = _timestamp(row["open_timestamp_utc"], field="calendar.open_timestamp_utc")
        closed = _timestamp(row["close_timestamp_utc"], field="calendar.close_timestamp_utc")
        if opened >= closed or session_date in seen_dates:
            raise H024ProspectiveError("H024 calendar session is invalid/duplicate")
        if prior_open is not None and opened <= prior_open:
            raise H024ProspectiveError("H024 calendar sessions are not strictly increasing")
        seen_dates.add(session_date)
        prior_open = opened
        sessions.append(
            {
                "session_date": session_date,
                "open_timestamp_utc": _utc_text(opened),
                "close_timestamp_utc": _utc_text(closed),
            }
        )
    return sessions


def planned_entry_session(calendar: dict[str, Any], exchange_time_utc: str) -> dict[str, Any]:
    disseminated = _timestamp(exchange_time_utc, field="exchange_time_utc")
    local_date = disseminated.astimezone(IST).date().isoformat()
    for session in validate_calendar(calendar):
        if session["session_date"] > local_date:
            return dict(session)
    raise H024ProspectiveError("H024 calendar does not cover the next entry session")


def build_signal_record(
    *,
    source_ledger: dict[str, Any],
    evidence_ledger: dict[str, Any],
    calendar: dict[str, Any],
    source_id: str,
    frozen_at_utc: str,
) -> dict[str, Any] | None:
    source = source_by_id(source_ledger, source_id)
    evidence_record = evidence_record_by_source(evidence_ledger, source_id)
    if evidence_record is None or evidence_record["evidence"]["status"] != "READY":
        return None
    evidence = evidence_record["evidence"]
    if source["submission_type"] != "Original":
        return None
    if int(evidence["direct_market_purchase_count"]) < 1:
        return None
    disseminated = _timestamp(
        source["exchange_disseminated_at_utc"], field="source.exchange_disseminated_at_utc"
    )
    if disseminated < PROSPECTIVE_START_UTC:
        return None
    first_seen = _timestamp(
        source_first_seen(source_ledger, source_id), field="source_first_seen_at_utc"
    )
    evidence_frozen = _timestamp(
        evidence_record["evidence_frozen_at_utc"], field="evidence_frozen_at_utc"
    )
    frozen = _timestamp(frozen_at_utc, field="signal_frozen_at_utc")
    if evidence_frozen < first_seen:
        raise H024ProspectiveError("H024 evidence freeze precedes source first-seen")
    if frozen < evidence_frozen:
        raise H024ProspectiveError("H024 signal freeze precedes raw-XBRL evidence freeze")
    entry = planned_entry_session(calendar, str(source["exchange_disseminated_at_utc"]))
    entry_open = _timestamp(entry["open_timestamp_utc"], field="entry.open_timestamp_utc")
    status = (
        "QUALIFYING"
        if first_seen <= entry_open and evidence_frozen <= entry_open and frozen <= entry_open
        else "LATE_SIGNAL_FREEZE"
    )
    signal_id = canonical_hash({"protocol_id": PROTOCOL_ID, "source_id": source_id})
    record: dict[str, Any] = {
        "signal_id": signal_id,
        "source_id": source_id,
        "symbol": source["symbol"],
        "status": status,
        "exchange_disseminated_at_utc": _utc_text(disseminated),
        "source_first_seen_at_utc": _utc_text(first_seen),
        "evidence_frozen_at_utc": _utc_text(evidence_frozen),
        "signal_frozen_at_utc": _utc_text(frozen),
        "planned_entry_session": entry["session_date"],
        "planned_entry_open_utc": entry["open_timestamp_utc"],
        "direct_market_purchase_count": evidence["direct_market_purchase_count"],
        "direct_market_purchase_value_inr": evidence["direct_market_purchase_value_inr"],
        "direct_market_purchase_quantity": evidence["direct_market_purchase_quantity"],
        "direct_market_purchase_ownership_delta_pp": evidence[
            "direct_market_purchase_ownership_delta_pp"
        ],
        "direct_market_purchase_actor_count": evidence["direct_market_purchase_actor_count"],
        "xbrl_sha256": evidence["xbrl_sha256"],
    }
    record["signal_record_sha256"] = _record_hash(record, "signal_record_sha256")
    validate_signal_record(record)
    return record


def validate_signal_record(record: dict[str, Any]) -> None:
    required = {
        "signal_id",
        "source_id",
        "symbol",
        "status",
        "exchange_disseminated_at_utc",
        "source_first_seen_at_utc",
        "evidence_frozen_at_utc",
        "signal_frozen_at_utc",
        "planned_entry_session",
        "planned_entry_open_utc",
        "direct_market_purchase_count",
        "direct_market_purchase_value_inr",
        "direct_market_purchase_quantity",
        "direct_market_purchase_ownership_delta_pp",
        "direct_market_purchase_actor_count",
        "xbrl_sha256",
        "signal_record_sha256",
    }
    if not isinstance(record, dict) or not required.issubset(record):
        raise H024ProspectiveError("H024 signal record is incomplete")
    if record["status"] not in {"QUALIFYING", "LATE_SIGNAL_FREEZE"}:
        raise H024ProspectiveError("H024 signal status is invalid")
    if not _is_sha256(record["signal_id"]) or not _is_sha256(record["source_id"]) or not _is_sha256(record["xbrl_sha256"]):
        raise H024ProspectiveError("H024 signal identity/hash is invalid")
    disseminated = _timestamp(record["exchange_disseminated_at_utc"], field="signal.exchange")
    first_seen = _timestamp(record["source_first_seen_at_utc"], field="signal.first_seen")
    evidence_frozen = _timestamp(
        record["evidence_frozen_at_utc"], field="signal.evidence_frozen"
    )
    frozen = _timestamp(record["signal_frozen_at_utc"], field="signal.frozen")
    entry = _timestamp(record["planned_entry_open_utc"], field="signal.entry_open")
    if (
        first_seen < disseminated
        or evidence_frozen < first_seen
        or frozen < evidence_frozen
    ):
        raise H024ProspectiveError("H024 signal timestamps are inconsistent")
    expected_status = (
        "QUALIFYING"
        if first_seen <= entry and evidence_frozen <= entry and frozen <= entry
        else "LATE_SIGNAL_FREEZE"
    )
    if record["status"] != expected_status:
        raise H024ProspectiveError("H024 signal late-freeze status is inconsistent")
    if record["signal_record_sha256"] != _record_hash(record, "signal_record_sha256"):
        raise H024ProspectiveError("H024 signal record digest mismatch")


def validate_signal_ledger(ledger: dict[str, Any]) -> None:
    _validate_ledger_header(ledger, SIGNAL_LEDGER_VERSION, "signal")
    seen_source_ids: set[str] = set()
    for record in ledger["records"]:
        validate_signal_record(record)
        source_id = str(record["source_id"])
        if source_id in seen_source_ids:
            raise H024ProspectiveError("duplicate H024 signal source")
        seen_source_ids.add(source_id)


def append_signal(ledger: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    validate_signal_ledger(ledger)
    validate_signal_record(record)
    source_id = str(record["source_id"])
    existing = [item for item in ledger["records"] if item["source_id"] == source_id]
    if existing:
        if existing[0] != record:
            raise H024ProspectiveError(f"{source_id}: H024 signal is immutable")
        return ledger
    records = [dict(item) for item in ledger["records"]] + [record]
    records.sort(
        key=lambda item: (
            str(item["exchange_disseminated_at_utc"]),
            str(item["symbol"]),
            str(item["source_id"]),
        )
    )
    result = dict(ledger)
    result["records"] = records
    result["record_count"] = len(records)
    result["ledger_sha256"] = _ledger_hash(result)
    validate_signal_ledger(result)
    return result


def signal_exists(ledger: dict[str, Any], source_id: str) -> bool:
    validate_signal_ledger(ledger)
    return any(record["source_id"] == source_id for record in ledger["records"])


def build_scan_record(
    *,
    scanned_at_utc: str,
    window_start: str,
    window_end: str,
    discovery_raw_sha256: str,
    source_ids: list[str],
) -> dict[str, Any]:
    scanned = _timestamp(scanned_at_utc, field="scanned_at_utc")
    if not _is_sha256(discovery_raw_sha256) or any(not _is_sha256(value) for value in source_ids):
        raise H024ProspectiveError("H024 scan hashes are invalid")
    payload = {
        "scanned_at_utc": _utc_text(scanned),
        "window_start": window_start,
        "window_end": window_end,
        "discovery_raw_sha256": discovery_raw_sha256,
        "source_ids": sorted(set(source_ids)),
    }
    record = {"scan_id": canonical_hash({"protocol_id": PROTOCOL_ID, **payload}), **payload}
    record["scan_record_sha256"] = _record_hash(record, "scan_record_sha256")
    return record


def validate_scan_ledger(ledger: dict[str, Any]) -> None:
    _validate_ledger_header(ledger, SCAN_LEDGER_VERSION, "scan")
    seen: set[str] = set()
    prior_time: datetime | None = None
    for record in ledger["records"]:
        required = {
            "scan_id",
            "scanned_at_utc",
            "window_start",
            "window_end",
            "discovery_raw_sha256",
            "source_ids",
            "scan_record_sha256",
        }
        if not isinstance(record, dict) or not required.issubset(record):
            raise H024ProspectiveError("invalid H024 scan record")
        if not _is_sha256(record["scan_id"]) or record["scan_id"] in seen:
            raise H024ProspectiveError("invalid/duplicate H024 scan id")
        seen.add(str(record["scan_id"]))
        scanned = _timestamp(record["scanned_at_utc"], field="scan.scanned_at_utc")
        if prior_time is not None and scanned < prior_time:
            raise H024ProspectiveError("H024 scan ledger time regressed")
        prior_time = scanned
        if not _is_sha256(record["discovery_raw_sha256"]):
            raise H024ProspectiveError("H024 scan raw hash is invalid")
        if not isinstance(record["source_ids"], list) or any(
            not _is_sha256(value) for value in record["source_ids"]
        ):
            raise H024ProspectiveError("H024 scan source ids are invalid")
        if record["source_ids"] != sorted(set(record["source_ids"])):
            raise H024ProspectiveError("H024 scan source ids are not canonical")
        if record["scan_record_sha256"] != _record_hash(record, "scan_record_sha256"):
            raise H024ProspectiveError("H024 scan record digest mismatch")


def append_scan(ledger: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    validate_scan_ledger(ledger)
    records = [dict(item) for item in ledger["records"]] + [record]
    result = dict(ledger)
    result["records"] = records
    result["record_count"] = len(records)
    result["ledger_sha256"] = _ledger_hash(result)
    validate_scan_ledger(result)
    return result


def _validate_ledger_header(ledger: dict[str, Any], version: int, kind: str) -> None:
    if not isinstance(ledger, dict):
        raise TypeError(f"H024 {kind} ledger must be an object")
    if ledger.get("schema_version") != version or ledger.get("protocol_id") != PROTOCOL_ID:
        raise H024ProspectiveError(f"H024 {kind} ledger header is invalid")
    if not isinstance(ledger.get("records"), list):
        raise H024ProspectiveError(f"H024 {kind} ledger records must be a list")
    if ledger.get("record_count") != len(ledger["records"]):
        raise H024ProspectiveError(f"H024 {kind} ledger record count mismatch")
    if ledger.get("ledger_sha256") != _ledger_hash(ledger):
        raise H024ProspectiveError(f"H024 {kind} ledger digest mismatch")


def dump_json(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
