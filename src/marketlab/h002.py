from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import yaml

from marketlab.events import PROSPECTIVE, FinancialEvent

EXPECTATION_MODEL_VERSION = "seasonal_same_quarter_basic_eps_v1"
SIGNAL_VERSION = "ue_price_normalized_v1"
RULE_ID = "H002-R001"

SignalBucket = Literal["POSITIVE", "ZERO", "NEGATIVE", "NO_SIGNAL"]


class H002SignalError(ValueError):
    """Raised when H002 inputs violate the frozen point-in-time contract."""


@dataclass(frozen=True)
class SeasonalEPSExpectation:
    schema_version: int
    rule_id: str
    model_version: str
    expectation_id: str
    symbol: str
    target_period_end: str
    target_quarter: str
    accounting_basis: str
    baseline_event_id: str
    baseline_event_version_id: str
    baseline_period_end: str | None
    baseline_basic_eps: float | None
    baseline_available_at_utc: str
    expectation_as_of_utc: str
    corporate_action_factor: float
    corporate_action_version: str
    expected_eps: float | None
    status: Literal["READY", "NO_SIGNAL"]
    no_signal_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PriceReference:
    symbol: str
    role: str
    trading_date: str
    close_timestamp_utc: str
    close_price: float | None
    source: str
    corporate_action_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class H002SignalResult:
    schema_version: int
    rule_id: str
    signal_version: str
    event_id: str
    event_version_id: str
    expectation_id: str
    symbol: str
    scored_at_utc: str
    actual_basic_eps: float | None
    expected_eps: float | None
    surprise_eps: float | None
    price_day_minus_2: float | None
    ue: float | None
    bucket: SignalBucket
    no_signal_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise H002SignalError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H002SignalError(f"{field} must include timezone: {value}")
    return parsed.astimezone(UTC)


def _parse_period_end(value: str | None, *, field: str) -> date:
    if not value:
        raise H002SignalError(f"{field} is required")
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        pass
    for fmt in ("%d-%m-%Y", "%d-%b-%Y"):
        try:
            parsed = time.strptime(value, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except (TypeError, ValueError):
            continue
    raise H002SignalError(f"unsupported {field}: {value}")


def _one_year_apart(baseline: date, target: date) -> bool:
    return (
        target.year == baseline.year + 1
        and target.month == baseline.month
        and target.day == baseline.day
    )


def _canonical_hash(payload: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise H002SignalError("canonical payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise H002SignalError(f"{field} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise H002SignalError(f"{field} must be a finite number") from exc
    if not math.isfinite(result):
        raise H002SignalError(f"{field} must be a finite number")
    return result


def _decimal_result(value: Decimal, *, field: str) -> float:
    result = _finite_number(float(value), field=field)
    if result == 0 and value != 0:
        raise H002SignalError(f"{field} underflows the output numeric representation")
    return result


def _expectation_digest(expectation: SeasonalEPSExpectation) -> str:
    payload = expectation.to_dict()
    payload.pop("expectation_id")
    return _canonical_hash(payload)[:24]


def _validate_expectation(expectation: SeasonalEPSExpectation) -> None:
    if (
        expectation.schema_version != 2
        or expectation.rule_id != RULE_ID
        or expectation.model_version != EXPECTATION_MODEL_VERSION
    ):
        raise H002SignalError("unsupported expectation schema, model or rule")
    if expectation.expectation_id != _expectation_digest(expectation):
        raise H002SignalError("expectation identity does not match its complete payload")
    factor = _finite_number(expectation.corporate_action_factor, field="corporate_action_factor")
    if factor <= 0:
        raise H002SignalError("corporate_action_factor must be positive")
    if expectation.baseline_basic_eps is None:
        if (
            expectation.status != "NO_SIGNAL"
            or expectation.expected_eps is not None
            or expectation.no_signal_reason != "missing_baseline_basic_eps"
        ):
            raise H002SignalError("missing baseline EPS requires a consistent NO_SIGNAL record")
        return
    _finite_number(expectation.baseline_basic_eps, field="baseline_basic_eps")
    expected = _decimal_result(
        Decimal(str(expectation.baseline_basic_eps))
        * Decimal(str(expectation.corporate_action_factor)),
        field="expected_eps",
    )
    if (
        expectation.status != "READY"
        or expectation.no_signal_reason is not None
        or _finite_number(expectation.expected_eps, field="expected_eps") != expected
    ):
        raise H002SignalError("expectation does not match the frozen EPS calculation")


def validate_rule_document(document: dict[str, Any]) -> str:
    """Validate the frozen H002 rule and return its canonical SHA-256."""

    if not isinstance(document, dict):
        raise H002SignalError("H002 rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise H002SignalError("H002 rule must declare a 64-character sha256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared:
        raise H002SignalError(
            f"H002 rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("id") != RULE_ID:
        raise H002SignalError(f"unexpected H002 rule id: {document.get('id')}")
    if document.get("status") != "FROZEN":
        raise H002SignalError("H002 signal rule must remain FROZEN during prospective testing")
    if document.get("decision", {}).get("live_capital") is not False:
        raise H002SignalError("H002 signal rule must keep live_capital: false")
    return actual


def load_and_validate_rule(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    validate_rule_document(document)
    return document


def build_seasonal_expectation(
    baseline_event: FinancialEvent,
    *,
    target_period_end: str,
    target_quarter: str,
    target_accounting_basis: str,
    baseline_available_at_utc: str | None,
    expectation_as_of_utc: str,
    corporate_action_factor: float,
    corporate_action_version: str,
) -> SeasonalEPSExpectation:
    """Build the frozen H002 expected-EPS record from prior-year same-quarter EPS.

    Historical reconstruction capture time is not treated as historical availability.
    If the baseline event lacks a prospective exchange timestamp, the caller must
    provide independently verified `baseline_available_at_utc`.
    """

    if not corporate_action_version.strip():
        raise H002SignalError("corporate_action_version is required")
    _finite_number(corporate_action_factor, field="corporate_action_factor")
    if corporate_action_factor <= 0:
        raise H002SignalError("corporate_action_factor must be positive")

    baseline_available_at_utc = (
        baseline_event.provenance.exchange_published_at_utc or baseline_available_at_utc
    )
    if not baseline_available_at_utc:
        raise H002SignalError(
            "baseline availability is required; historical reconstruction capture time is not valid"
        )

    baseline_available = _parse_timestamp(
        baseline_available_at_utc, field="baseline_available_at_utc"
    )
    expectation_as_of = _parse_timestamp(expectation_as_of_utc, field="expectation_as_of_utc")
    if baseline_available > expectation_as_of:
        raise H002SignalError("baseline became available after expectation_as_of")

    baseline_period = _parse_period_end(
        baseline_event.reporting_period_end, field="baseline reporting_period_end"
    )
    target_period = _parse_period_end(target_period_end, field="target_period_end")
    if not _one_year_apart(baseline_period, target_period):
        raise H002SignalError(
            "baseline event must be the same quarter exactly one year before target period"
        )
    if (baseline_event.reporting_quarter or "").strip().casefold() != target_quarter.strip().casefold():
        raise H002SignalError("baseline reporting quarter does not match target quarter")
    if baseline_event.accounting_basis.strip().casefold() != target_accounting_basis.strip().casefold():
        raise H002SignalError("baseline accounting basis does not match target accounting basis")

    expected_eps: float | None
    status: Literal["READY", "NO_SIGNAL"]
    reason: str | None
    if baseline_event.basic_eps is None:
        expected_eps = None
        status = "NO_SIGNAL"
        reason = "missing_baseline_basic_eps"
    else:
        _finite_number(baseline_event.basic_eps, field="baseline_basic_eps")
        expected_eps = _decimal_result(
            Decimal(str(baseline_event.basic_eps)) * Decimal(str(corporate_action_factor)),
            field="expected_eps",
        )
        status = "READY"
        reason = None

    expectation = SeasonalEPSExpectation(
        schema_version=2,
        rule_id=RULE_ID,
        model_version=EXPECTATION_MODEL_VERSION,
        expectation_id="",
        symbol=baseline_event.symbol.upper(),
        target_period_end=target_period.isoformat(),
        target_quarter=target_quarter,
        accounting_basis=target_accounting_basis,
        baseline_event_id=baseline_event.economic_event_id,
        baseline_event_version_id=baseline_event.version_id,
        baseline_period_end=baseline_period.isoformat(),
        baseline_basic_eps=baseline_event.basic_eps,
        baseline_available_at_utc=baseline_available.isoformat().replace("+00:00", "Z"),
        expectation_as_of_utc=expectation_as_of.isoformat().replace("+00:00", "Z"),
        corporate_action_factor=corporate_action_factor,
        corporate_action_version=corporate_action_version,
        expected_eps=expected_eps,
        status=status,
        no_signal_reason=reason,
    )
    return replace(expectation, expectation_id=_expectation_digest(expectation))


def score_h002(
    actual_event: FinancialEvent,
    expectation: SeasonalEPSExpectation,
    price_reference: PriceReference,
    *,
    scored_at_utc: str,
) -> H002SignalResult:
    """Score H002 without opening or simulating any paper position."""

    if actual_event.mode != PROSPECTIVE:
        raise H002SignalError("actual event must be PROSPECTIVE")
    publication_value = actual_event.provenance.exchange_published_at_utc
    if not publication_value:
        raise H002SignalError("prospective event is missing exchange publication timestamp")
    publication = _parse_timestamp(publication_value, field="exchange_published_at_utc")
    scored_at = _parse_timestamp(scored_at_utc, field="scored_at_utc")
    captured_at = _parse_timestamp(
        actual_event.provenance.captured_at_utc, field="actual captured_at_utc"
    )
    expectation_as_of = _parse_timestamp(
        expectation.expectation_as_of_utc, field="expectation_as_of_utc"
    )
    baseline_available = _parse_timestamp(
        expectation.baseline_available_at_utc, field="baseline_available_at_utc"
    )
    price_at = _parse_timestamp(price_reference.close_timestamp_utc, field="price close timestamp")

    if expectation_as_of >= publication:
        raise H002SignalError("expectation_as_of must be strictly before current filing publication")
    if baseline_available >= publication:
        raise H002SignalError("baseline availability must be strictly before current filing publication")
    if price_at >= publication:
        raise H002SignalError("price reference must be strictly before current filing publication")
    if scored_at < publication:
        raise H002SignalError("H002 cannot be scored before the filing is published")
    if scored_at < captured_at:
        raise H002SignalError("H002 cannot be scored before local filing capture")

    if actual_event.symbol.upper() != expectation.symbol.upper():
        raise H002SignalError("actual event symbol does not match expectation")
    if actual_event.symbol.upper() != price_reference.symbol.upper():
        raise H002SignalError("price reference symbol does not match actual event")
    actual_period = _parse_period_end(
        actual_event.reporting_period_end, field="actual reporting_period_end"
    )
    if actual_period.isoformat() != expectation.target_period_end:
        raise H002SignalError("actual reporting period does not match expectation target")
    if (actual_event.reporting_quarter or "").strip().casefold() != expectation.target_quarter.strip().casefold():
        raise H002SignalError("actual reporting quarter does not match expectation")
    if actual_event.accounting_basis.strip().casefold() != expectation.accounting_basis.strip().casefold():
        raise H002SignalError("actual accounting basis does not match expectation")
    if price_reference.role != "price_day_minus_2":
        raise H002SignalError("price reference role must be price_day_minus_2")
    if not price_reference.corporate_action_version.strip():
        raise H002SignalError("price corporate_action_version is required")
    _validate_expectation(expectation)
    if actual_event.basic_eps is not None:
        _finite_number(actual_event.basic_eps, field="actual_basic_eps")
    if price_reference.close_price is not None:
        _finite_number(price_reference.close_price, field="price_day_minus_2")
        if price_reference.close_price <= 0:
            raise H002SignalError("price_day_minus_2 must be positive")
    if not isinstance(price_reference.source, str) or not price_reference.source.strip():
        raise H002SignalError("price reference source is required")
    trading_date = _parse_period_end(price_reference.trading_date, field="price trading_date")
    exchange_timezone = ZoneInfo("Asia/Kolkata")
    if trading_date != price_at.astimezone(exchange_timezone).date():
        raise H002SignalError("price trading_date does not match its exchange-local timestamp")
    if trading_date >= publication.astimezone(exchange_timezone).date():
        raise H002SignalError("reference trading date must precede the publication date")
    if expectation.status == "NO_SIGNAL":
        return H002SignalResult(
            schema_version=1,
            rule_id=RULE_ID,
            signal_version=SIGNAL_VERSION,
            event_id=actual_event.economic_event_id,
            event_version_id=actual_event.version_id,
            expectation_id=expectation.expectation_id,
            symbol=actual_event.symbol,
            scored_at_utc=scored_at.isoformat().replace("+00:00", "Z"),
            actual_basic_eps=actual_event.basic_eps,
            expected_eps=None,
            surprise_eps=None,
            price_day_minus_2=price_reference.close_price,
            ue=None,
            bucket="NO_SIGNAL",
            no_signal_reason=expectation.no_signal_reason,
        )
    if actual_event.basic_eps is None:
        return H002SignalResult(
            schema_version=1,
            rule_id=RULE_ID,
            signal_version=SIGNAL_VERSION,
            event_id=actual_event.economic_event_id,
            event_version_id=actual_event.version_id,
            expectation_id=expectation.expectation_id,
            symbol=actual_event.symbol,
            scored_at_utc=scored_at.isoformat().replace("+00:00", "Z"),
            actual_basic_eps=None,
            expected_eps=expectation.expected_eps,
            surprise_eps=None,
            price_day_minus_2=price_reference.close_price,
            ue=None,
            bucket="NO_SIGNAL",
            no_signal_reason="missing_actual_basic_eps",
        )
    if price_reference.close_price is None:
        return H002SignalResult(
            schema_version=1,
            rule_id=RULE_ID,
            signal_version=SIGNAL_VERSION,
            event_id=actual_event.economic_event_id,
            event_version_id=actual_event.version_id,
            expectation_id=expectation.expectation_id,
            symbol=actual_event.symbol,
            scored_at_utc=scored_at.isoformat().replace("+00:00", "Z"),
            actual_basic_eps=actual_event.basic_eps,
            expected_eps=expectation.expected_eps,
            surprise_eps=None,
            price_day_minus_2=None,
            ue=None,
            bucket="NO_SIGNAL",
            no_signal_reason="missing_price_day_minus_2",
        )
    if expectation.expected_eps is None:
        raise H002SignalError("READY expectation cannot have missing expected_eps")

    surprise = Decimal(str(actual_event.basic_eps)) - Decimal(str(expectation.expected_eps))
    ue_decimal = surprise / Decimal(str(price_reference.close_price))
    surprise_value = _decimal_result(surprise, field="surprise_eps")
    ue_value = _decimal_result(ue_decimal, field="ue")
    if ue_decimal > 0:
        bucket: SignalBucket = "POSITIVE"
    elif ue_decimal < 0:
        bucket = "NEGATIVE"
    else:
        bucket = "ZERO"

    return H002SignalResult(
        schema_version=1,
        rule_id=RULE_ID,
        signal_version=SIGNAL_VERSION,
        event_id=actual_event.economic_event_id,
        event_version_id=actual_event.version_id,
        expectation_id=expectation.expectation_id,
        symbol=actual_event.symbol,
        scored_at_utc=scored_at.isoformat().replace("+00:00", "Z"),
        actual_basic_eps=actual_event.basic_eps,
        expected_eps=expectation.expected_eps,
        surprise_eps=surprise_value,
        price_day_minus_2=price_reference.close_price,
        ue=ue_value,
        bucket=bucket,
        no_signal_reason=None,
    )
