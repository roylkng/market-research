from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time as clock_time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import yaml

from marketlab.events import HISTORICAL_RECONSTRUCTION, FinancialEvent
from marketlab.h002 import (
    EXPECTATION_MODEL_VERSION,
    SIGNAL_VERSION,
    PriceReference,
    SeasonalEPSExpectation,
)
from marketlab.preparation import PreparationError, _parse_exchange_timestamp

REPLAY_RULE_ID = "H002-HR001"
SOURCE_SIGNAL_RULE_ID = "H002-R001"
IST = ZoneInfo("Asia/Kolkata")
DEFAULT_FREEZE_CLOCK = clock_time(20, 41, 38, 303000)
DEFAULT_FREEZE_CLOCK_TEXT = "20:41:38.303000 Asia/Kolkata"
FREEZE_CLOCK_BASIS = "FY27_Q2_expectation_bundle_anchored_at_2026-09-06T15:11:38.303000Z"
ReplayBucket = Literal["POSITIVE", "ZERO", "NEGATIVE", "NO_SIGNAL"]


class HistoricalReplayError(ValueError):
    """Raised when H002 historical replay inputs violate the frozen replay contract."""


@dataclass(frozen=True)
class HistoricalFilingCandidate:
    symbol: str
    accounting_basis: str
    period_end: str
    exchange_published_at_utc: str
    source_url: str
    discovery_row_sha256: str


@dataclass(frozen=True)
class HistoricalFilingPair:
    symbol: str
    accounting_basis: str
    target: HistoricalFilingCandidate
    baseline: HistoricalFilingCandidate


@dataclass(frozen=True)
class HistoricalSignalResult:
    schema_version: int
    replay_rule_id: str
    source_signal_rule_id: str
    signal_version: str
    event_id: str
    event_version_id: str
    expectation_id: str
    symbol: str
    historical_freeze_at_utc: str
    reconstructed_at_utc: str
    actual_basic_eps: float | None
    expected_eps: float | None
    surprise_eps: float | None
    price_day_minus_2: float | None
    ue: float | None
    bucket: ReplayBucket
    no_signal_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        raise HistoricalReplayError(
            "historical replay payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def validate_historical_replay_rule(document: dict[str, Any]) -> str:
    if not isinstance(document, dict):
        raise HistoricalReplayError("historical replay rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise HistoricalReplayError("historical replay rule must declare sha256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared:
        raise HistoricalReplayError(
            f"historical replay rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("id") != REPLAY_RULE_ID:
        raise HistoricalReplayError(
            f"unexpected historical replay rule id: {document.get('id')}"
        )
    if document.get("status") != "FROZEN_HISTORICAL_REPLAY":
        raise HistoricalReplayError("historical replay rule must remain frozen")
    if document.get("source_signal_rule_id") != SOURCE_SIGNAL_RULE_ID:
        raise HistoricalReplayError("historical replay must reference H002-R001")
    evidence_mode = document.get("evidence_mode", {})
    if evidence_mode.get("actual_event_mode") != HISTORICAL_RECONSTRUCTION:
        raise HistoricalReplayError("historical replay event mode must remain reconstruction")
    if evidence_mode.get("prospective_equivalence_claimed") is not False:
        raise HistoricalReplayError("historical replay cannot claim prospective equivalence")
    if evidence_mode.get("live_capital") is not False:
        raise HistoricalReplayError("historical replay must keep live_capital false")
    freeze_policy = document.get("freeze_policy", {})
    if freeze_policy.get("freeze_clock") != DEFAULT_FREEZE_CLOCK_TEXT:
        raise HistoricalReplayError("historical replay freeze clock differs from frozen anchor")
    if freeze_policy.get("freeze_clock_basis") != FREEZE_CLOCK_BASIS:
        raise HistoricalReplayError("historical replay freeze-clock basis differs from anchor")
    if document.get("phase_separation", {}).get("outcome_data_forbidden_in_phase_a") is not True:
        raise HistoricalReplayError("phase A must forbid post-filing outcome data")
    return actual


def load_and_validate_historical_replay_rule(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    validate_historical_replay_rule(document)
    return document


def historical_freeze_at(
    target_period_end: str,
    *,
    offset_days: int = -24,
) -> str:
    try:
        target = date.fromisoformat(target_period_end)
    except ValueError as exc:
        raise HistoricalReplayError(
            f"invalid target_period_end: {target_period_end}"
        ) from exc
    freeze_day = target + timedelta(days=offset_days)
    freeze = datetime.combine(freeze_day, DEFAULT_FREEZE_CLOCK, tzinfo=IST)
    return freeze.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_period(value: Any) -> date:
    if not isinstance(value, str) or not value.strip():
        raise HistoricalReplayError("filing period is required")
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            parsed = time.strptime(value.strip(), fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    raise HistoricalReplayError(f"unsupported filing period: {value}")


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise HistoricalReplayError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise HistoricalReplayError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _official_timestamp(row: dict[str, Any]) -> datetime:
    last_error: PreparationError | None = None
    for key in (
        "broadcast_Date",
        "revised_Date",
        "revisedDate",
        "creation_Date",
        "creationDate",
    ):
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return _parse_exchange_timestamp(value)
        except PreparationError as exc:
            last_error = exc
    raise HistoricalReplayError(
        f"filing row has no parseable official timestamp: {last_error}"
    )


def _candidate_rows(
    payload: Any,
    *,
    symbol: str,
    period_end: str,
    accounting_basis: str,
) -> list[HistoricalFilingCandidate]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise HistoricalReplayError("NSE result discovery payload does not contain a data list")
    wanted_symbol = symbol.strip().upper()
    wanted_basis = accounting_basis.strip().casefold()
    wanted_period = date.fromisoformat(period_end)
    matches: list[HistoricalFilingCandidate] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("type") or "").strip().casefold() != "integrated filing- financials":
            continue
        if str(row.get("symbol") or "").strip().upper() != wanted_symbol:
            continue
        if str(row.get("consolidated") or "").strip().casefold() != wanted_basis:
            continue
        try:
            observed_period = _parse_period(row.get("qe_Date"))
            published = _official_timestamp(row)
        except HistoricalReplayError:
            continue
        if observed_period != wanted_period:
            continue
        source_url = str(row.get("xbrl") or "").strip()
        if not source_url:
            continue
        matches.append(
            HistoricalFilingCandidate(
                symbol=wanted_symbol,
                accounting_basis=accounting_basis,
                period_end=wanted_period.isoformat(),
                exchange_published_at_utc=published.astimezone(UTC).isoformat().replace(
                    "+00:00", "Z"
                ),
                source_url=source_url,
                discovery_row_sha256=_canonical_hash(row),
            )
        )
    matches.sort(key=lambda item: (item.exchange_published_at_utc, item.source_url))
    return matches


def _unique_at_timestamp(
    matches: list[HistoricalFilingCandidate],
    *,
    latest: bool,
    role: str,
    symbol: str,
    accounting_basis: str,
) -> HistoricalFilingCandidate | None:
    if not matches:
        return None
    timestamp = matches[-1].exchange_published_at_utc if latest else matches[0].exchange_published_at_utc
    same_time = [item for item in matches if item.exchange_published_at_utc == timestamp]
    urls = {item.source_url for item in same_time}
    if len(urls) != 1:
        raise HistoricalReplayError(
            f"ambiguous {role} filing for {symbol}/{accounting_basis}: {sorted(urls)}"
        )
    return same_time[-1] if latest else same_time[0]


def _first_target(
    payload: Any,
    *,
    symbol: str,
    period_end: str,
    accounting_basis: str,
) -> HistoricalFilingCandidate | None:
    matches = _candidate_rows(
        payload,
        symbol=symbol,
        period_end=period_end,
        accounting_basis=accounting_basis,
    )
    return _unique_at_timestamp(
        matches,
        latest=False,
        role="first target",
        symbol=symbol,
        accounting_basis=accounting_basis,
    )


def _latest_baseline_as_of(
    payload: Any,
    *,
    symbol: str,
    period_end: str,
    accounting_basis: str,
    freeze_at_utc: str,
) -> HistoricalFilingCandidate | None:
    freeze = _timestamp(freeze_at_utc, "freeze_at_utc")
    matches = [
        item
        for item in _candidate_rows(
            payload,
            symbol=symbol,
            period_end=period_end,
            accounting_basis=accounting_basis,
        )
        if _timestamp(item.exchange_published_at_utc, "baseline publication") <= freeze
    ]
    return _unique_at_timestamp(
        matches,
        latest=True,
        role="baseline as-of freeze",
        symbol=symbol,
        accounting_basis=accounting_basis,
    )


def select_historical_filing_pair(
    payload: Any,
    *,
    symbol: str,
    target_period_end: str,
    baseline_period_end: str,
    freeze_at_utc: str,
) -> HistoricalFilingPair | None:
    freeze = _timestamp(freeze_at_utc, "freeze_at_utc")
    for accounting_basis in ("Consolidated", "Standalone"):
        target = _first_target(
            payload,
            symbol=symbol,
            period_end=target_period_end,
            accounting_basis=accounting_basis,
        )
        baseline = _latest_baseline_as_of(
            payload,
            symbol=symbol,
            period_end=baseline_period_end,
            accounting_basis=accounting_basis,
            freeze_at_utc=freeze_at_utc,
        )
        if target is None or baseline is None:
            continue
        if _timestamp(target.exchange_published_at_utc, "target publication") <= freeze:
            raise HistoricalReplayError(
                f"target filing for {symbol} was published on/before the historical freeze"
            )
        return HistoricalFilingPair(
            symbol=symbol.strip().upper(),
            accounting_basis=accounting_basis,
            target=target,
            baseline=baseline,
        )
    return None


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HistoricalReplayError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise HistoricalReplayError(f"{field} must be a finite number")
    return result


def _decimal_result(value: Decimal, field: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise HistoricalReplayError(f"{field} must be finite")
    if result == 0 and value != 0:
        raise HistoricalReplayError(f"{field} underflows float representation")
    return result


def _validate_expectation_shape(expectation: SeasonalEPSExpectation) -> None:
    if expectation.rule_id != SOURCE_SIGNAL_RULE_ID:
        raise HistoricalReplayError("historical replay expectation must use H002-R001")
    if expectation.model_version != EXPECTATION_MODEL_VERSION:
        raise HistoricalReplayError("unexpected H002 expectation model version")
    if expectation.status == "READY":
        if expectation.expected_eps is None or expectation.baseline_basic_eps is None:
            raise HistoricalReplayError("READY expectation is missing EPS values")
        expected = float(
            Decimal(str(expectation.baseline_basic_eps))
            * Decimal(str(expectation.corporate_action_factor))
        )
        if not math.isclose(expectation.expected_eps, expected, rel_tol=0.0, abs_tol=1e-12):
            raise HistoricalReplayError(
                "historical expectation does not match H002-R001 formula"
            )
    elif expectation.status == "NO_SIGNAL":
        if expectation.expected_eps is not None:
            raise HistoricalReplayError("NO_SIGNAL expectation cannot contain expected EPS")
    else:
        raise HistoricalReplayError(f"unsupported expectation status: {expectation.status}")


def _result(
    *,
    actual_event: FinancialEvent,
    expectation: SeasonalEPSExpectation,
    reconstructed_at: datetime,
    actual_basic_eps: float | None,
    expected_eps: float | None,
    surprise_eps: float | None,
    price_day_minus_2: float | None,
    ue: float | None,
    bucket: ReplayBucket,
    no_signal_reason: str | None,
) -> HistoricalSignalResult:
    return HistoricalSignalResult(
        schema_version=1,
        replay_rule_id=REPLAY_RULE_ID,
        source_signal_rule_id=SOURCE_SIGNAL_RULE_ID,
        signal_version=SIGNAL_VERSION,
        event_id=actual_event.economic_event_id,
        event_version_id=actual_event.version_id,
        expectation_id=expectation.expectation_id,
        symbol=actual_event.symbol,
        historical_freeze_at_utc=expectation.expectation_as_of_utc,
        reconstructed_at_utc=reconstructed_at.isoformat().replace("+00:00", "Z"),
        actual_basic_eps=actual_basic_eps,
        expected_eps=expected_eps,
        surprise_eps=surprise_eps,
        price_day_minus_2=price_day_minus_2,
        ue=ue,
        bucket=bucket,
        no_signal_reason=no_signal_reason,
    )


def score_h002_historical_replay(
    actual_event: FinancialEvent,
    expectation: SeasonalEPSExpectation,
    price_reference: PriceReference,
    *,
    reconstructed_at_utc: str,
) -> HistoricalSignalResult:
    if actual_event.mode != HISTORICAL_RECONSTRUCTION:
        raise HistoricalReplayError(
            "historical replay actual event must remain HISTORICAL_RECONSTRUCTION"
        )
    publication_value = actual_event.provenance.exchange_published_at_utc
    if not publication_value:
        raise HistoricalReplayError(
            "historical event is missing verified exchange publication timestamp"
        )
    publication = _timestamp(publication_value, "exchange_published_at_utc")
    reconstructed_at = _timestamp(reconstructed_at_utc, "reconstructed_at_utc")
    captured_at = _timestamp(actual_event.provenance.captured_at_utc, "actual captured_at_utc")
    freeze_at = _timestamp(expectation.expectation_as_of_utc, "expectation_as_of_utc")
    baseline_available = _timestamp(
        expectation.baseline_available_at_utc, "baseline_available_at_utc"
    )
    price_at = _timestamp(price_reference.close_timestamp_utc, "price close timestamp")

    if reconstructed_at < captured_at:
        raise HistoricalReplayError("historical replay cannot be scored before source capture")
    if freeze_at >= publication:
        raise HistoricalReplayError("historical freeze must strictly predate target filing")
    if baseline_available > freeze_at:
        raise HistoricalReplayError("baseline was not available by the historical freeze")
    if price_at >= publication:
        raise HistoricalReplayError("price reference must strictly predate target filing")

    if actual_event.symbol.upper() != expectation.symbol.upper():
        raise HistoricalReplayError("actual event symbol does not match expectation")
    if actual_event.symbol.upper() != price_reference.symbol.upper():
        raise HistoricalReplayError("price reference symbol does not match actual event")
    actual_period = _parse_period(actual_event.reporting_period_end)
    if actual_period.isoformat() != expectation.target_period_end:
        raise HistoricalReplayError("actual reporting period does not match replay target")
    if (
        (actual_event.reporting_quarter or "").strip().casefold()
        != expectation.target_quarter.strip().casefold()
    ):
        raise HistoricalReplayError("actual reporting quarter does not match expectation")
    if (
        actual_event.accounting_basis.strip().casefold()
        != expectation.accounting_basis.strip().casefold()
    ):
        raise HistoricalReplayError("actual accounting basis does not match expectation")
    if price_reference.role != "price_day_minus_2":
        raise HistoricalReplayError("price reference role must be price_day_minus_2")
    if not price_reference.corporate_action_version.strip():
        raise HistoricalReplayError("price corporate-action version is required")
    if not price_reference.source.strip():
        raise HistoricalReplayError("price reference source is required")
    _validate_expectation_shape(expectation)

    trading_date = _parse_period(price_reference.trading_date)
    if trading_date != price_at.astimezone(IST).date():
        raise HistoricalReplayError(
            "price trading date does not match exchange-local timestamp"
        )
    if trading_date >= publication.astimezone(IST).date():
        raise HistoricalReplayError("reference trading date must precede publication date")

    if expectation.status == "NO_SIGNAL":
        return _result(
            actual_event=actual_event,
            expectation=expectation,
            reconstructed_at=reconstructed_at,
            actual_basic_eps=actual_event.basic_eps,
            expected_eps=None,
            surprise_eps=None,
            price_day_minus_2=price_reference.close_price,
            ue=None,
            bucket="NO_SIGNAL",
            no_signal_reason=expectation.no_signal_reason,
        )
    if actual_event.basic_eps is None:
        return _result(
            actual_event=actual_event,
            expectation=expectation,
            reconstructed_at=reconstructed_at,
            actual_basic_eps=None,
            expected_eps=expectation.expected_eps,
            surprise_eps=None,
            price_day_minus_2=price_reference.close_price,
            ue=None,
            bucket="NO_SIGNAL",
            no_signal_reason="missing_actual_basic_eps",
        )
    actual_eps = _finite(actual_event.basic_eps, "actual_basic_eps")
    if price_reference.close_price is None:
        return _result(
            actual_event=actual_event,
            expectation=expectation,
            reconstructed_at=reconstructed_at,
            actual_basic_eps=actual_eps,
            expected_eps=expectation.expected_eps,
            surprise_eps=None,
            price_day_minus_2=None,
            ue=None,
            bucket="NO_SIGNAL",
            no_signal_reason="missing_price_day_minus_2",
        )
    price = _finite(price_reference.close_price, "price_day_minus_2")
    if price <= 0:
        raise HistoricalReplayError("price_day_minus_2 must be positive")
    if expectation.expected_eps is None:
        raise HistoricalReplayError("READY expectation cannot have missing expected_eps")

    surprise = Decimal(str(actual_eps)) - Decimal(str(expectation.expected_eps))
    ue_decimal = surprise / Decimal(str(price))
    surprise_value = _decimal_result(surprise, "surprise_eps")
    ue_value = _decimal_result(ue_decimal, "ue")
    if ue_decimal > 0:
        bucket: ReplayBucket = "POSITIVE"
    elif ue_decimal < 0:
        bucket = "NEGATIVE"
    else:
        bucket = "ZERO"
    return _result(
        actual_event=actual_event,
        expectation=expectation,
        reconstructed_at=reconstructed_at,
        actual_basic_eps=actual_eps,
        expected_eps=expectation.expected_eps,
        surprise_eps=surprise_value,
        price_day_minus_2=price,
        ue=ue_value,
        bucket=bucket,
        no_signal_reason=None,
    )
