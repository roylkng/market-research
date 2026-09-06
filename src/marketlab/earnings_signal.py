from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from marketlab.events import FinancialEvent

H002_SIGNAL_VERSION = "H002-UE-SIGN-v1"
H002_EXPECTATION_MODEL = "seasonal_naive_same_quarter_basic_eps_v1"
H002_FORMULA = "(actual_basic_eps - prior_year_same_quarter_basic_eps) / price_day_minus_2"

SignalState = Literal["POSITIVE", "NEGATIVE", "ZERO", "NO_SIGNAL"]


class EarningsSignalError(ValueError):
    """Raised when H002 inputs violate the frozen causal/time contract."""


@dataclass(frozen=True)
class EPSObservation:
    symbol: str
    reporting_period_end: str
    reporting_quarter: str
    accounting_basis: str
    basic_eps: float | None
    source_event_id: str
    source_version_id: str
    source_published_at_utc: str | None
    eps_basis_version: str | None


@dataclass(frozen=True)
class PriceObservation:
    close: float | None
    observed_at_utc: str | None
    source: str
    price_basis_version: str


@dataclass(frozen=True)
class H002Signal:
    signal_version: str
    expectation_model: str
    formula: str
    symbol: str
    decision_at_utc: str
    actual_basic_eps: float | None
    expected_basic_eps: float | None
    price_day_minus_2: float | None
    ue: float | None
    state: SignalState
    no_signal_reasons: tuple[str, ...]
    actual_source_event_id: str
    expected_source_event_id: str | None
    actual_source_version_id: str
    expected_source_version_id: str | None
    actual_source_published_at_utc: str | None
    expected_source_published_at_utc: str | None
    price_observed_at_utc: str | None
    eps_basis_version: str | None
    price_basis_version: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_utc(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EarningsSignalError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise EarningsSignalError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _parse_period_end(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise EarningsSignalError(f"{field} must use YYYY-MM-DD") from exc


def _exchange_date_to_iso(value: str, *, field: str) -> str:
    for pattern in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise EarningsSignalError(f"{field} must use DD-MM-YYYY or YYYY-MM-DD")


def _normalized(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def eps_observation_from_event(
    event: FinancialEvent,
    *,
    eps_basis_version: str | None,
    source_published_at_utc: str | None = None,
) -> EPSObservation:
    """Adapt one filing event to the H002 point-in-time EPS contract.

    Historical reconstruction capture time is never substituted for original
    publication time. If exchange publication provenance is absent, the caller
    must supply a separately source-grounded timestamp or the signal will be
    ineligible.
    """

    if not event.reporting_period_end:
        raise EarningsSignalError("financial event reporting_period_end is required")
    if not event.reporting_quarter:
        raise EarningsSignalError("financial event reporting_quarter is required")

    published = source_published_at_utc or event.provenance.exchange_published_at_utc
    if published is not None:
        _parse_utc(published, field="source_published_at_utc")

    return EPSObservation(
        symbol=event.symbol,
        reporting_period_end=_exchange_date_to_iso(
            event.reporting_period_end, field="financial_event.reporting_period_end"
        ),
        reporting_quarter=event.reporting_quarter,
        accounting_basis=event.accounting_basis,
        basic_eps=event.basic_eps,
        source_event_id=event.economic_event_id,
        source_version_id=event.version_id,
        source_published_at_utc=published,
        eps_basis_version=eps_basis_version,
    )


def _validate_identity(actual: EPSObservation, expected: EPSObservation) -> None:
    if actual.symbol.strip().upper() != expected.symbol.strip().upper():
        raise EarningsSignalError("actual and expected EPS symbols do not match")
    if _normalized(actual.accounting_basis) != _normalized(expected.accounting_basis):
        raise EarningsSignalError("actual and expected EPS accounting bases do not match")
    if _normalized(actual.reporting_quarter) != _normalized(expected.reporting_quarter):
        raise EarningsSignalError("actual and expected EPS reporting quarters do not match")

    actual_period = _parse_period_end(
        actual.reporting_period_end, field="actual.reporting_period_end"
    )
    expected_period = _parse_period_end(
        expected.reporting_period_end, field="expected.reporting_period_end"
    )
    if (
        actual_period.year - expected_period.year != 1
        or actual_period.month != expected_period.month
        or actual_period.day != expected_period.day
    ):
        raise EarningsSignalError(
            "expected EPS must be the same reporting-period end exactly one year earlier"
        )


def _no_signal(
    *,
    actual: EPSObservation,
    expected: EPSObservation | None,
    price: PriceObservation | None,
    decision_at_utc: str,
    reasons: list[str],
) -> H002Signal:
    return H002Signal(
        signal_version=H002_SIGNAL_VERSION,
        expectation_model=H002_EXPECTATION_MODEL,
        formula=H002_FORMULA,
        symbol=actual.symbol.strip().upper(),
        decision_at_utc=decision_at_utc,
        actual_basic_eps=actual.basic_eps,
        expected_basic_eps=expected.basic_eps if expected else None,
        price_day_minus_2=price.close if price else None,
        ue=None,
        state="NO_SIGNAL",
        no_signal_reasons=tuple(reasons),
        actual_source_event_id=actual.source_event_id,
        expected_source_event_id=expected.source_event_id if expected else None,
        actual_source_version_id=actual.source_version_id,
        expected_source_version_id=expected.source_version_id if expected else None,
        actual_source_published_at_utc=actual.source_published_at_utc,
        expected_source_published_at_utc=(expected.source_published_at_utc if expected else None),
        price_observed_at_utc=price.observed_at_utc if price else None,
        eps_basis_version=actual.eps_basis_version,
        price_basis_version=price.price_basis_version if price else None,
    )


def compute_h002_seasonal_ue(
    *,
    actual: EPSObservation,
    prior_year: EPSObservation | None,
    price_day_minus_2: PriceObservation | None,
    decision_at_utc: str,
) -> H002Signal:
    """Compute the frozen H002 v1 seasonal unexpected-earnings signal.

    Expected EPS is the basic EPS from the same quarter/period one year earlier.
    The prior observation must have been public before the current filing. Price
    construction is delegated to H002-C; this function only verifies that the
    supplied day-minus-2 observation predates the current filing.
    """

    decision_at = _parse_utc(decision_at_utc, field="decision_at_utc")

    if not actual.source_published_at_utc:
        return _no_signal(
            actual=actual,
            expected=prior_year,
            price=price_day_minus_2,
            decision_at_utc=decision_at_utc,
            reasons=["ACTUAL_PUBLICATION_TIMESTAMP_MISSING"],
        )
    actual_published = _parse_utc(
        actual.source_published_at_utc, field="actual.source_published_at_utc"
    )
    if decision_at < actual_published:
        raise EarningsSignalError("decision timestamp precedes current earnings publication")

    if prior_year is None:
        return _no_signal(
            actual=actual,
            expected=None,
            price=price_day_minus_2,
            decision_at_utc=decision_at_utc,
            reasons=["PRIOR_YEAR_EPS_MISSING"],
        )

    _validate_identity(actual, prior_year)

    if not prior_year.source_published_at_utc:
        return _no_signal(
            actual=actual,
            expected=prior_year,
            price=price_day_minus_2,
            decision_at_utc=decision_at_utc,
            reasons=["PRIOR_YEAR_PUBLICATION_TIMESTAMP_MISSING"],
        )
    prior_published = _parse_utc(
        prior_year.source_published_at_utc, field="prior_year.source_published_at_utc"
    )
    if prior_published >= actual_published:
        raise EarningsSignalError("expected EPS source was not public before current filing")

    reasons: list[str] = []
    if actual.basic_eps is None:
        reasons.append("ACTUAL_BASIC_EPS_MISSING")
    if prior_year.basic_eps is None:
        reasons.append("EXPECTED_BASIC_EPS_MISSING")

    if not actual.eps_basis_version or not prior_year.eps_basis_version:
        reasons.append("EPS_BASIS_UNRESOLVED")
    elif actual.eps_basis_version != prior_year.eps_basis_version:
        reasons.append("EPS_BASIS_VERSION_MISMATCH")

    if price_day_minus_2 is None or price_day_minus_2.close is None:
        reasons.append("PRICE_DAY_MINUS_2_MISSING")
    else:
        if price_day_minus_2.close <= 0:
            reasons.append("PRICE_DAY_MINUS_2_INVALID")
        if not price_day_minus_2.observed_at_utc:
            reasons.append("PRICE_TIMESTAMP_MISSING")
        else:
            price_observed = _parse_utc(
                price_day_minus_2.observed_at_utc, field="price_day_minus_2.observed_at_utc"
            )
            if price_observed >= actual_published:
                raise EarningsSignalError("day-minus-2 price must predate current earnings publication")
        if not price_day_minus_2.price_basis_version:
            reasons.append("PRICE_BASIS_VERSION_MISSING")

    if reasons:
        return _no_signal(
            actual=actual,
            expected=prior_year,
            price=price_day_minus_2,
            decision_at_utc=decision_at_utc,
            reasons=reasons,
        )

    assert actual.basic_eps is not None
    assert prior_year.basic_eps is not None
    assert price_day_minus_2 is not None
    assert price_day_minus_2.close is not None

    ue = (actual.basic_eps - prior_year.basic_eps) / price_day_minus_2.close
    if ue > 0:
        state: SignalState = "POSITIVE"
    elif ue < 0:
        state = "NEGATIVE"
    else:
        state = "ZERO"

    return H002Signal(
        signal_version=H002_SIGNAL_VERSION,
        expectation_model=H002_EXPECTATION_MODEL,
        formula=H002_FORMULA,
        symbol=actual.symbol.strip().upper(),
        decision_at_utc=decision_at_utc,
        actual_basic_eps=actual.basic_eps,
        expected_basic_eps=prior_year.basic_eps,
        price_day_minus_2=price_day_minus_2.close,
        ue=float(ue),
        state=state,
        no_signal_reasons=(),
        actual_source_event_id=actual.source_event_id,
        expected_source_event_id=prior_year.source_event_id,
        actual_source_version_id=actual.source_version_id,
        expected_source_version_id=prior_year.source_version_id,
        actual_source_published_at_utc=actual.source_published_at_utc,
        expected_source_published_at_utc=prior_year.source_published_at_utc,
        price_observed_at_utc=price_day_minus_2.observed_at_utc,
        eps_basis_version=actual.eps_basis_version,
        price_basis_version=price_day_minus_2.price_basis_version,
    )
