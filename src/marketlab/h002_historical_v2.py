from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, time as clock_time, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import yaml

from marketlab.preparation import _parse_exchange_timestamp

REPLAY_RULE_ID = "H002-HR002"
SOURCE_SIGNAL_RULE_ID = "H002-R001"
INTEGRATED_FIRST_PERIOD_END = date(2025, 3, 31)
IST = ZoneInfo("Asia/Kolkata")
SourceFeed = Literal["INTEGRATED", "LEGACY_FINANCIAL_RESULTS"]


class HistoricalReplayV2Error(ValueError):
    """Raised when the six-quarter replay would require point-in-time inference."""


@dataclass(frozen=True)
class MixedHistoricalFilingCandidate:
    symbol: str
    accounting_basis: str
    period_end: str
    exchange_published_at_utc: str
    source_url: str
    discovery_row_sha256: str
    source_feed: SourceFeed
    relating_to: str | None


@dataclass(frozen=True)
class MixedHistoricalFilingPair:
    symbol: str
    accounting_basis: str
    target: MixedHistoricalFilingCandidate
    baseline: MixedHistoricalFilingCandidate


def _canonical_hash(payload: Any) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HistoricalReplayV2Error("H002-HR002 payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def validate_historical_replay_v2_rule(document: dict[str, Any]) -> str:
    if not isinstance(document, dict):
        raise HistoricalReplayV2Error("H002-HR002 rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise HistoricalReplayV2Error("H002-HR002 rule must declare SHA-256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared:
        raise HistoricalReplayV2Error(
            f"H002-HR002 rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("id") != REPLAY_RULE_ID:
        raise HistoricalReplayV2Error(f"unexpected replay id: {document.get('id')}")
    if document.get("status") != "FROZEN_HISTORICAL_REPLAY":
        raise HistoricalReplayV2Error("H002-HR002 must remain frozen")
    if document.get("source_signal_rule_id") != SOURCE_SIGNAL_RULE_ID:
        raise HistoricalReplayV2Error("H002-HR002 must transport H002-R001")
    if document.get("evidence_mode", {}).get("prospective_equivalence_claimed") is not False:
        raise HistoricalReplayV2Error("historical replay cannot claim prospective equivalence")
    if document.get("evidence_mode", {}).get("live_capital") is not False:
        raise HistoricalReplayV2Error("historical replay must keep live capital disabled")
    if document.get("phase_separation", {}).get("outcome_data_forbidden_in_phase_a") is not True:
        raise HistoricalReplayV2Error("H002-HR002 Phase A must forbid outcome data")
    quarters = document.get("target_quarters")
    if not isinstance(quarters, list) or len(quarters) != 6:
        raise HistoricalReplayV2Error("H002-HR002 must keep the six pre-registered quarters")
    if document.get("cohort", {}).get("planned_observations") != 600:
        raise HistoricalReplayV2Error("H002-HR002 planned observation count must remain 600")
    return actual


def load_historical_replay_v2_rule(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    validate_historical_replay_v2_rule(document)
    return document


def historical_freeze_v2(
    target_period_end: str,
    *,
    offset_days: int,
    freeze_clock: str,
) -> str:
    try:
        target = date.fromisoformat(target_period_end)
    except ValueError as exc:
        raise HistoricalReplayV2Error(f"invalid target period: {target_period_end}") from exc
    try:
        raw_clock, zone_name = freeze_clock.rsplit(" ", 1)
        parsed_clock = clock_time.fromisoformat(raw_clock)
        zone = ZoneInfo(zone_name)
    except (ValueError, KeyError) as exc:
        raise HistoricalReplayV2Error(f"invalid freeze clock: {freeze_clock}") from exc
    freeze = datetime.combine(target + timedelta(days=offset_days), parsed_clock, tzinfo=zone)
    return freeze.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_date(value: Any, *, field: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise HistoricalReplayV2Error(f"{field} is required")
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            parsed = time.strptime(value.strip(), fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    raise HistoricalReplayV2Error(f"unsupported {field}: {value}")


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise HistoricalReplayV2Error("timestamp must include timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _row_hash(row: dict[str, Any]) -> str:
    return _canonical_hash(row)


def _normalize_legacy_basis(value: Any) -> str | None:
    token = str(value or "").strip().casefold()
    if token == "consolidated":
        return "Consolidated"
    if token in {"non-consolidated", "standalone", "non consolidated"}:
        return "Standalone"
    return None


def _normalize_integrated_basis(value: Any) -> str | None:
    token = str(value or "").strip().casefold()
    if token == "consolidated":
        return "Consolidated"
    if token == "standalone":
        return "Standalone"
    return None


def _integrated_rows(
    payload: Any,
    *,
    symbol: str,
    period_end: str,
    accounting_basis: str,
) -> list[MixedHistoricalFilingCandidate]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise HistoricalReplayV2Error("integrated filing payload does not contain a data list")
    wanted_symbol = symbol.strip().upper()
    wanted_period = date.fromisoformat(period_end)
    wanted_basis = accounting_basis.casefold()
    matches: list[MixedHistoricalFilingCandidate] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("type") or "").strip().casefold() != "integrated filing- financials":
            continue
        if str(row.get("symbol") or "").strip().upper() != wanted_symbol:
            continue
        basis = _normalize_integrated_basis(row.get("consolidated"))
        if basis is None or basis.casefold() != wanted_basis:
            continue
        try:
            observed_period = _parse_date(row.get("qe_Date"), field="integrated qe_Date")
        except HistoricalReplayV2Error:
            continue
        if observed_period != wanted_period:
            continue
        source_url = str(row.get("xbrl") or "").strip()
        if not source_url:
            continue
        timestamp_value = (
            row.get("broadcast_Date")
            or row.get("revised_Date")
            or row.get("revisedDate")
            or row.get("creation_Date")
            or row.get("creationDate")
        )
        try:
            timestamp = _parse_exchange_timestamp(timestamp_value)
        except Exception:
            continue
        matches.append(
            MixedHistoricalFilingCandidate(
                symbol=wanted_symbol,
                accounting_basis=basis,
                period_end=wanted_period.isoformat(),
                exchange_published_at_utc=_iso_utc(timestamp),
                source_url=source_url,
                discovery_row_sha256=_row_hash(row),
                source_feed="INTEGRATED",
                relating_to=str(row.get("relatingTo") or "").strip() or None,
            )
        )
    return sorted(matches, key=lambda item: (item.exchange_published_at_utc, item.source_url))


def _legacy_rows(
    payload: Any,
    *,
    symbol: str,
    period_end: str,
    accounting_basis: str,
) -> list[MixedHistoricalFilingCandidate]:
    rows = payload if isinstance(payload, list) else payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise HistoricalReplayV2Error("legacy financial-results payload does not contain a row list")
    wanted_symbol = symbol.strip().upper()
    wanted_period = date.fromisoformat(period_end)
    wanted_basis = accounting_basis.casefold()
    matches: list[MixedHistoricalFilingCandidate] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("symbol") or "").strip().upper() != wanted_symbol:
            continue
        if str(row.get("period") or "").strip().casefold() != "quarterly":
            continue
        basis = _normalize_legacy_basis(row.get("consolidated"))
        if basis is None or basis.casefold() != wanted_basis:
            continue
        try:
            observed_period = _parse_date(row.get("toDate"), field="legacy toDate")
        except HistoricalReplayV2Error:
            continue
        if observed_period != wanted_period:
            continue
        source_url = str(row.get("xbrl") or "").strip()
        if not source_url:
            continue
        try:
            timestamp = _parse_exchange_timestamp(row.get("broadCastDate"))
        except Exception:
            continue
        matches.append(
            MixedHistoricalFilingCandidate(
                symbol=wanted_symbol,
                accounting_basis=basis,
                period_end=wanted_period.isoformat(),
                exchange_published_at_utc=_iso_utc(timestamp),
                source_url=source_url,
                discovery_row_sha256=_row_hash(row),
                source_feed="LEGACY_FINANCIAL_RESULTS",
                relating_to=str(row.get("relatingTo") or "").strip() or None,
            )
        )
    return sorted(matches, key=lambda item: (item.exchange_published_at_utc, item.source_url))


def candidate_rows_for_period(
    *,
    integrated_payload: Any,
    legacy_payload: Any,
    symbol: str,
    period_end: str,
    accounting_basis: str,
) -> list[MixedHistoricalFilingCandidate]:
    period = date.fromisoformat(period_end)
    if period >= INTEGRATED_FIRST_PERIOD_END:
        return _integrated_rows(
            integrated_payload,
            symbol=symbol,
            period_end=period_end,
            accounting_basis=accounting_basis,
        )
    return _legacy_rows(
        legacy_payload,
        symbol=symbol,
        period_end=period_end,
        accounting_basis=accounting_basis,
    )


def _unique_at_timestamp(
    matches: list[MixedHistoricalFilingCandidate],
    *,
    timestamp: str,
    role: str,
) -> MixedHistoricalFilingCandidate:
    rows = [item for item in matches if item.exchange_published_at_utc == timestamp]
    urls = {item.source_url for item in rows}
    if len(urls) != 1:
        raise HistoricalReplayV2Error(
            f"ambiguous {role} filing at {timestamp}: {sorted(urls)}"
        )
    return rows[-1]


def select_mixed_historical_pair(
    *,
    integrated_payload: Any,
    legacy_payload: Any,
    symbol: str,
    target_period_end: str,
    baseline_period_end: str,
    freeze_at_utc: str,
) -> MixedHistoricalFilingPair | None:
    freeze = datetime.fromisoformat(freeze_at_utc).astimezone(UTC)
    for accounting_basis in ("Consolidated", "Standalone"):
        targets = candidate_rows_for_period(
            integrated_payload=integrated_payload,
            legacy_payload=legacy_payload,
            symbol=symbol,
            period_end=target_period_end,
            accounting_basis=accounting_basis,
        )
        baselines = candidate_rows_for_period(
            integrated_payload=integrated_payload,
            legacy_payload=legacy_payload,
            symbol=symbol,
            period_end=baseline_period_end,
            accounting_basis=accounting_basis,
        )
        baselines = [
            item
            for item in baselines
            if datetime.fromisoformat(item.exchange_published_at_utc).astimezone(UTC) <= freeze
        ]
        if not targets or not baselines:
            continue
        first_target = _unique_at_timestamp(
            targets,
            timestamp=targets[0].exchange_published_at_utc,
            role="first target",
        )
        latest_baseline = _unique_at_timestamp(
            baselines,
            timestamp=baselines[-1].exchange_published_at_utc,
            role="latest baseline as-of freeze",
        )
        if datetime.fromisoformat(first_target.exchange_published_at_utc).astimezone(UTC) <= freeze:
            raise HistoricalReplayV2Error(
                f"target filing for {symbol} was already public at the historical freeze"
            )
        return MixedHistoricalFilingPair(
            symbol=symbol.strip().upper(),
            accounting_basis=accounting_basis,
            target=first_target,
            baseline=latest_baseline,
        )
    return None
