from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from marketlab.h003_sources import SOURCE_RULE_ID, SOURCE_RULE_SHA256
from marketlab.h022_p001_acquisition import (
    canonical_hash,
    seal_operational_signal,
    validate_operational_context,
)
from marketlab.h022_prospective import (
    COHORT_ID,
    COHORT_SHA256,
    HYPOTHESIS_ID,
    PROSPECTIVE_START,
    PROTOCOL_ID,
    append_signal_record,
    source_disposition,
    validate_e002_record,
    validate_signal_ledger,
    validate_universe_snapshot,
)

SOURCE_LEDGER_VERSION = 1
E002_LEDGER_VERSION = 1
SCAN_MANIFEST_VERSION = 1


class H022P001StreamError(ValueError):
    """Raised when the prospective P001 source stream cannot advance safely."""


class RetroactiveSourceGap(H022P001StreamError):
    """A newly discovered old source invalidates already-sealed prospective context."""


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise H022P001StreamError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H022P001StreamError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H022P001StreamError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _source_identity_payload(source: dict[str, Any]) -> dict[str, str]:
    return {
        "rule_id": SOURCE_RULE_ID,
        "symbol": str(source["symbol"]).strip().upper(),
        "seq_id": str(source["seq_id"]),
        "exchange_published_at_utc": str(source["exchange_published_at_utc"]),
        "attachment_url": str(source["attachment_url"]),
        "discovery_row_sha256": str(source["discovery_row_sha256"]),
    }


def validate_prospective_source(source: dict[str, Any]) -> None:
    if not isinstance(source, dict):
        raise H022P001StreamError("P001 prospective source must be an object")
    required = {
        "source_id",
        "symbol",
        "seq_id",
        "exchange_published_at_utc",
        "attachment_url",
        "discovery_row_sha256",
    }
    if not required.issubset(source):
        raise H022P001StreamError("P001 prospective source identity fields are incomplete")
    source_id = str(source.get("source_id") or "")
    if not _is_sha256(source_id):
        raise H022P001StreamError("P001 prospective source id is not SHA-256")
    if source_id != canonical_hash(_source_identity_payload(source)):
        raise H022P001StreamError(f"{source_id}: prospective source identity hash mismatch")
    if not _is_sha256(source.get("discovery_row_sha256")):
        raise H022P001StreamError(f"{source_id}: discovery row digest is invalid")
    symbol = str(source.get("symbol") or "").strip().upper()
    if not symbol:
        raise H022P001StreamError(f"{source_id}: source symbol is empty")
    published = _timestamp(
        source.get("exchange_published_at_utc"),
        field=f"{source_id}.exchange_published_at_utc",
    )
    if published < PROSPECTIVE_START:
        raise H022P001StreamError(f"{source_id}: source precedes prospective start")
    attachment = str(source.get("attachment_url") or "")
    if not attachment.startswith("https://"):
        raise H022P001StreamError(f"{source_id}: attachment URL is not HTTPS")


def _source_ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = dict(ledger)
    unsigned.pop("ledger_sha256", None)
    return canonical_hash(unsigned)


def new_source_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": SOURCE_LEDGER_VERSION,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "source_rule_id": SOURCE_RULE_ID,
        "source_rule_sha256": SOURCE_RULE_SHA256,
        "prospective_start_utc": _utc_text(PROSPECTIVE_START),
        "outcome_data_attached": False,
        "live_capital_allowed": False,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _source_ledger_hash(ledger)
    return ledger


def validate_source_ledger(ledger: dict[str, Any]) -> None:
    if not isinstance(ledger, dict):
        raise H022P001StreamError("P001 source ledger must be an object")
    if ledger.get("ledger_sha256") != _source_ledger_hash(ledger):
        raise H022P001StreamError("P001 source ledger digest mismatch")
    if (
        ledger.get("schema_version") != SOURCE_LEDGER_VERSION
        or ledger.get("protocol_id") != PROTOCOL_ID
        or ledger.get("hypothesis_id") != HYPOTHESIS_ID
        or ledger.get("cohort_id") != COHORT_ID
        or ledger.get("cohort_sha256") != COHORT_SHA256
        or ledger.get("source_rule_id") != SOURCE_RULE_ID
        or ledger.get("source_rule_sha256") != SOURCE_RULE_SHA256
        or ledger.get("prospective_start_utc") != _utc_text(PROSPECTIVE_START)
    ):
        raise H022P001StreamError("P001 source ledger frozen identity changed")
    if ledger.get("outcome_data_attached") is not False:
        raise H022P001StreamError("P001 source ledger contains outcome data")
    if ledger.get("live_capital_allowed") is not False:
        raise H022P001StreamError("P001 source ledger enabled live capital")
    records = ledger.get("records")
    if not isinstance(records, list) or ledger.get("record_count") != len(records):
        raise H022P001StreamError("P001 source ledger record count mismatch")
    seen_sources: set[str] = set()
    seen_seq: dict[tuple[str, str], str] = {}
    prior_sort: tuple[str, str, str] | None = None
    for record in records:
        if not isinstance(record, dict):
            raise H022P001StreamError("P001 source ledger record must be an object")
        source = record.get("source")
        if not isinstance(source, dict):
            raise H022P001StreamError("P001 source ledger record lacks source object")
        validate_prospective_source(source)
        source_id = str(source["source_id"])
        if source_id in seen_sources:
            raise H022P001StreamError(f"duplicate P001 source ledger source: {source_id}")
        seen_sources.add(source_id)
        symbol = str(source["symbol"]).strip().upper()
        seq_id = str(source["seq_id"])
        key = (symbol, seq_id)
        previous_id = seen_seq.get(key)
        if previous_id is not None and previous_id != source_id:
            raise H022P001StreamError(
                f"{symbol}/{seq_id}: NSE source identity drifted across source ids"
            )
        seen_seq[key] = source_id
        first_seen = _timestamp(
            record.get("first_seen_at_utc"), field=f"{source_id}.first_seen_at_utc"
        )
        published = _timestamp(
            source["exchange_published_at_utc"],
            field=f"{source_id}.exchange_published_at_utc",
        )
        if first_seen < published:
            raise H022P001StreamError(f"{source_id}: source first-seen precedes publication")
        if record.get("source_record_sha256") != canonical_hash(
            {
                "source": source,
                "first_seen_at_utc": _utc_text(first_seen),
            }
        ):
            raise H022P001StreamError(f"{source_id}: source-ledger record digest mismatch")
        sort_key = (str(source["exchange_published_at_utc"]), symbol, source_id)
        if prior_sort is not None and sort_key < prior_sort:
            raise H022P001StreamError("P001 source ledger records are not canonical-sorted")
        prior_sort = sort_key


def append_sources(
    ledger: dict[str, Any],
    sources: list[dict[str, Any]],
    *,
    first_seen_at_utc: str,
    signal_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_source_ledger(ledger)
    first_seen = _timestamp(first_seen_at_utc, field="first_seen_at_utc")
    existing_by_id = {
        str(row["source"]["source_id"]): row for row in ledger["records"]
    }
    existing_by_seq = {
        (str(row["source"]["symbol"]).strip().upper(), str(row["source"]["seq_id"])): str(
            row["source"]["source_id"]
        )
        for row in ledger["records"]
    }
    sealed_signal_publications: dict[str, list[datetime]] = {}
    if signal_ledger is not None:
        validate_signal_ledger(signal_ledger)
        for signal in signal_ledger["records"]:
            symbol = str(signal["symbol"]).strip().upper()
            sealed_signal_publications.setdefault(symbol, []).append(
                _timestamp(
                    signal["exchange_published_at_utc"],
                    field=f"{signal['source_id']}.signal_publication",
                )
            )

    records = [dict(row) for row in ledger["records"]]
    for source in sources:
        validate_prospective_source(source)
        source_id = str(source["source_id"])
        existing = existing_by_id.get(source_id)
        if existing is not None:
            if existing["source"] != source:
                raise H022P001StreamError(
                    f"P001 source {source_id} reappeared with different immutable bytes"
                )
            continue
        symbol = str(source["symbol"]).strip().upper()
        seq_key = (symbol, str(source["seq_id"]))
        prior_source_id = existing_by_seq.get(seq_key)
        if prior_source_id is not None and prior_source_id != source_id:
            raise H022P001StreamError(
                f"{symbol}/{source['seq_id']}: NSE source identity drift detected"
            )
        published = _timestamp(
            source["exchange_published_at_utc"],
            field=f"{source_id}.exchange_published_at_utc",
        )
        if any(
            published < sealed_publication
            for sealed_publication in sealed_signal_publications.get(symbol, [])
        ):
            raise RetroactiveSourceGap(
                f"{source_id}: newly discovered source predates an already sealed {symbol} signal"
            )
        normalized_seen = max(first_seen, published)
        record = {
            "source": dict(source),
            "first_seen_at_utc": _utc_text(normalized_seen),
        }
        record["source_record_sha256"] = canonical_hash(record)
        records.append(record)
        existing_by_id[source_id] = record
        existing_by_seq[seq_key] = source_id

    records.sort(
        key=lambda row: (
            str(row["source"]["exchange_published_at_utc"]),
            str(row["source"]["symbol"]),
            str(row["source"]["source_id"]),
        )
    )
    updated = dict(ledger)
    updated["records"] = records
    updated["record_count"] = len(records)
    updated["ledger_sha256"] = _source_ledger_hash(updated)
    validate_source_ledger(updated)
    return updated


def _e002_ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = dict(ledger)
    unsigned.pop("ledger_sha256", None)
    return canonical_hash(unsigned)


def new_e002_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": E002_LEDGER_VERSION,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "prospective_start_utc": _utc_text(PROSPECTIVE_START),
        "outcome_data_attached": False,
        "live_capital_allowed": False,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _e002_ledger_hash(ledger)
    return ledger


def validate_e002_ledger(ledger: dict[str, Any]) -> None:
    if not isinstance(ledger, dict):
        raise H022P001StreamError("P001 E002 ledger must be an object")
    if ledger.get("ledger_sha256") != _e002_ledger_hash(ledger):
        raise H022P001StreamError("P001 E002 ledger digest mismatch")
    if (
        ledger.get("schema_version") != E002_LEDGER_VERSION
        or ledger.get("protocol_id") != PROTOCOL_ID
        or ledger.get("hypothesis_id") != HYPOTHESIS_ID
        or ledger.get("cohort_id") != COHORT_ID
        or ledger.get("cohort_sha256") != COHORT_SHA256
        or ledger.get("prospective_start_utc") != _utc_text(PROSPECTIVE_START)
    ):
        raise H022P001StreamError("P001 E002 ledger frozen identity changed")
    if ledger.get("outcome_data_attached") is not False:
        raise H022P001StreamError("P001 E002 ledger contains outcome data")
    if ledger.get("live_capital_allowed") is not False:
        raise H022P001StreamError("P001 E002 ledger enabled live capital")
    records = ledger.get("records")
    if not isinstance(records, list) or ledger.get("record_count") != len(records):
        raise H022P001StreamError("P001 E002 ledger record count mismatch")
    seen: set[str] = set()
    prior_sort: tuple[str, str, str] | None = None
    for record in records:
        validate_e002_record(record)
        if source_disposition(record) != "PROSPECTIVE_SIGNAL_ELIGIBLE":
            raise H022P001StreamError(
                f"{record.get('source_id')}: E002 ledger record is not prospective"
            )
        source_id = str(record["source_id"])
        if source_id in seen:
            raise H022P001StreamError(f"duplicate P001 E002 source: {source_id}")
        seen.add(source_id)
        sort_key = (
            str(record["exchange_published_at_utc"]),
            str(record["symbol"]),
            source_id,
        )
        if prior_sort is not None and sort_key < prior_sort:
            raise H022P001StreamError("P001 E002 records are not canonical-sorted")
        prior_sort = sort_key


def append_e002_record(
    ledger: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any]:
    validate_e002_ledger(ledger)
    validate_e002_record(record)
    if source_disposition(record) != "PROSPECTIVE_SIGNAL_ELIGIBLE":
        raise H022P001StreamError("only prospective E002 records may enter stream ledger")
    records = [dict(row) for row in ledger["records"]]
    source_id = str(record["source_id"])
    existing = next((row for row in records if row["source_id"] == source_id), None)
    if existing is not None:
        if existing.get("record_id") == record.get("record_id"):
            return ledger
        raise H022P001StreamError(
            f"P001 E002 source {source_id} already exists with different immutable bytes"
        )
    records.append(dict(record))
    records.sort(
        key=lambda row: (
            str(row["exchange_published_at_utc"]),
            str(row["symbol"]),
            str(row["source_id"]),
        )
    )
    updated = dict(ledger)
    updated["records"] = records
    updated["record_count"] = len(records)
    updated["ledger_sha256"] = _e002_ledger_hash(updated)
    validate_e002_ledger(updated)
    return updated


def unresolved_source_records(
    source_ledger: dict[str, Any], e002_ledger: dict[str, Any]
) -> list[dict[str, Any]]:
    validate_source_ledger(source_ledger)
    validate_e002_ledger(e002_ledger)
    resolved = {str(record["source_id"]) for record in e002_ledger["records"]}
    return [
        dict(row)
        for row in source_ledger["records"]
        if str(row["source"]["source_id"]) not in resolved
    ]


def unresolved_prior_source_ids(
    *,
    current_record: dict[str, Any],
    source_ledger: dict[str, Any],
    e002_ledger: dict[str, Any],
) -> list[str]:
    validate_e002_record(current_record)
    current_symbol = str(current_record["symbol"]).strip().upper()
    current_time = _timestamp(
        current_record["exchange_published_at_utc"], field="current.exchange_published_at_utc"
    )
    unresolved: list[tuple[datetime, str]] = []
    for row in unresolved_source_records(source_ledger, e002_ledger):
        source = row["source"]
        if str(source["symbol"]).strip().upper() != current_symbol:
            continue
        published = _timestamp(
            source["exchange_published_at_utc"],
            field=f"{source['source_id']}.exchange_published_at_utc",
        )
        if published < current_time:
            unresolved.append((published, str(source["source_id"])))
    unresolved.sort()
    return [source_id for _, source_id in unresolved]


def _scan_manifest_hash(manifest: dict[str, Any]) -> str:
    unsigned = dict(manifest)
    unsigned.pop("scan_sha256", None)
    return canonical_hash(unsigned)


def build_scan_manifest(
    *,
    universe_snapshot: dict[str, Any],
    cutoff_utc: str,
    completed_at_utc: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    members = validate_universe_snapshot(universe_snapshot)
    cutoff = _timestamp(cutoff_utc, field="scan.cutoff_utc")
    completed = _timestamp(completed_at_utc, field="scan.completed_at_utc")
    if cutoff < PROSPECTIVE_START or completed < cutoff:
        raise H022P001StreamError("P001 scan timestamps are outside prospective ordering")
    by_symbol: dict[str, dict[str, Any]] = {}
    all_source_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise H022P001StreamError("P001 scan row must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol not in members or symbol in by_symbol:
            raise H022P001StreamError(f"invalid/duplicate P001 scan symbol: {symbol}")
        status = row.get("coverage_status")
        sources = row.get("sources")
        if status not in {"COMPLETE", "INCOMPLETE"} or not isinstance(sources, list):
            raise H022P001StreamError(f"{symbol}: invalid P001 scan coverage row")
        if status == "COMPLETE":
            if not _is_sha256(row.get("discovery_sha256")):
                raise H022P001StreamError(f"{symbol}: complete scan row lacks discovery digest")
            if row.get("incomplete_reason") is not None:
                raise H022P001StreamError(f"{symbol}: complete scan row has failure reason")
        else:
            if sources:
                raise H022P001StreamError(f"{symbol}: incomplete scan row must not claim sources")
            reason = row.get("incomplete_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise H022P001StreamError(f"{symbol}: incomplete scan row lacks reason")
        for source in sources:
            validate_prospective_source(source)
            if str(source["symbol"]).strip().upper() != symbol:
                raise H022P001StreamError(f"{symbol}: scan source symbol mismatch")
            source_id = str(source["source_id"])
            if source_id in all_source_ids:
                raise H022P001StreamError(f"duplicate source across scan rows: {source_id}")
            all_source_ids.add(source_id)
            if _timestamp(
                source["exchange_published_at_utc"],
                field=f"{source_id}.published",
            ) > cutoff:
                raise H022P001StreamError(f"{source_id}: source is after scan cutoff")
        if row.get("source_count") != len(sources):
            raise H022P001StreamError(f"{symbol}: scan source_count mismatch")
        by_symbol[symbol] = {
            "symbol": symbol,
            "coverage_status": status,
            "incomplete_reason": row.get("incomplete_reason"),
            "discovery_sha256": row.get("discovery_sha256"),
            "source_count": len(sources),
            "sources": sorted(sources, key=lambda source: str(source["source_id"])),
        }
    if set(by_symbol) != set(members):
        missing = sorted(set(members) - set(by_symbol))
        extra = sorted(set(by_symbol) - set(members))
        raise H022P001StreamError(
            f"P001 scan does not exactly cover U001: missing={missing} extra={extra}"
        )
    ordered = [
        by_symbol[str(member["symbol"]).strip().upper()]
        for member in universe_snapshot["members"]
    ]
    incomplete = [row["symbol"] for row in ordered if row["coverage_status"] != "COMPLETE"]
    manifest: dict[str, Any] = {
        "schema_version": SCAN_MANIFEST_VERSION,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "source_rule_id": SOURCE_RULE_ID,
        "source_rule_sha256": SOURCE_RULE_SHA256,
        "prospective_start_utc": _utc_text(PROSPECTIVE_START),
        "cutoff_utc": _utc_text(cutoff),
        "completed_at_utc": _utc_text(completed),
        "member_count": len(ordered),
        "complete_member_count": len(ordered) - len(incomplete),
        "incomplete_member_count": len(incomplete),
        "incomplete_symbols": incomplete,
        "source_count": len(all_source_ids),
        "source_ids": sorted(all_source_ids),
        "records": ordered,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    manifest["scan_sha256"] = _scan_manifest_hash(manifest)
    return manifest


def validate_scan_manifest(manifest: dict[str, Any], universe_snapshot: dict[str, Any]) -> None:
    if not isinstance(manifest, dict) or manifest.get("scan_sha256") != _scan_manifest_hash(
        manifest
    ):
        raise H022P001StreamError("P001 scan manifest digest mismatch")
    if (
        manifest.get("schema_version") != SCAN_MANIFEST_VERSION
        or manifest.get("protocol_id") != PROTOCOL_ID
        or manifest.get("hypothesis_id") != HYPOTHESIS_ID
        or manifest.get("cohort_id") != COHORT_ID
        or manifest.get("cohort_sha256") != COHORT_SHA256
        or manifest.get("source_rule_id") != SOURCE_RULE_ID
        or manifest.get("source_rule_sha256") != SOURCE_RULE_SHA256
        or manifest.get("prospective_start_utc") != _utc_text(PROSPECTIVE_START)
    ):
        raise H022P001StreamError("P001 scan manifest frozen identity changed")
    if manifest.get("outcome_data_attached") is not False:
        raise H022P001StreamError("P001 scan manifest contains outcome data")
    if manifest.get("live_capital_allowed") is not False:
        raise H022P001StreamError("P001 scan manifest enabled live capital")
    rebuilt = build_scan_manifest(
        universe_snapshot=universe_snapshot,
        cutoff_utc=str(manifest.get("cutoff_utc") or ""),
        completed_at_utc=str(manifest.get("completed_at_utc") or ""),
        rows=list(manifest.get("records") or []),
    )
    if rebuilt != manifest:
        raise H022P001StreamError("P001 scan manifest canonical reconstruction mismatch")


def scan_complete(manifest: dict[str, Any]) -> bool:
    return (
        manifest.get("member_count") == 100
        and manifest.get("complete_member_count") == 100
        and manifest.get("incomplete_member_count") == 0
    )


def reconstruct_static_prior_records(
    *,
    prior_index: dict[str, Any],
    historical_records: list[dict[str, Any]],
    catchup_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    available: dict[tuple[str, str], dict[str, Any]] = {}
    for record in [*historical_records, *catchup_records]:
        validate_e002_record(record)
        key = (str(record["source_id"]), str(record["record_id"]))
        existing = available.get(key)
        if existing is not None and existing != record:
            raise H022P001StreamError(f"static prior record identity collision: {key}")
        available[key] = record
    required: set[tuple[str, str]] = {
        (str(record["source_id"]), str(record["record_id"]))
        for entry in prior_index.get("entries", [])
        if isinstance(entry, dict)
        for record in entry.get("records", [])
        if isinstance(record, dict)
    }
    missing = sorted(required - set(available))
    if missing:
        raise H022P001StreamError(f"static prior full records are unavailable: {missing}")
    records = [dict(available[key]) for key in sorted(required)]
    records.sort(
        key=lambda row: (
            str(row["exchange_published_at_utc"]),
            str(row["symbol"]),
            str(row["source_id"]),
        )
    )
    return records


def seal_pending_signals(
    *,
    source_ledger: dict[str, Any],
    e002_ledger: dict[str, Any],
    signal_ledger: dict[str, Any],
    static_prior_records: list[dict[str, Any]],
    universe_snapshot: dict[str, Any],
    core_gate: dict[str, Any],
    discovery_manifest: dict[str, Any],
    prior_index: dict[str, Any],
    operational_context: dict[str, Any],
    frozen_at_utc: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validate_source_ledger(source_ledger)
    validate_e002_ledger(e002_ledger)
    validate_signal_ledger(signal_ledger)
    validate_operational_context(
        operational_context=operational_context,
        core_gate=core_gate,
        prior_index=prior_index,
        discovery_manifest=discovery_manifest,
        universe_snapshot=universe_snapshot,
    )
    frozen_at = _timestamp(frozen_at_utc, field="frozen_at_utc")
    signaled = {str(record["source_id"]) for record in signal_ledger["records"]}
    prospective_records = [dict(record) for record in e002_ledger["records"]]
    blocked: list[dict[str, Any]] = []
    updated = signal_ledger
    for current in prospective_records:
        source_id = str(current["source_id"])
        if source_id in signaled:
            continue
        unresolved = unresolved_prior_source_ids(
            current_record=current,
            source_ledger=source_ledger,
            e002_ledger=e002_ledger,
        )
        if unresolved:
            blocked.append(
                {
                    "source_id": source_id,
                    "symbol": current["symbol"],
                    "exchange_published_at_utc": current["exchange_published_at_utc"],
                    "reason": "UNRESOLVED_EARLIER_SOURCE",
                    "unresolved_prior_source_ids": unresolved,
                }
            )
            continue
        current_time = _timestamp(
            current["exchange_published_at_utc"], field=f"{source_id}.published"
        )
        if frozen_at < current_time:
            raise H022P001StreamError(f"{source_id}: signal freeze precedes publication")
        symbol = str(current["symbol"]).strip().upper()
        context_records = [
            record
            for record in static_prior_records
            if str(record["symbol"]).strip().upper() == symbol
        ]
        context_records.extend(
            record
            for record in prospective_records
            if str(record["symbol"]).strip().upper() == symbol
            and str(record["source_id"]) != source_id
            and _timestamp(
                record["exchange_published_at_utc"],
                field=f"{record['source_id']}.published",
            )
            <= current_time
        )
        signal = seal_operational_signal(
            current_record=current,
            context_records=context_records,
            universe_snapshot=universe_snapshot,
            core_gate=core_gate,
            discovery_manifest=discovery_manifest,
            prior_index=prior_index,
            operational_context=operational_context,
            signal_frozen_at_utc=_utc_text(frozen_at),
        )
        updated = append_signal_record(updated, signal)
        signaled.add(source_id)
    return updated, blocked


def validate_stream_consistency(
    *,
    source_ledger: dict[str, Any],
    e002_ledger: dict[str, Any],
    signal_ledger: dict[str, Any],
) -> None:
    validate_source_ledger(source_ledger)
    validate_e002_ledger(e002_ledger)
    validate_signal_ledger(signal_ledger)
    source_ids = {str(row["source"]["source_id"]) for row in source_ledger["records"]}
    e002_by_id = {str(row["source_id"]): row for row in e002_ledger["records"]}
    signal_by_id = {str(row["source_id"]): row for row in signal_ledger["records"]}
    extra_e002 = sorted(set(e002_by_id) - source_ids)
    extra_signals = sorted(set(signal_by_id) - set(e002_by_id))
    if extra_e002:
        raise H022P001StreamError(f"E002 records lack discovered source: {extra_e002}")
    if extra_signals:
        raise H022P001StreamError(f"signals lack E002 records: {extra_signals}")
    for source_id, signal in signal_by_id.items():
        current = e002_by_id[source_id]
        unresolved = unresolved_prior_source_ids(
            current_record=current,
            source_ledger=source_ledger,
            e002_ledger=e002_ledger,
        )
        if unresolved:
            raise H022P001StreamError(
                f"{source_id}: sealed signal has unresolved earlier sources: {unresolved}"
            )
        if signal.get("source_record_id") != current.get("record_id"):
            raise H022P001StreamError(f"{source_id}: signal/E002 record identity mismatch")
