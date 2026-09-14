from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from typing import Any

from marketlab.h023_ownership import previous_quarter_end

HYPOTHESIS_ID = "H023"
PROTOCOL_ID = "H023-MF-OWNERSHIP-ACCUMULATION-V1"
SOURCE_CONTRACT_ID = "H023-NSE-SHAREHOLDING-XBRL-V1"
COHORT_ID = "FY27-Q2-2026-09-06"
COHORT_PATH = "research/prospective/universes/FY27-Q2-2026-09-06.json"
COHORT_BLOB_SHA = "8026e81faee3e913d2fba1dba72d60603b69fa07"
PROSPECTIVE_START_UTC = datetime(2026, 9, 14, 18, 30, tzinfo=UTC)
SOURCE_LEDGER_VERSION = 1
EVENT_LEDGER_VERSION = 1
SCAN_LEDGER_VERSION = 1


class H023ProspectiveError(ValueError):
    """Raised when the H023 prospective stream cannot advance without guessing."""


class RetroactiveSourceGap(H023ProspectiveError):
    """A newly discovered older filing invalidates already sealed event context."""


def canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise H023ProspectiveError("H023 canonical payload must contain finite JSON") from exc
    return hashlib.sha256(raw).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
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


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise H023ProspectiveError("timestamp must include timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def validate_universe_snapshot(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, dict):
        raise TypeError("H023 universe snapshot must be an object")
    if snapshot.get("cohort_id") != COHORT_ID:
        raise H023ProspectiveError("H023 frozen cohort id changed")
    members = snapshot.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise H023ProspectiveError("H023 requires the frozen 100-name U001 universe")
    result: dict[str, dict[str, Any]] = {}
    for row in members:
        if not isinstance(row, dict):
            raise TypeError("H023 universe member must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        if not symbol or not isin or symbol in result:
            raise H023ProspectiveError(f"invalid/duplicate H023 universe member: {symbol}")
        result[symbol] = {"symbol": symbol, "isin": isin}
    return result


def _source_identity_payload(source: dict[str, Any]) -> dict[str, str]:
    return {
        "source_contract_id": SOURCE_CONTRACT_ID,
        "symbol": str(source["symbol"]).strip().upper(),
        "record_id": str(source["record_id"]),
        "report_date": str(source["report_date"]),
        "broadcast_at_utc": str(source["broadcast_at_utc"]),
        "xbrl_url": str(source["xbrl_url"]),
        "master_row_sha256": str(source["master_row_sha256"]),
    }


def validate_source(source: dict[str, Any]) -> None:
    if not isinstance(source, dict):
        raise TypeError("H023 source must be an object")
    required = {
        "source_id",
        "symbol",
        "record_id",
        "report_date",
        "broadcast_at_utc",
        "xbrl_url",
        "master_row_sha256",
    }
    if not required.issubset(source):
        raise H023ProspectiveError("H023 source identity fields are incomplete")
    symbol = str(source.get("symbol") or "").strip().upper()
    record_id = str(source.get("record_id") or "").strip()
    report_date = str(source.get("report_date") or "")
    source_id = str(source.get("source_id") or "")
    if not symbol or not record_id:
        raise H023ProspectiveError("H023 source symbol/record id is empty")
    previous_quarter_end(report_date)
    _timestamp(source.get("broadcast_at_utc"), field=f"{source_id}.broadcast_at_utc")
    url = str(source.get("xbrl_url") or "")
    if not (
        url.startswith(("https://nsearchives.nseindia.com/", "https://archives.nseindia.com/"))
    ):
        raise H023ProspectiveError(f"{source_id}: XBRL URL is not an approved NSE archive")
    if not _is_sha256(source.get("master_row_sha256")):
        raise H023ProspectiveError(f"{source_id}: master row digest is invalid")
    if not _is_sha256(source_id) or source_id != canonical_hash(_source_identity_payload(source)):
        raise H023ProspectiveError(f"{source_id}: source identity hash mismatch")


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = dict(ledger)
    unsigned.pop("ledger_sha256", None)
    return canonical_hash(unsigned)


def _base_ledger(*, version: int, ledger_type: str) -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": version,
        "ledger_type": ledger_type,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "source_contract_id": SOURCE_CONTRACT_ID,
        "cohort_id": COHORT_ID,
        "cohort_path": COHORT_PATH,
        "cohort_blob_sha": COHORT_BLOB_SHA,
        "prospective_start_utc": _utc_text(PROSPECTIVE_START_UTC),
        "outcome_data_attached": False,
        "live_capital_allowed": False,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def new_source_ledger() -> dict[str, Any]:
    return _base_ledger(version=SOURCE_LEDGER_VERSION, ledger_type="H023_SOURCE_LEDGER")


def new_event_ledger() -> dict[str, Any]:
    return _base_ledger(version=EVENT_LEDGER_VERSION, ledger_type="H023_EVENT_LEDGER")


def new_scan_ledger() -> dict[str, Any]:
    return _base_ledger(version=SCAN_LEDGER_VERSION, ledger_type="H023_SCAN_LEDGER")


def _validate_base_ledger(
    ledger: dict[str, Any], *, version: int, ledger_type: str
) -> list[dict[str, Any]]:
    if not isinstance(ledger, dict):
        raise TypeError(f"{ledger_type} must be an object")
    if ledger.get("ledger_sha256") != _ledger_hash(ledger):
        raise H023ProspectiveError(f"{ledger_type} digest mismatch")
    expected = {
        "schema_version": version,
        "ledger_type": ledger_type,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "source_contract_id": SOURCE_CONTRACT_ID,
        "cohort_id": COHORT_ID,
        "cohort_path": COHORT_PATH,
        "cohort_blob_sha": COHORT_BLOB_SHA,
        "prospective_start_utc": _utc_text(PROSPECTIVE_START_UTC),
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    for field, value in expected.items():
        if ledger.get(field) != value:
            raise H023ProspectiveError(f"{ledger_type} frozen field changed: {field}")
    records = ledger.get("records")
    if not isinstance(records, list) or ledger.get("record_count") != len(records):
        raise H023ProspectiveError(f"{ledger_type} record count mismatch")
    return records


def validate_source_ledger(ledger: dict[str, Any]) -> None:
    records = _validate_base_ledger(
        ledger, version=SOURCE_LEDGER_VERSION, ledger_type="H023_SOURCE_LEDGER"
    )
    seen_ids: set[str] = set()
    seen_record_keys: dict[tuple[str, str], str] = {}
    prior_sort: tuple[str, str, str, str] | None = None
    for row in records:
        if not isinstance(row, dict):
            raise TypeError("H023 source-ledger record must be an object")
        source = row.get("source")
        if not isinstance(source, dict):
            raise H023ProspectiveError("H023 source-ledger record lacks source")
        validate_source(source)
        source_id = str(source["source_id"])
        if source_id in seen_ids:
            raise H023ProspectiveError(f"duplicate H023 source: {source_id}")
        seen_ids.add(source_id)
        key = (str(source["symbol"]), str(source["record_id"]))
        prior_id = seen_record_keys.get(key)
        if prior_id is not None and prior_id != source_id:
            raise H023ProspectiveError(
                f"{key[0]}/{key[1]}: official source identity drift detected"
            )
        seen_record_keys[key] = source_id
        first_seen = _timestamp(
            row.get("first_seen_at_utc"), field=f"{source_id}.first_seen_at_utc"
        )
        broadcast = _timestamp(
            source["broadcast_at_utc"], field=f"{source_id}.broadcast_at_utc"
        )
        if first_seen < broadcast:
            raise H023ProspectiveError(f"{source_id}: first-seen precedes NSE broadcast")
        if row.get("source_record_sha256") != canonical_hash(
            {"source": source, "first_seen_at_utc": _utc_text(first_seen)}
        ):
            raise H023ProspectiveError(f"{source_id}: source-ledger record digest mismatch")
        sort_key = (
            str(source["broadcast_at_utc"]),
            str(source["symbol"]),
            str(source["report_date"]),
            source_id,
        )
        if prior_sort is not None and sort_key < prior_sort:
            raise H023ProspectiveError("H023 source ledger is not canonical-sorted")
        prior_sort = sort_key


def _event_hash(record: dict[str, Any]) -> str:
    unsigned = dict(record)
    unsigned.pop("record_sha256", None)
    return canonical_hash(unsigned)


def validate_event_record(record: dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise TypeError("H023 event record must be an object")
    required = {
        "event_id",
        "symbol",
        "report_date",
        "status",
        "current_source",
        "prior_source",
        "current_xbrl_sha256",
        "prior_xbrl_sha256",
        "current_mutual_fund_percentage",
        "prior_mutual_fund_percentage",
        "mf_ownership_delta_pp",
        "source_first_seen_at_utc",
        "signal_frozen_at_utc",
        "record_sha256",
    }
    if not required.issubset(record):
        raise H023ProspectiveError("H023 event record fields are incomplete")
    symbol = str(record.get("symbol") or "").strip().upper()
    report_date = str(record.get("report_date") or "")
    event_id = canonical_hash(
        {"protocol_id": PROTOCOL_ID, "symbol": symbol, "report_date": report_date}
    )
    if record.get("event_id") != event_id:
        raise H023ProspectiveError(f"{symbol}/{report_date}: event id mismatch")
    current = record.get("current_source")
    if not isinstance(current, dict):
        raise H023ProspectiveError(f"{event_id}: current source is missing")
    validate_source(current)
    if current["symbol"] != symbol or current["report_date"] != report_date:
        raise H023ProspectiveError(f"{event_id}: current source identity mismatch")
    if _timestamp(current["broadcast_at_utc"], field="current.broadcast") < PROSPECTIVE_START_UTC:
        raise H023ProspectiveError(f"{event_id}: primary current source is pre-boundary")
    first_seen = _timestamp(
        record.get("source_first_seen_at_utc"), field=f"{event_id}.source_first_seen"
    )
    frozen = _timestamp(
        record.get("signal_frozen_at_utc"), field=f"{event_id}.signal_frozen"
    )
    current_broadcast = _timestamp(current["broadcast_at_utc"], field="current.broadcast")
    if first_seen < current_broadcast or frozen < first_seen:
        raise H023ProspectiveError(f"{event_id}: impossible first-seen/freeze ordering")
    status = record.get("status")
    allowed = {
        "SIGNAL",
        "SOURCE_BLOCKED",
        "NO_SIGNAL_PRIOR_UNAVAILABLE",
        "PRIOR_SOURCE_BLOCKED",
    }
    if status not in allowed:
        raise H023ProspectiveError(f"{event_id}: invalid event status {status}")
    prior = record.get("prior_source")
    if status in {"SIGNAL", "PRIOR_SOURCE_BLOCKED"}:
        if not isinstance(prior, dict):
            raise H023ProspectiveError(f"{event_id}: prior source is required")
        validate_source(prior)
        if prior["symbol"] != symbol or prior["report_date"] != previous_quarter_end(report_date):
            raise H023ProspectiveError(f"{event_id}: prior source is not adjacent quarter")
        if _timestamp(prior["broadcast_at_utc"], field="prior.broadcast") > current_broadcast:
            raise H023ProspectiveError(f"{event_id}: prior source was not public at current event")
    elif prior is not None:
        raise H023ProspectiveError(f"{event_id}: status must not carry prior source")

    numeric_fields = (
        "current_mutual_fund_percentage",
        "prior_mutual_fund_percentage",
        "mf_ownership_delta_pp",
    )
    if status == "SIGNAL":
        if not _is_sha256(record.get("current_xbrl_sha256")) or not _is_sha256(
            record.get("prior_xbrl_sha256")
        ):
            raise H023ProspectiveError(f"{event_id}: SIGNAL lacks XBRL digests")
        values: list[float] = []
        for field in numeric_fields:
            value = record.get(field)
            if isinstance(value, bool):
                raise H023ProspectiveError(f"{event_id}: {field} is not finite numeric")
            try:
                parsed = float(value)
            except (TypeError, ValueError) as exc:
                raise H023ProspectiveError(f"{event_id}: {field} is invalid") from exc
            if not math.isfinite(parsed):
                raise H023ProspectiveError(f"{event_id}: {field} is non-finite")
            values.append(parsed)
        if abs((values[0] - values[1]) - values[2]) > 1e-10:
            raise H023ProspectiveError(f"{event_id}: ownership delta arithmetic mismatch")
    else:
        if any(record.get(field) is not None for field in numeric_fields):
            raise H023ProspectiveError(f"{event_id}: no-signal status carries signal values")
    if record.get("record_sha256") != _event_hash(record):
        raise H023ProspectiveError(f"{event_id}: event record digest mismatch")


def validate_event_ledger(ledger: dict[str, Any]) -> None:
    records = _validate_base_ledger(
        ledger, version=EVENT_LEDGER_VERSION, ledger_type="H023_EVENT_LEDGER"
    )
    seen_events: set[str] = set()
    prior_sort: tuple[str, str] | None = None
    for record in records:
        validate_event_record(record)
        event_id = str(record["event_id"])
        if event_id in seen_events:
            raise H023ProspectiveError(f"duplicate H023 event: {event_id}")
        seen_events.add(event_id)
        sort_key = (str(record["report_date"]), str(record["symbol"]))
        if prior_sort is not None and sort_key < prior_sort:
            raise H023ProspectiveError("H023 event ledger is not canonical-sorted")
        prior_sort = sort_key


def _scan_record_hash(record: dict[str, Any]) -> str:
    unsigned = dict(record)
    unsigned.pop("scan_record_sha256", None)
    return canonical_hash(unsigned)


def validate_scan_ledger(ledger: dict[str, Any]) -> None:
    records = _validate_base_ledger(
        ledger, version=SCAN_LEDGER_VERSION, ledger_type="H023_SCAN_LEDGER"
    )
    prior_timestamp: datetime | None = None
    seen_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("H023 scan record must be an object")
        required = {
            "scan_id",
            "scanned_at_utc",
            "member_count",
            "complete_member_count",
            "master_response_sha256_by_symbol",
            "source_ids_by_symbol",
            "scan_record_sha256",
        }
        if not required.issubset(record):
            raise H023ProspectiveError("H023 scan record fields are incomplete")
        scanned = _timestamp(record["scanned_at_utc"], field="scan.scanned_at_utc")
        if prior_timestamp is not None and scanned <= prior_timestamp:
            raise H023ProspectiveError("H023 scans are not strictly chronological")
        prior_timestamp = scanned
        if record.get("member_count") != 100 or record.get("complete_member_count") != 100:
            raise H023ProspectiveError("H023 canonical scan is not complete for all 100 members")
        scan_id = str(record.get("scan_id") or "")
        if not _is_sha256(scan_id) or scan_id in seen_ids:
            raise H023ProspectiveError("H023 scan id is invalid/duplicate")
        seen_ids.add(scan_id)
        if record.get("scan_record_sha256") != _scan_record_hash(record):
            raise H023ProspectiveError(f"{scan_id}: scan record digest mismatch")


def _event_context(record: dict[str, Any]) -> tuple[str, str, datetime, str | None, datetime | None]:
    current = record["current_source"]
    prior = record.get("prior_source")
    return (
        str(record["symbol"]),
        str(record["report_date"]),
        _timestamp(current["broadcast_at_utc"], field="sealed.current.broadcast"),
        str(prior["report_date"]) if isinstance(prior, dict) else None,
        _timestamp(prior["broadcast_at_utc"], field="sealed.prior.broadcast")
        if isinstance(prior, dict)
        else None,
    )


def append_sources(
    ledger: dict[str, Any],
    sources: list[dict[str, Any]],
    *,
    first_seen_at_utc: str,
    event_ledger: dict[str, Any],
) -> dict[str, Any]:
    validate_source_ledger(ledger)
    validate_event_ledger(event_ledger)
    first_seen = _timestamp(first_seen_at_utc, field="first_seen_at_utc")
    existing_by_id = {
        str(row["source"]["source_id"]): row for row in ledger["records"]
    }
    existing_by_record = {
        (str(row["source"]["symbol"]), str(row["source"]["record_id"])): str(
            row["source"]["source_id"]
        )
        for row in ledger["records"]
    }
    sealed_contexts = [_event_context(record) for record in event_ledger["records"]]
    records = [dict(row) for row in ledger["records"]]
    for source in sources:
        validate_source(source)
        source_id = str(source["source_id"])
        existing = existing_by_id.get(source_id)
        if existing is not None:
            if existing["source"] != source:
                raise H023ProspectiveError(
                    f"{source_id}: source reappeared with different immutable identity"
                )
            continue
        key = (str(source["symbol"]), str(source["record_id"]))
        prior_id = existing_by_record.get(key)
        if prior_id is not None and prior_id != source_id:
            raise H023ProspectiveError(
                f"{key[0]}/{key[1]}: official source identity drift detected"
            )
        broadcast = _timestamp(source["broadcast_at_utc"], field=f"{source_id}.broadcast")
        if first_seen < broadcast:
            raise H023ProspectiveError(f"{source_id}: scan first-seen precedes broadcast")
        source_report_date = str(source["report_date"])
        symbol = str(source["symbol"])
        for sealed_symbol, sealed_date, sealed_current_time, prior_date, prior_time in sealed_contexts:
            if sealed_symbol != symbol:
                continue
            if source_report_date == sealed_date and broadcast < sealed_current_time:
                raise RetroactiveSourceGap(
                    f"{source_id}: newly discovered current-quarter source predates sealed event"
                )
            expected_prior = previous_quarter_end(sealed_date)
            if source_report_date != expected_prior or broadcast > sealed_current_time:
                continue
            if prior_date is None:
                raise RetroactiveSourceGap(
                    f"{source_id}: newly discovered prior source invalidates sealed no-prior event"
                )
            if prior_time is not None and broadcast > prior_time:
                raise RetroactiveSourceGap(
                    f"{source_id}: newly discovered prior revision supersedes sealed prior context"
                )
        normalized_seen = _utc_text(first_seen)
        row = {
            "source": source,
            "first_seen_at_utc": normalized_seen,
        }
        row["source_record_sha256"] = canonical_hash(row)
        records.append(row)
        existing_by_id[source_id] = row
        existing_by_record[key] = source_id
    records.sort(
        key=lambda row: (
            str(row["source"]["broadcast_at_utc"]),
            str(row["source"]["symbol"]),
            str(row["source"]["report_date"]),
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
    matches = [
        row for row in ledger["records"] if row["source"]["source_id"] == source_id
    ]
    if len(matches) != 1:
        raise H023ProspectiveError(f"source not uniquely present in ledger: {source_id}")
    return str(matches[0]["first_seen_at_utc"])


def primary_current_source(
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
    matches.sort(key=lambda row: (str(row["broadcast_at_utc"]), str(row["record_id"])))
    return dict(matches[0])


def prior_source_at_event(
    ledger: dict[str, Any], *, symbol: str, current_report_date: str, current_broadcast_at_utc: str
) -> dict[str, Any] | None:
    validate_source_ledger(ledger)
    wanted = symbol.strip().upper()
    prior_date = previous_quarter_end(current_report_date)
    current_time = _timestamp(current_broadcast_at_utc, field="current_broadcast_at_utc")
    matches = [
        row["source"]
        for row in ledger["records"]
        if row["source"]["symbol"] == wanted
        and row["source"]["report_date"] == prior_date
        and _timestamp(row["source"]["broadcast_at_utc"], field="prior.broadcast")
        <= current_time
    ]
    if not matches:
        return None
    matches.sort(
        key=lambda row: (str(row["broadcast_at_utc"]), str(row["record_id"])),
        reverse=True,
    )
    return dict(matches[0])


def event_exists(ledger: dict[str, Any], *, symbol: str, report_date: str) -> bool:
    validate_event_ledger(ledger)
    wanted = symbol.strip().upper()
    return any(
        row["symbol"] == wanted and row["report_date"] == report_date
        for row in ledger["records"]
    )


def build_event_record(
    *,
    source_ledger: dict[str, Any],
    symbol: str,
    report_date: str,
    frozen_at_utc: str,
    current_evidence: dict[str, Any] | None,
    prior_evidence: dict[str, Any] | None,
) -> dict[str, Any] | None:
    validate_source_ledger(source_ledger)
    current = primary_current_source(source_ledger, symbol=symbol, report_date=report_date)
    if current is None:
        return None
    current_broadcast = _timestamp(current["broadcast_at_utc"], field="current.broadcast")
    if current_broadcast < PROSPECTIVE_START_UTC:
        return None
    frozen = _timestamp(frozen_at_utc, field="signal_frozen_at_utc")
    first_seen_text = source_first_seen(source_ledger, str(current["source_id"]))
    first_seen = _timestamp(first_seen_text, field="source_first_seen_at_utc")
    if frozen < first_seen:
        raise H023ProspectiveError("event freeze precedes current source first-seen")

    prior = prior_source_at_event(
        source_ledger,
        symbol=symbol,
        current_report_date=report_date,
        current_broadcast_at_utc=str(current["broadcast_at_utc"]),
    )
    status: str
    current_hash: str | None = None
    prior_hash: str | None = None
    current_pct: float | None = None
    prior_pct: float | None = None
    delta: float | None = None

    if current_evidence is None or current_evidence.get("status") != "READY":
        status = "SOURCE_BLOCKED"
        prior = None
    elif prior is None:
        status = "NO_SIGNAL_PRIOR_UNAVAILABLE"
    elif prior_evidence is None or prior_evidence.get("status") != "READY":
        status = "PRIOR_SOURCE_BLOCKED"
    else:
        if current_evidence.get("source_id") != current["source_id"]:
            raise H023ProspectiveError("current evidence is bound to the wrong source")
        if prior_evidence.get("source_id") != prior["source_id"]:
            raise H023ProspectiveError("prior evidence is bound to the wrong source")
        current_hash = str(current_evidence.get("xbrl_sha256") or "")
        prior_hash = str(prior_evidence.get("xbrl_sha256") or "")
        if not _is_sha256(current_hash) or not _is_sha256(prior_hash):
            raise H023ProspectiveError("ready H023 evidence lacks XBRL SHA-256")
        current_pct = float(current_evidence["mutual_fund_percentage"])
        prior_pct = float(prior_evidence["mutual_fund_percentage"])
        if not math.isfinite(current_pct) or not math.isfinite(prior_pct):
            raise H023ProspectiveError("H023 ownership evidence is non-finite")
        delta = current_pct - prior_pct
        status = "SIGNAL"

    event_id = canonical_hash(
        {
            "protocol_id": PROTOCOL_ID,
            "symbol": symbol.strip().upper(),
            "report_date": report_date,
        }
    )
    record: dict[str, Any] = {
        "event_id": event_id,
        "symbol": symbol.strip().upper(),
        "report_date": report_date,
        "status": status,
        "current_source": current,
        "prior_source": prior,
        "current_xbrl_sha256": current_hash,
        "prior_xbrl_sha256": prior_hash,
        "current_mutual_fund_percentage": current_pct,
        "prior_mutual_fund_percentage": prior_pct,
        "mf_ownership_delta_pp": delta,
        "source_first_seen_at_utc": _utc_text(first_seen),
        "signal_frozen_at_utc": _utc_text(frozen),
    }
    record["record_sha256"] = _event_hash(record)
    validate_event_record(record)
    return record


def append_event(ledger: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    validate_event_ledger(ledger)
    validate_event_record(record)
    event_id = str(record["event_id"])
    for existing in ledger["records"]:
        if existing["event_id"] == event_id:
            if existing != record:
                raise H023ProspectiveError(f"{event_id}: event is immutable and already sealed")
            return ledger
    records = [dict(row) for row in ledger["records"]]
    records.append(record)
    records.sort(key=lambda row: (str(row["report_date"]), str(row["symbol"])))
    result = dict(ledger)
    result["records"] = records
    result["record_count"] = len(records)
    result["ledger_sha256"] = _ledger_hash(result)
    validate_event_ledger(result)
    return result


def build_scan_record(
    *,
    universe_snapshot: dict[str, Any],
    scanned_at_utc: str,
    master_response_sha256_by_symbol: dict[str, str],
    source_ids_by_symbol: dict[str, list[str]],
) -> dict[str, Any]:
    members = validate_universe_snapshot(universe_snapshot)
    scanned = _timestamp(scanned_at_utc, field="scanned_at_utc")
    if set(master_response_sha256_by_symbol) != set(members) or set(source_ids_by_symbol) != set(
        members
    ):
        raise H023ProspectiveError("H023 scan does not exactly account for all frozen symbols")
    for symbol, digest in master_response_sha256_by_symbol.items():
        if not _is_sha256(digest):
            raise H023ProspectiveError(f"{symbol}: master response digest is invalid")
    normalized_sources: dict[str, list[str]] = {}
    for symbol, ids in source_ids_by_symbol.items():
        if not isinstance(ids, list) or any(not _is_sha256(value) for value in ids):
            raise H023ProspectiveError(f"{symbol}: scan source ids are invalid")
        normalized_sources[symbol] = sorted(set(ids))
    payload = {
        "scanned_at_utc": _utc_text(scanned),
        "member_count": len(members),
        "complete_member_count": len(members),
        "master_response_sha256_by_symbol": dict(sorted(master_response_sha256_by_symbol.items())),
        "source_ids_by_symbol": dict(sorted(normalized_sources.items())),
    }
    scan_id = canonical_hash({"protocol_id": PROTOCOL_ID, **payload})
    record = {"scan_id": scan_id, **payload}
    record["scan_record_sha256"] = _scan_record_hash(record)
    return record


def append_scan(ledger: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    validate_scan_ledger(ledger)
    trial = dict(ledger)
    records = [dict(row) for row in ledger["records"]]
    records.append(record)
    trial["records"] = records
    trial["record_count"] = len(records)
    trial["ledger_sha256"] = _ledger_hash(trial)
    validate_scan_ledger(trial)
    return trial
