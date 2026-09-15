from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from marketlab.h024_acquisition import canonical_hash
from marketlab.h024_events import PRIMARY_EVENT_STATUS, validate_event_ledger
from marketlab.h024_historical import HORIZONS, ROUND_TRIP_COST_PP, blocked_actions
from marketlab.h024_prospective import (
    PROTOCOL_ID,
    H024ProspectiveError,
    source_by_id,
    validate_calendar,
    validate_source_ledger,
)

ENTRY_LEDGER_VERSION = 1
OUTCOME_LEDGER_VERSION = 1
ENTRY_READY = "READY"
ENTRY_BLOCKED = "BLOCKED"
ENTRY_BLOCK_REASONS = frozenset({"MISSING_ENTRY_STOCK_BAR", "ENTRY_IDENTITY_DRIFT"})
OUTCOME_COMPLETE = "COMPLETE"
OUTCOME_BLOCKED = "BLOCKED"
OUTCOME_BLOCK_REASONS = frozenset(
    {
        "ENTRY_OBSERVATION_BLOCKED",
        "MISSING_EXIT_STOCK_BAR",
        "EXIT_IDENTITY_DRIFT",
        "CORPORATE_ACTION_AUDIT_UNRESOLVED",
        "SHARE_CHANGING_CORPORATE_ACTION",
    }
)
PRIMARY_POPULATION_ELIGIBLE = "ELIGIBLE"
PRIMARY_POPULATION_RETROACTIVE_GAP = "EXCLUDED_RETROACTIVE_PREENTRY_REVISION_GAP"


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


def _new_ledger(version: int) -> dict[str, Any]:
    ledger = {
        "schema_version": version,
        "protocol_id": PROTOCOL_ID,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def new_entry_ledger() -> dict[str, Any]:
    return _new_ledger(ENTRY_LEDGER_VERSION)


def new_outcome_ledger() -> dict[str, Any]:
    return _new_ledger(OUTCOME_LEDGER_VERSION)


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


def event_by_id(event_ledger: dict[str, Any], event_id: str) -> dict[str, Any]:
    validate_event_ledger(event_ledger)
    matches = [row for row in event_ledger["records"] if row["event_id"] == event_id]
    if len(matches) != 1:
        raise H024ProspectiveError(f"H024 event not uniquely present: {event_id}")
    return dict(matches[0])


def horizon_exit_session(
    calendar: dict[str, Any], *, entry_session: str, horizon: int
) -> dict[str, Any] | None:
    if horizon not in HORIZONS:
        raise H024ProspectiveError(f"unsupported H024 horizon: {horizon}")
    sessions = validate_calendar(calendar)
    indices = [index for index, row in enumerate(sessions) if row["session_date"] == entry_session]
    if len(indices) != 1:
        raise H024ProspectiveError(
            f"H024 entry session is not uniquely present in calendar: {entry_session}"
        )
    target = indices[0] + horizon - 1
    return None if target >= len(sessions) else dict(sessions[target])


def _validate_market_bar(
    bar: dict[str, Any],
    *,
    kind: str,
    expected_session: str,
    expected_symbol: str | None = None,
) -> None:
    required = {
        "session_date",
        "open_price",
        "close_price",
        "source_url",
        "raw_sha256",
    }
    if not isinstance(bar, dict) or not required.issubset(bar):
        raise H024ProspectiveError(f"H024 {kind} market bar is incomplete")
    if str(bar["session_date"]) != expected_session:
        raise H024ProspectiveError(f"H024 {kind} market-bar session mismatch")
    if not isinstance(bar["source_url"], str) or not bar["source_url"].startswith("https://"):
        raise H024ProspectiveError(f"H024 {kind} market-bar URL is invalid")
    if not _is_sha256(bar["raw_sha256"]):
        raise H024ProspectiveError(f"H024 {kind} market-bar hash is invalid")
    for field in ("open_price", "close_price"):
        value = float(bar[field])
        if not math.isfinite(value) or value <= 0:
            raise H024ProspectiveError(f"H024 {kind} {field} is invalid")
    if expected_symbol is not None:
        if str(bar.get("symbol") or "").strip().upper() != expected_symbol.upper():
            raise H024ProspectiveError(f"H024 {kind} symbol mismatch")
        if not str(bar.get("isin") or "").strip():
            raise H024ProspectiveError(f"H024 {kind} ISIN is missing")
        if str(bar.get("series") or "").strip().upper() != "EQ":
            raise H024ProspectiveError(f"H024 {kind} series is not EQ")
    else:
        if str(bar.get("benchmark_id") or "") != "nifty_500":
            raise H024ProspectiveError(f"H024 {kind} benchmark id is not Nifty 500")


def entry_observation_id(event_id: str) -> str:
    if not _is_sha256(event_id):
        raise H024ProspectiveError("H024 entry event id is invalid")
    return canonical_hash(
        {"protocol_id": PROTOCOL_ID, "event_id": event_id, "record_type": "ENTRY"}
    )


def build_entry_record(
    *,
    event: dict[str, Any],
    stock_bar: dict[str, Any] | None,
    benchmark_bar: dict[str, Any],
    observed_at_utc: str,
) -> dict[str, Any]:
    if event.get("status") != PRIMARY_EVENT_STATUS:
        raise H024ProspectiveError("H024 entry observation requires a primary eligible event")
    event_id = str(event["event_id"])
    symbol = str(event["symbol"]).strip().upper()
    entry_session = str(event["planned_entry_session"])
    entry_isin = str(event["investability"].get("entry_isin") or "").strip()
    if not entry_isin:
        raise H024ProspectiveError("H024 primary event lacks frozen entry ISIN")
    _validate_market_bar(
        benchmark_bar,
        kind="entry benchmark",
        expected_session=entry_session,
    )
    observed = _timestamp(observed_at_utc, field="entry.observed_at_utc")

    block_reason: str | None = None
    normalized_stock: dict[str, Any] | None = None
    if stock_bar is None:
        block_reason = "MISSING_ENTRY_STOCK_BAR"
    else:
        _validate_market_bar(
            stock_bar,
            kind="entry stock",
            expected_session=entry_session,
            expected_symbol=symbol,
        )
        normalized_stock = dict(stock_bar)
        if str(stock_bar["isin"]) != entry_isin:
            block_reason = "ENTRY_IDENTITY_DRIFT"

    record: dict[str, Any] = {
        "entry_observation_id": entry_observation_id(event_id),
        "event_id": event_id,
        "symbol": symbol,
        "entry_session": entry_session,
        "entry_isin": entry_isin,
        "status": ENTRY_READY if block_reason is None else ENTRY_BLOCKED,
        "block_reason": block_reason,
        "stock_bar": normalized_stock,
        "benchmark_bar": dict(benchmark_bar),
        "observed_at_utc": _utc_text(observed),
    }
    record["entry_record_sha256"] = _record_hash(record, "entry_record_sha256")
    validate_entry_record(record)
    return record


def validate_entry_record(record: dict[str, Any]) -> None:
    required = {
        "entry_observation_id",
        "event_id",
        "symbol",
        "entry_session",
        "entry_isin",
        "status",
        "block_reason",
        "stock_bar",
        "benchmark_bar",
        "observed_at_utc",
        "entry_record_sha256",
    }
    if not isinstance(record, dict) or not required.issubset(record):
        raise H024ProspectiveError("H024 entry observation is incomplete")
    if not _is_sha256(record["event_id"]) or not _is_sha256(record["entry_observation_id"]):
        raise H024ProspectiveError("H024 entry observation identity is invalid")
    if record["entry_observation_id"] != entry_observation_id(str(record["event_id"])):
        raise H024ProspectiveError("H024 entry observation id mismatch")
    if not str(record["symbol"]).strip() or not str(record["entry_isin"]).strip():
        raise H024ProspectiveError("H024 entry observation symbol/ISIN is missing")
    if record["status"] not in {ENTRY_READY, ENTRY_BLOCKED}:
        raise H024ProspectiveError("H024 entry observation status is invalid")
    reason = record["block_reason"]
    if record["status"] == ENTRY_READY:
        if reason is not None or record["stock_bar"] is None:
            raise H024ProspectiveError("H024 ready entry observation is inconsistent")
    elif reason not in ENTRY_BLOCK_REASONS:
        raise H024ProspectiveError("H024 blocked entry observation reason is invalid")
    _validate_market_bar(
        record["benchmark_bar"],
        kind="entry benchmark",
        expected_session=str(record["entry_session"]),
    )
    if record["stock_bar"] is not None:
        _validate_market_bar(
            record["stock_bar"],
            kind="entry stock",
            expected_session=str(record["entry_session"]),
            expected_symbol=str(record["symbol"]),
        )
        if record["status"] == ENTRY_READY and str(record["stock_bar"]["isin"]) != str(
            record["entry_isin"]
        ):
            raise H024ProspectiveError("H024 ready entry observation has ISIN drift")
    _timestamp(record["observed_at_utc"], field="entry.observed_at_utc")
    if record["entry_record_sha256"] != _record_hash(record, "entry_record_sha256"):
        raise H024ProspectiveError("H024 entry observation digest mismatch")


def validate_entry_ledger(ledger: dict[str, Any]) -> None:
    _validate_ledger_header(ledger, ENTRY_LEDGER_VERSION, "entry")
    seen: set[str] = set()
    prior_key: tuple[str, str] | None = None
    for record in ledger["records"]:
        validate_entry_record(record)
        event_id = str(record["event_id"])
        if event_id in seen:
            raise H024ProspectiveError("duplicate H024 entry observation event")
        seen.add(event_id)
        key = (str(record["entry_session"]), str(record["symbol"]))
        if prior_key is not None and key < prior_key:
            raise H024ProspectiveError("H024 entry ledger is not canonical-sorted")
        prior_key = key


def append_entry(ledger: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    validate_entry_ledger(ledger)
    validate_entry_record(record)
    event_id = str(record["event_id"])
    existing = [row for row in ledger["records"] if row["event_id"] == event_id]
    if existing:
        if existing[0] != record:
            raise H024ProspectiveError(f"{event_id}: H024 entry observation is immutable")
        return ledger
    records = [dict(row) for row in ledger["records"]] + [record]
    records.sort(key=lambda row: (str(row["entry_session"]), str(row["symbol"])))
    result = dict(ledger)
    result["records"] = records
    result["record_count"] = len(records)
    result["ledger_sha256"] = _ledger_hash(result)
    validate_entry_ledger(result)
    return result


def entry_by_event(ledger: dict[str, Any], event_id: str) -> dict[str, Any] | None:
    validate_entry_ledger(ledger)
    matches = [row for row in ledger["records"] if row["event_id"] == event_id]
    if not matches:
        return None
    if len(matches) != 1:
        raise H024ProspectiveError(f"duplicate H024 entry observation: {event_id}")
    return dict(matches[0])


def outcome_id(event_id: str, horizon: int) -> str:
    if not _is_sha256(event_id) or horizon not in HORIZONS:
        raise H024ProspectiveError("H024 outcome identity is invalid")
    return canonical_hash(
        {
            "protocol_id": PROTOCOL_ID,
            "event_id": event_id,
            "horizon_sessions": horizon,
            "record_type": "OUTCOME",
        }
    )


def _gross_return_pct(entry: float, exit_value: float) -> float:
    result = (exit_value / entry - 1.0) * 100.0
    if not math.isfinite(result):
        raise H024ProspectiveError("computed H024 prospective return is non-finite")
    return result


def build_outcome_record(
    *,
    event: dict[str, Any],
    entry_record: dict[str, Any],
    horizon: int,
    exit_session: str,
    exit_stock_bar: dict[str, Any] | None,
    exit_benchmark_bar: dict[str, Any],
    corporate_action_audit: dict[str, Any],
    corporate_action_source_url: str,
    corporate_action_raw_sha256: str,
    observed_at_utc: str,
) -> dict[str, Any]:
    if event.get("status") != PRIMARY_EVENT_STATUS:
        raise H024ProspectiveError("H024 outcome requires a primary eligible event")
    validate_entry_record(entry_record)
    event_id = str(event["event_id"])
    symbol = str(event["symbol"]).strip().upper()
    if entry_record["event_id"] != event_id or entry_record["symbol"] != symbol:
        raise H024ProspectiveError("H024 outcome entry observation does not match event")
    if horizon not in HORIZONS:
        raise H024ProspectiveError(f"unsupported H024 horizon: {horizon}")
    if not isinstance(corporate_action_source_url, str) or not corporate_action_source_url.startswith(
        "https://"
    ):
        raise H024ProspectiveError("H024 corporate-action source URL is invalid")
    if not _is_sha256(corporate_action_raw_sha256):
        raise H024ProspectiveError("H024 corporate-action raw hash is invalid")
    _validate_market_bar(
        exit_benchmark_bar,
        kind="exit benchmark",
        expected_session=exit_session,
    )
    observed = _timestamp(observed_at_utc, field="outcome.observed_at_utc")

    action_status = str(corporate_action_audit.get("status") or "")
    action_rows = corporate_action_audit.get("actions", [])
    unresolved = corporate_action_audit.get("unresolved_subjects", [])
    if action_status not in {"READY", "UNRESOLVED"} or not isinstance(action_rows, list):
        raise H024ProspectiveError("H024 corporate-action audit is invalid")
    if not isinstance(unresolved, list):
        raise H024ProspectiveError("H024 corporate-action unresolved subjects are invalid")
    relevant_actions: list[dict[str, str]] = []
    if action_status == "READY":
        relevant_actions = list(
            blocked_actions(
                corporate_action_audit,
                entry_date=str(entry_record["entry_session"]),
                exit_date=exit_session,
            )
        )

    block_reason: str | None = None
    normalized_exit_stock: dict[str, Any] | None = None
    if entry_record["status"] != ENTRY_READY:
        block_reason = "ENTRY_OBSERVATION_BLOCKED"
    elif action_status != "READY":
        block_reason = "CORPORATE_ACTION_AUDIT_UNRESOLVED"
    elif relevant_actions:
        block_reason = "SHARE_CHANGING_CORPORATE_ACTION"
    elif exit_stock_bar is None:
        block_reason = "MISSING_EXIT_STOCK_BAR"
    else:
        _validate_market_bar(
            exit_stock_bar,
            kind="exit stock",
            expected_session=exit_session,
            expected_symbol=symbol,
        )
        normalized_exit_stock = dict(exit_stock_bar)
        if str(exit_stock_bar["isin"]) != str(entry_record["entry_isin"]):
            block_reason = "EXIT_IDENTITY_DRIFT"

    stock_return: float | None = None
    benchmark_return: float | None = None
    gross_excess: float | None = None
    cost_adjusted: float | None = None
    beat_benchmark: bool | None = None
    if block_reason is None:
        assert entry_record["stock_bar"] is not None
        assert normalized_exit_stock is not None
        stock_return = _gross_return_pct(
            float(entry_record["stock_bar"]["open_price"]),
            float(normalized_exit_stock["close_price"]),
        )
        benchmark_return = _gross_return_pct(
            float(entry_record["benchmark_bar"]["open_price"]),
            float(exit_benchmark_bar["close_price"]),
        )
        gross_excess = stock_return - benchmark_return
        cost_adjusted = gross_excess - ROUND_TRIP_COST_PP
        beat_benchmark = gross_excess > 0

    record: dict[str, Any] = {
        "outcome_id": outcome_id(event_id, horizon),
        "event_id": event_id,
        "symbol": symbol,
        "horizon_sessions": horizon,
        "entry_session": str(entry_record["entry_session"]),
        "exit_session": exit_session,
        "status": OUTCOME_COMPLETE if block_reason is None else OUTCOME_BLOCKED,
        "block_reason": block_reason,
        "entry_observation_id": str(entry_record["entry_observation_id"]),
        "entry_record_sha256": str(entry_record["entry_record_sha256"]),
        "exit_stock_bar": normalized_exit_stock,
        "exit_benchmark_bar": dict(exit_benchmark_bar),
        "corporate_action_audit": {
            "status": action_status,
            "actions": action_rows,
            "unresolved_subjects": unresolved,
            "relevant_blocked_actions": relevant_actions,
            "source_url": corporate_action_source_url,
            "raw_sha256": corporate_action_raw_sha256,
        },
        "stock_return_pct": stock_return,
        "benchmark_return_pct": benchmark_return,
        "gross_excess_pp": gross_excess,
        "cost_adjusted_excess_pp": cost_adjusted,
        "beat_benchmark": beat_benchmark,
        "round_trip_cost_stress_pp": ROUND_TRIP_COST_PP,
        "observed_at_utc": _utc_text(observed),
    }
    record["outcome_record_sha256"] = _record_hash(record, "outcome_record_sha256")
    validate_outcome_record(record)
    return record


def validate_outcome_record(record: dict[str, Any]) -> None:
    required = {
        "outcome_id",
        "event_id",
        "symbol",
        "horizon_sessions",
        "entry_session",
        "exit_session",
        "status",
        "block_reason",
        "entry_observation_id",
        "entry_record_sha256",
        "exit_stock_bar",
        "exit_benchmark_bar",
        "corporate_action_audit",
        "stock_return_pct",
        "benchmark_return_pct",
        "gross_excess_pp",
        "cost_adjusted_excess_pp",
        "beat_benchmark",
        "round_trip_cost_stress_pp",
        "observed_at_utc",
        "outcome_record_sha256",
    }
    if not isinstance(record, dict) or not required.issubset(record):
        raise H024ProspectiveError("H024 outcome record is incomplete")
    horizon = record["horizon_sessions"]
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon not in HORIZONS:
        raise H024ProspectiveError("H024 outcome horizon is invalid")
    if not _is_sha256(record["event_id"]) or not _is_sha256(record["outcome_id"]):
        raise H024ProspectiveError("H024 outcome identity is invalid")
    if record["outcome_id"] != outcome_id(str(record["event_id"]), horizon):
        raise H024ProspectiveError("H024 outcome id mismatch")
    if not _is_sha256(record["entry_observation_id"]) or not _is_sha256(
        record["entry_record_sha256"]
    ):
        raise H024ProspectiveError("H024 outcome entry reference is invalid")
    if record["status"] not in {OUTCOME_COMPLETE, OUTCOME_BLOCKED}:
        raise H024ProspectiveError("H024 outcome status is invalid")
    reason = record["block_reason"]
    if record["status"] == OUTCOME_COMPLETE:
        if reason is not None or record["exit_stock_bar"] is None:
            raise H024ProspectiveError("H024 complete outcome is inconsistent")
        numeric_fields = (
            "stock_return_pct",
            "benchmark_return_pct",
            "gross_excess_pp",
            "cost_adjusted_excess_pp",
        )
        if any(record[field] is None or not math.isfinite(float(record[field])) for field in numeric_fields):
            raise H024ProspectiveError("H024 complete outcome returns are invalid")
        if not isinstance(record["beat_benchmark"], bool):
            raise H024ProspectiveError("H024 complete outcome beat flag is invalid")
    else:
        if reason not in OUTCOME_BLOCK_REASONS:
            raise H024ProspectiveError("H024 blocked outcome reason is invalid")
        if any(
            record[field] is not None
            for field in (
                "stock_return_pct",
                "benchmark_return_pct",
                "gross_excess_pp",
                "cost_adjusted_excess_pp",
                "beat_benchmark",
            )
        ):
            raise H024ProspectiveError("H024 blocked outcome carries return data")
    if float(record["round_trip_cost_stress_pp"]) != ROUND_TRIP_COST_PP:
        raise H024ProspectiveError("H024 outcome implementation-cost stress drifted")
    _validate_market_bar(
        record["exit_benchmark_bar"],
        kind="exit benchmark",
        expected_session=str(record["exit_session"]),
    )
    if record["exit_stock_bar"] is not None:
        _validate_market_bar(
            record["exit_stock_bar"],
            kind="exit stock",
            expected_session=str(record["exit_session"]),
            expected_symbol=str(record["symbol"]),
        )
    action = record["corporate_action_audit"]
    required_action = {
        "status",
        "actions",
        "unresolved_subjects",
        "relevant_blocked_actions",
        "source_url",
        "raw_sha256",
    }
    if not isinstance(action, dict) or not required_action.issubset(action):
        raise H024ProspectiveError("H024 outcome corporate-action audit is incomplete")
    if action["status"] not in {"READY", "UNRESOLVED"}:
        raise H024ProspectiveError("H024 outcome corporate-action status is invalid")
    if not isinstance(action["source_url"], str) or not action["source_url"].startswith("https://"):
        raise H024ProspectiveError("H024 outcome corporate-action URL is invalid")
    if not _is_sha256(action["raw_sha256"]):
        raise H024ProspectiveError("H024 outcome corporate-action hash is invalid")
    _timestamp(record["observed_at_utc"], field="outcome.observed_at_utc")
    if record["outcome_record_sha256"] != _record_hash(record, "outcome_record_sha256"):
        raise H024ProspectiveError("H024 outcome record digest mismatch")


def validate_outcome_ledger(ledger: dict[str, Any]) -> None:
    _validate_ledger_header(ledger, OUTCOME_LEDGER_VERSION, "outcome")
    seen: set[tuple[str, int]] = set()
    prior_key: tuple[str, str, int] | None = None
    for record in ledger["records"]:
        validate_outcome_record(record)
        identity = (str(record["event_id"]), int(record["horizon_sessions"]))
        if identity in seen:
            raise H024ProspectiveError("duplicate H024 event/horizon outcome")
        seen.add(identity)
        key = (
            str(record["entry_session"]),
            str(record["symbol"]),
            int(record["horizon_sessions"]),
        )
        if prior_key is not None and key < prior_key:
            raise H024ProspectiveError("H024 outcome ledger is not canonical-sorted")
        prior_key = key


def append_outcome(ledger: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    validate_outcome_ledger(ledger)
    validate_outcome_record(record)
    identity = (str(record["event_id"]), int(record["horizon_sessions"]))
    existing = [
        row
        for row in ledger["records"]
        if (str(row["event_id"]), int(row["horizon_sessions"])) == identity
    ]
    if existing:
        if existing[0] != record:
            raise H024ProspectiveError(f"{identity}: H024 outcome is immutable")
        return ledger
    records = [dict(row) for row in ledger["records"]] + [record]
    records.sort(
        key=lambda row: (
            str(row["entry_session"]),
            str(row["symbol"]),
            int(row["horizon_sessions"]),
        )
    )
    result = dict(ledger)
    result["records"] = records
    result["record_count"] = len(records)
    result["ledger_sha256"] = _ledger_hash(result)
    validate_outcome_ledger(result)
    return result


def outcome_exists(ledger: dict[str, Any], event_id: str, horizon: int) -> bool:
    validate_outcome_ledger(ledger)
    return any(
        row["event_id"] == event_id and int(row["horizon_sessions"]) == horizon
        for row in ledger["records"]
    )


def current_primary_population_audit(
    *, event: dict[str, Any], source_ledger: dict[str, Any]
) -> dict[str, Any]:
    validate_source_ledger(source_ledger)
    if event.get("status") != PRIMARY_EVENT_STATUS:
        raise H024ProspectiveError("H024 primary-population audit requires a primary event")
    symbol = str(event["symbol"]).strip().upper()
    entry_open = _timestamp(event["planned_entry_open_utc"], field="event.entry_open")
    event_frozen = _timestamp(event["event_frozen_at_utc"], field="event.frozen")
    candidates = [str(value) for value in event["candidate_source_ids"]]
    candidate_blockers: dict[str, list[str]] = {}
    late_revision_ids: set[str] = set()
    all_revision_ids: set[str] = set()
    revisions = [
        row
        for row in source_ledger["records"]
        if str(row["source"]["symbol"]).strip().upper() == symbol
        and row["source"]["submission_type"] == "Revision"
    ]
    for candidate_id in candidates:
        candidate = source_by_id(source_ledger, candidate_id)
        original_time = _timestamp(
            candidate["exchange_disseminated_at_utc"], field="candidate.disseminated"
        )
        blockers: list[str] = []
        for revision_row in revisions:
            revision = revision_row["source"]
            revision_time = _timestamp(
                revision["exchange_disseminated_at_utc"], field="revision.disseminated"
            )
            if not (original_time < revision_time < entry_open):
                continue
            revision_id = str(revision["source_id"])
            blockers.append(revision_id)
            all_revision_ids.add(revision_id)
            first_seen = _timestamp(revision_row["first_seen_at_utc"], field="revision.first_seen")
            if first_seen > event_frozen:
                late_revision_ids.add(revision_id)
        candidate_blockers[candidate_id] = sorted(set(blockers))

    surviving = sorted(
        candidate_id for candidate_id in candidates if not candidate_blockers[candidate_id]
    )
    status = (
        PRIMARY_POPULATION_ELIGIBLE
        if surviving
        else PRIMARY_POPULATION_RETROACTIVE_GAP
    )
    return {
        "status": status,
        "surviving_candidate_source_ids": surviving,
        "official_preentry_revision_source_ids": sorted(all_revision_ids),
        "late_discovered_preentry_revision_source_ids": sorted(late_revision_ids),
        "candidate_blockers": {
            key: candidate_blockers[key] for key in sorted(candidate_blockers)
        },
        "sealed_eligible_source_ids": sorted(str(value) for value in event["eligible_source_ids"]),
        "provenance_drift": surviving
        != sorted(str(value) for value in event["eligible_source_ids"]),
    }
