from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from marketlab.h003_candidates import ALLOWED_ATTACHMENT_HOSTS
from marketlab.h003_sources import SOURCE_RULE_ID, SOURCE_RULE_SHA256
from marketlab.h022_prospective import (
    COHORT_ID,
    COHORT_SHA256,
    HISTORICAL_BASELINE_REPORT_SHA256,
    HISTORICAL_BASELINE_SOURCE_BUNDLE_SHA256,
    HISTORICAL_CUTOFF,
    HYPOTHESIS_ID,
    PROSPECTIVE_START,
    PROTOCOL_ID,
    H022ProspectiveError,
    _signal_record_hash,
    build_context_gate,
    seal_signal_record,
    source_disposition,
    validate_context_gate,
    validate_e002_record,
    validate_signal_record,
    validate_universe_snapshot,
)

IST = ZoneInfo("Asia/Kolkata")
DISCOVERY_MANIFEST_VERSION = 1
STATIC_PRIOR_INDEX_VERSION = 1
OPERATIONAL_CONTEXT_VERSION = 1


class H022P001AcquisitionError(ValueError):
    """Raised when P001 acquisition/context evidence is incomplete or inconsistent."""


def canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise H022P001AcquisitionError("P001 acquisition payload must be finite JSON") from exc
    return hashlib.sha256(raw).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise H022P001AcquisitionError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise H022P001AcquisitionError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H022P001AcquisitionError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise H022P001AcquisitionError("timestamp must include timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def catchup_query_dates() -> tuple[date, date]:
    start = HISTORICAL_CUTOFF.astimezone(IST).date()
    end = PROSPECTIVE_START.astimezone(IST).date()
    if PROSPECTIVE_START.astimezone(IST).time().isoformat() == "00:00:00":
        end = date.fromordinal(end.toordinal() - 1)
    return start, end


def _source_identity_payload(source: dict[str, Any]) -> dict[str, str]:
    return {
        "rule_id": SOURCE_RULE_ID,
        "symbol": str(source["symbol"]).strip().upper(),
        "seq_id": str(source["seq_id"]),
        "exchange_published_at_utc": str(source["exchange_published_at_utc"]),
        "attachment_url": str(source["attachment_url"]),
        "discovery_row_sha256": str(source["discovery_row_sha256"]),
    }


def validate_catchup_source(source: dict[str, Any], *, expected_symbol: str) -> None:
    if not isinstance(source, dict):
        raise H022P001AcquisitionError("catch-up source must be an object")
    required = {
        "source_id",
        "symbol",
        "seq_id",
        "exchange_published_at_utc",
        "attachment_url",
        "discovery_row_sha256",
    }
    if not required.issubset(source):
        raise H022P001AcquisitionError("catch-up source identity fields are incomplete")
    symbol = str(source.get("symbol") or "").strip().upper()
    if symbol != expected_symbol.strip().upper():
        raise H022P001AcquisitionError(
            f"catch-up source symbol mismatch: expected={expected_symbol} observed={symbol}"
        )
    source_id = str(source.get("source_id") or "")
    if not _is_sha256(source_id) or source_id != canonical_hash(_source_identity_payload(source)):
        raise H022P001AcquisitionError(f"{symbol}: catch-up source identity hash mismatch")
    if not _is_sha256(source.get("discovery_row_sha256")):
        raise H022P001AcquisitionError(f"{symbol}: discovery row digest is invalid")
    parsed_url = urlparse(str(source.get("attachment_url") or ""))
    if (
        parsed_url.scheme != "https"
        or (parsed_url.hostname or "").lower() not in ALLOWED_ATTACHMENT_HOSTS
    ):
        raise H022P001AcquisitionError(f"{symbol}: attachment URL is not approved NSE host")
    published = _timestamp(
        source.get("exchange_published_at_utc"),
        field=f"{source_id}.exchange_published_at_utc",
    )
    if not HISTORICAL_CUTOFF < published < PROSPECTIVE_START:
        raise H022P001AcquisitionError(
            f"{source_id}: source is outside the frozen context-only catch-up interval"
        )


def build_discovery_manifest(
    *,
    universe_snapshot: dict[str, Any],
    rows: list[dict[str, Any]],
    generated_at_utc: str,
) -> dict[str, Any]:
    members = validate_universe_snapshot(universe_snapshot)
    generated = _timestamp(generated_at_utc, field="discovery.generated_at_utc")
    by_symbol: dict[str, dict[str, Any]] = {}
    source_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise H022P001AcquisitionError("discovery coverage row must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in by_symbol:
            raise H022P001AcquisitionError(f"invalid/duplicate discovery symbol: {symbol}")
        if symbol not in members:
            raise H022P001AcquisitionError(f"{symbol}: discovery row is outside frozen U001")
        status = row.get("coverage_status")
        if status not in {"COMPLETE", "INCOMPLETE"}:
            raise H022P001AcquisitionError(f"{symbol}: invalid coverage_status")
        sources = row.get("sources")
        if not isinstance(sources, list):
            raise H022P001AcquisitionError(f"{symbol}: sources must be a list")
        if status == "COMPLETE":
            if not _is_sha256(row.get("discovery_sha256")):
                raise H022P001AcquisitionError(f"{symbol}: complete row lacks discovery digest")
            if row.get("incomplete_reason") is not None:
                raise H022P001AcquisitionError(f"{symbol}: complete row has incomplete reason")
        else:
            if sources:
                raise H022P001AcquisitionError(f"{symbol}: incomplete row must not claim sources")
            reason = row.get("incomplete_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise H022P001AcquisitionError(f"{symbol}: incomplete row requires reason")
        for source in sources:
            validate_catchup_source(source, expected_symbol=symbol)
            source_id = str(source["source_id"])
            if source_id in source_ids:
                raise H022P001AcquisitionError(f"duplicate catch-up source id: {source_id}")
            source_ids.add(source_id)
        if row.get("source_count") != len(sources):
            raise H022P001AcquisitionError(f"{symbol}: source_count mismatch")
        by_symbol[symbol] = {
            "symbol": symbol,
            "coverage_status": status,
            "incomplete_reason": row.get("incomplete_reason"),
            "discovery_sha256": row.get("discovery_sha256"),
            "source_count": len(sources),
            "sources": sorted(sources, key=lambda item: str(item["source_id"])),
        }

    if set(by_symbol) != set(members):
        missing = sorted(set(members) - set(by_symbol))
        extra = sorted(set(by_symbol) - set(members))
        raise H022P001AcquisitionError(
            f"discovery manifest does not exactly cover U001: missing={missing} extra={extra}"
        )
    ordered_symbols = [str(row["symbol"]).strip().upper() for row in universe_snapshot["members"]]
    ordered = [by_symbol[symbol] for symbol in ordered_symbols]
    incomplete = [row["symbol"] for row in ordered if row["coverage_status"] != "COMPLETE"]
    manifest: dict[str, Any] = {
        "schema_version": DISCOVERY_MANIFEST_VERSION,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "source_rule_id": SOURCE_RULE_ID,
        "source_rule_sha256": SOURCE_RULE_SHA256,
        "catchup_start_exclusive_utc": _utc_text(HISTORICAL_CUTOFF),
        "catchup_end_exclusive_utc": _utc_text(PROSPECTIVE_START),
        "generated_at_utc": _utc_text(generated),
        "member_count": len(ordered),
        "complete_member_count": len(ordered) - len(incomplete),
        "incomplete_member_count": len(incomplete),
        "incomplete_symbols": incomplete,
        "catchup_source_count": len(source_ids),
        "catchup_source_ids": sorted(source_ids),
        "records": ordered,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    manifest["manifest_sha256"] = canonical_hash(manifest)
    return manifest


def validate_discovery_manifest(
    manifest: dict[str, Any], universe_snapshot: dict[str, Any]
) -> None:
    if not isinstance(manifest, dict):
        raise H022P001AcquisitionError("discovery manifest must be an object")
    stored = manifest.get("manifest_sha256")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if not _is_sha256(stored) or stored != canonical_hash(unsigned):
        raise H022P001AcquisitionError("discovery manifest digest mismatch")
    if manifest.get("schema_version") != DISCOVERY_MANIFEST_VERSION:
        raise H022P001AcquisitionError("discovery manifest schema changed")
    if (
        manifest.get("protocol_id") != PROTOCOL_ID
        or manifest.get("hypothesis_id") != HYPOTHESIS_ID
        or manifest.get("cohort_id") != COHORT_ID
        or manifest.get("cohort_sha256") != COHORT_SHA256
    ):
        raise H022P001AcquisitionError("discovery manifest identity changed")
    if (
        manifest.get("source_rule_id") != SOURCE_RULE_ID
        or manifest.get("source_rule_sha256") != SOURCE_RULE_SHA256
    ):
        raise H022P001AcquisitionError("discovery source rule changed")
    if (
        manifest.get("catchup_start_exclusive_utc") != _utc_text(HISTORICAL_CUTOFF)
        or manifest.get("catchup_end_exclusive_utc") != _utc_text(PROSPECTIVE_START)
    ):
        raise H022P001AcquisitionError("discovery catch-up interval changed")
    if manifest.get("outcome_data_attached") is not False:
        raise H022P001AcquisitionError("discovery manifest contains outcome attachment")
    if manifest.get("live_capital_allowed") is not False:
        raise H022P001AcquisitionError("discovery manifest enabled live capital")
    rebuilt = build_discovery_manifest(
        universe_snapshot=universe_snapshot,
        rows=list(manifest.get("records") or []),
        generated_at_utc=str(manifest.get("generated_at_utc") or ""),
    )
    if rebuilt != manifest:
        raise H022P001AcquisitionError("discovery manifest canonical reconstruction mismatch")


def discovery_complete(manifest: dict[str, Any]) -> bool:
    return (
        manifest.get("member_count") == 100
        and manifest.get("complete_member_count") == 100
        and manifest.get("incomplete_member_count") == 0
    )


def _record_identity(record: dict[str, Any]) -> tuple[str, str]:
    validate_e002_record(record)
    return str(record["source_id"]), str(record["record_id"])


def _record_timestamp(record: dict[str, Any]) -> datetime:
    return _timestamp(
        record.get("exchange_published_at_utc"),
        field=f"{record.get('source_id')}.exchange_published_at_utc",
    )


def build_static_prior_index(
    *,
    universe_snapshot: dict[str, Any],
    historical_records: list[dict[str, Any]],
    catchup_records: list[dict[str, Any]],
    built_at_utc: str,
) -> dict[str, Any]:
    members = validate_universe_snapshot(universe_snapshot)
    built_at = _timestamp(built_at_utc, field="prior_index.built_at_utc")
    if built_at < PROSPECTIVE_START:
        raise H022P001AcquisitionError("static prior index cannot be built before prospective start")

    grouped: dict[str, dict[datetime, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    seen_source_ids: set[str] = set()
    for record in historical_records:
        validate_e002_record(record)
        symbol = str(record["symbol"]).strip().upper()
        if symbol not in members:
            continue
        source_id, _ = _record_identity(record)
        if source_id in seen_source_ids:
            raise H022P001AcquisitionError(f"duplicate context source id: {source_id}")
        seen_source_ids.add(source_id)
        published = _record_timestamp(record)
        if published > HISTORICAL_CUTOFF:
            raise H022P001AcquisitionError(
                f"{source_id}: historical baseline record exceeds frozen cutoff"
            )
        grouped[symbol][published].append(record)

    expected_catchup_ids: set[str] = set()
    for record in catchup_records:
        validate_e002_record(record)
        symbol = str(record["symbol"]).strip().upper()
        if symbol not in members:
            raise H022P001AcquisitionError(f"{symbol}: catch-up record outside frozen U001")
        source_id, _ = _record_identity(record)
        if source_id in seen_source_ids:
            raise H022P001AcquisitionError(f"duplicate context source id: {source_id}")
        seen_source_ids.add(source_id)
        expected_catchup_ids.add(source_id)
        if source_disposition(record) != "CONTEXT_ONLY_PRE_START":
            raise H022P001AcquisitionError(
                f"{source_id}: catch-up extraction is not CONTEXT_ONLY_PRE_START"
            )
        grouped[symbol][_record_timestamp(record)].append(record)

    entries: list[dict[str, Any]] = []
    for member in universe_snapshot["members"]:
        symbol = str(member["symbol"]).strip().upper()
        timestamp_groups = grouped.get(symbol, {})
        if not timestamp_groups:
            entries.append(
                {
                    "symbol": symbol,
                    "status": "NO_PRIOR_TRANSCRIPT",
                    "latest_prior_timestamp_utc": None,
                    "records": [],
                }
            )
            continue
        latest = max(timestamp_groups)
        latest_records = sorted(
            timestamp_groups[latest], key=lambda row: str(row["source_id"])
        )
        sealed_records = [
            {
                "source_id": str(row["source_id"]),
                "record_id": str(row["record_id"]),
                "exchange_published_at_utc": str(row["exchange_published_at_utc"]),
                "disposition": source_disposition(row),
            }
            for row in latest_records
        ]
        entries.append(
            {
                "symbol": symbol,
                "status": (
                    "UNIQUE_PRIOR"
                    if len(sealed_records) == 1
                    else "AMBIGUOUS_PRIOR_TIMESTAMP"
                ),
                "latest_prior_timestamp_utc": _utc_text(latest),
                "records": sealed_records,
            }
        )

    index: dict[str, Any] = {
        "schema_version": STATIC_PRIOR_INDEX_VERSION,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "historical_baseline_report_sha256": HISTORICAL_BASELINE_REPORT_SHA256,
        "historical_baseline_source_bundle_sha256": (
            HISTORICAL_BASELINE_SOURCE_BUNDLE_SHA256
        ),
        "prospective_start_utc": _utc_text(PROSPECTIVE_START),
        "built_at_utc": _utc_text(built_at),
        "member_count": len(entries),
        "catchup_record_count": len(expected_catchup_ids),
        "catchup_source_ids": sorted(expected_catchup_ids),
        "entries": entries,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    index["prior_index_sha256"] = canonical_hash(index)
    return index


def validate_static_prior_index(
    index: dict[str, Any], universe_snapshot: dict[str, Any]
) -> None:
    if not isinstance(index, dict):
        raise H022P001AcquisitionError("static prior index must be an object")
    stored = index.get("prior_index_sha256")
    unsigned = dict(index)
    unsigned.pop("prior_index_sha256", None)
    if not _is_sha256(stored) or stored != canonical_hash(unsigned):
        raise H022P001AcquisitionError("static prior index digest mismatch")
    members = validate_universe_snapshot(universe_snapshot)
    if (
        index.get("schema_version") != STATIC_PRIOR_INDEX_VERSION
        or index.get("protocol_id") != PROTOCOL_ID
        or index.get("hypothesis_id") != HYPOTHESIS_ID
        or index.get("cohort_id") != COHORT_ID
        or index.get("cohort_sha256") != COHORT_SHA256
    ):
        raise H022P001AcquisitionError("static prior index identity changed")
    if (
        index.get("historical_baseline_report_sha256")
        != HISTORICAL_BASELINE_REPORT_SHA256
        or index.get("historical_baseline_source_bundle_sha256")
        != HISTORICAL_BASELINE_SOURCE_BUNDLE_SHA256
        or index.get("prospective_start_utc") != _utc_text(PROSPECTIVE_START)
    ):
        raise H022P001AcquisitionError("static prior index frozen baseline changed")
    if index.get("outcome_data_attached") is not False:
        raise H022P001AcquisitionError("static prior index contains outcome attachment")
    if index.get("live_capital_allowed") is not False:
        raise H022P001AcquisitionError("static prior index enabled live capital")
    entries = index.get("entries")
    if not isinstance(entries, list) or len(entries) != 100:
        raise H022P001AcquisitionError("static prior index must contain 100 entries")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise H022P001AcquisitionError("static prior entry must be an object")
        symbol = str(entry.get("symbol") or "").strip().upper()
        if symbol not in members or symbol in seen:
            raise H022P001AcquisitionError(f"invalid/duplicate static prior symbol: {symbol}")
        seen.add(symbol)
        status = entry.get("status")
        records = entry.get("records")
        if not isinstance(records, list):
            raise H022P001AcquisitionError(f"{symbol}: static prior records must be a list")
        if status == "NO_PRIOR_TRANSCRIPT":
            if records or entry.get("latest_prior_timestamp_utc") is not None:
                raise H022P001AcquisitionError(f"{symbol}: NO_PRIOR entry contains records")
            continue
        if status not in {"UNIQUE_PRIOR", "AMBIGUOUS_PRIOR_TIMESTAMP"}:
            raise H022P001AcquisitionError(f"{symbol}: invalid static prior status")
        if status == "UNIQUE_PRIOR" and len(records) != 1:
            raise H022P001AcquisitionError(f"{symbol}: UNIQUE_PRIOR must contain one record")
        if status == "AMBIGUOUS_PRIOR_TIMESTAMP" and len(records) < 2:
            raise H022P001AcquisitionError(
                f"{symbol}: AMBIGUOUS_PRIOR_TIMESTAMP requires multiple records"
            )
        timestamp = _timestamp(
            entry.get("latest_prior_timestamp_utc"), field=f"{symbol}.latest_prior_timestamp"
        )
        pairs: set[tuple[str, str]] = set()
        for record in records:
            if not isinstance(record, dict):
                raise H022P001AcquisitionError(f"{symbol}: prior identity must be an object")
            source_id = str(record.get("source_id") or "")
            record_id = str(record.get("record_id") or "")
            if not _is_sha256(source_id) or not _is_sha256(record_id):
                raise H022P001AcquisitionError(f"{symbol}: prior source/record digest invalid")
            pair = (source_id, record_id)
            if pair in pairs:
                raise H022P001AcquisitionError(f"{symbol}: duplicate prior identity")
            pairs.add(pair)
            if _timestamp(
                record.get("exchange_published_at_utc"), field=f"{source_id}.published"
            ) != timestamp:
                raise H022P001AcquisitionError(f"{symbol}: prior timestamp group is inconsistent")
            if record.get("disposition") not in {
                "HISTORICAL_BASELINE",
                "CONTEXT_ONLY_PRE_START",
            }:
                raise H022P001AcquisitionError(f"{symbol}: invalid static prior disposition")
    if seen != set(members):
        raise H022P001AcquisitionError("static prior index symbol set changed")


def build_operational_context(
    *,
    universe_snapshot: dict[str, Any],
    discovery_manifest: dict[str, Any],
    historical_records: list[dict[str, Any]],
    catchup_records: list[dict[str, Any]],
    completed_at_utc: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    validate_discovery_manifest(discovery_manifest, universe_snapshot)
    if not discovery_complete(discovery_manifest):
        raise H022P001AcquisitionError("catch-up discovery is incomplete")
    expected_ids = set(discovery_manifest["catchup_source_ids"])
    actual_ids = {str(record.get("source_id") or "") for record in catchup_records}
    if actual_ids != expected_ids:
        raise H022P001AcquisitionError(
            "catch-up extraction set differs from discovery manifest: "
            f"missing={sorted(expected_ids - actual_ids)} extra={sorted(actual_ids - expected_ids)}"
        )
    for record in catchup_records:
        validate_e002_record(record)
        if source_disposition(record) != "CONTEXT_ONLY_PRE_START":
            raise H022P001AcquisitionError(
                f"{record.get('source_id')}: extracted catch-up record disposition changed"
            )

    prior_index = build_static_prior_index(
        universe_snapshot=universe_snapshot,
        historical_records=historical_records,
        catchup_records=catchup_records,
        built_at_utc=completed_at_utc,
    )
    core_gate = build_context_gate(
        universe_snapshot=universe_snapshot,
        discovery_manifest_sha256=str(discovery_manifest["manifest_sha256"]),
        covered_symbols=[str(row["symbol"]) for row in universe_snapshot["members"]],
        catchup_source_ids=sorted(expected_ids),
        completed_at_utc=completed_at_utc,
    )
    operational: dict[str, Any] = {
        "schema_version": OPERATIONAL_CONTEXT_VERSION,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "context_gate_sha256": core_gate["context_gate_sha256"],
        "discovery_manifest_sha256": discovery_manifest["manifest_sha256"],
        "prior_index_sha256": prior_index["prior_index_sha256"],
        "catchup_source_count": len(expected_ids),
        "completed_at_utc": core_gate["completed_at_utc"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    operational["operational_context_sha256"] = canonical_hash(operational)
    return core_gate, prior_index, operational


def validate_operational_context(
    *,
    operational_context: dict[str, Any],
    core_gate: dict[str, Any],
    prior_index: dict[str, Any],
    discovery_manifest: dict[str, Any],
    universe_snapshot: dict[str, Any],
) -> None:
    stored = operational_context.get("operational_context_sha256")
    unsigned = dict(operational_context)
    unsigned.pop("operational_context_sha256", None)
    if not _is_sha256(stored) or stored != canonical_hash(unsigned):
        raise H022P001AcquisitionError("operational context digest mismatch")
    validate_context_gate(core_gate, universe_snapshot)
    validate_static_prior_index(prior_index, universe_snapshot)
    validate_discovery_manifest(discovery_manifest, universe_snapshot)
    if (
        operational_context.get("schema_version") != OPERATIONAL_CONTEXT_VERSION
        or operational_context.get("protocol_id") != PROTOCOL_ID
        or operational_context.get("hypothesis_id") != HYPOTHESIS_ID
        or operational_context.get("cohort_id") != COHORT_ID
        or operational_context.get("cohort_sha256") != COHORT_SHA256
    ):
        raise H022P001AcquisitionError("operational context identity changed")
    if operational_context.get("context_gate_sha256") != core_gate.get(
        "context_gate_sha256"
    ):
        raise H022P001AcquisitionError("operational context gate binding changed")
    if operational_context.get("prior_index_sha256") != prior_index.get(
        "prior_index_sha256"
    ):
        raise H022P001AcquisitionError("operational context prior-index binding changed")
    if operational_context.get("discovery_manifest_sha256") != discovery_manifest.get(
        "manifest_sha256"
    ):
        raise H022P001AcquisitionError("operational context discovery binding changed")
    if operational_context.get("outcome_data_attached") is not False:
        raise H022P001AcquisitionError("operational context contains outcome attachment")
    if operational_context.get("live_capital_allowed") is not False:
        raise H022P001AcquisitionError("operational context enabled live capital")


def static_prior_identities(
    prior_index: dict[str, Any], *, symbol: str
) -> set[tuple[str, str]]:
    wanted = symbol.strip().upper()
    entries = [row for row in prior_index["entries"] if row.get("symbol") == wanted]
    if len(entries) != 1:
        raise H022P001AcquisitionError(f"{wanted}: static prior entry is missing/duplicated")
    return {
        (str(row["source_id"]), str(row["record_id"]))
        for row in entries[0]["records"]
    }


def seal_operational_signal(
    *,
    current_record: dict[str, Any],
    context_records: list[dict[str, Any]],
    universe_snapshot: dict[str, Any],
    core_gate: dict[str, Any],
    discovery_manifest: dict[str, Any],
    prior_index: dict[str, Any],
    operational_context: dict[str, Any],
    signal_frozen_at_utc: str,
    cohort_end_utc: str | None = None,
) -> dict[str, Any]:
    validate_operational_context(
        operational_context=operational_context,
        core_gate=core_gate,
        prior_index=prior_index,
        discovery_manifest=discovery_manifest,
        universe_snapshot=universe_snapshot,
    )
    validate_e002_record(current_record)
    symbol = str(current_record["symbol"]).strip().upper()
    required = static_prior_identities(prior_index, symbol=symbol)
    supplied = {
        (str(record.get("source_id") or ""), str(record.get("record_id") or ""))
        for record in context_records
        if str(record.get("symbol") or "").strip().upper() == symbol
    }
    if not required.issubset(supplied):
        raise H022P001AcquisitionError(
            f"{symbol}: context omits frozen static prior records: {sorted(required - supplied)}"
        )

    sealed = seal_signal_record(
        current_record=current_record,
        context_records=context_records,
        universe_snapshot=universe_snapshot,
        context_gate=core_gate,
        signal_frozen_at_utc=signal_frozen_at_utc,
        cohort_end_utc=cohort_end_utc,
    )
    sealed["prior_index_sha256"] = prior_index["prior_index_sha256"]
    sealed["operational_context_sha256"] = operational_context[
        "operational_context_sha256"
    ]
    sealed["signal_record_sha256"] = _signal_record_hash(sealed)
    validate_signal_record(sealed)
    return sealed


def capture_latency_status(
    *, signal_frozen_at_utc: str, nominal_entry_open_utc: str
) -> str:
    frozen = _timestamp(signal_frozen_at_utc, field="signal_frozen_at_utc")
    entry = _timestamp(nominal_entry_open_utc, field="nominal_entry_open_utc")
    return "EXECUTABLE_AT_H022_X001_ENTRY" if frozen <= entry else "LATE_SIGNAL_FREEZE"
