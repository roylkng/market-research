from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

H002_SIGNAL_VERSION = "H002-UE-v1"
H002_RULE_SHA256 = "24eb8325216e68db8e3f14db440a0f470f9f576a3d1aea034b570812c70686ff"

H002_RULE: dict[str, Any] = {
    "hypothesis_id": "H002",
    "signal_version": H002_SIGNAL_VERSION,
    "universe_rule_id": "U001",
    "actual_eps_field": "basic_eps",
    "expected_eps_model": {
        "type": "seasonal_naive_v1",
        "formula": "eps_t_minus_4",
        "same_accounting_basis": True,
        "same_reporting_quarter": True,
    },
    "surprise_formula": "actual_eps - eps_t_minus_4",
    "scaling": {
        "type": "price",
        "formula": "surprise / price_day_minus_2",
        "price_reference": (
            "official_close_second_prior_nse_trading_session_before_exchange_"
            "publication_local_date"
        ),
    },
    "bucket_rule": {
        "positive": "ue > 0",
        "zero": "ue == 0",
        "negative": "ue < 0",
    },
    "winsorization": "none",
    "missing_policy": "NO_SIGNAL",
    "corporate_action_policy": (
        "NO_SIGNAL unless pre_event_comparability_adjustment_is_versioned"
    ),
    "post_event_inputs_forbidden": True,
}


class EarningsSignalError(ValueError):
    """Raised when a supposedly frozen H002 input violates timing or identity rules."""


@dataclass(frozen=True)
class H002SignalInput:
    symbol: str
    current_event_id: str
    current_exchange_published_at_utc: str
    current_accounting_basis: str
    current_reporting_quarter: str
    actual_basic_eps: float | None
    prior_event_id: str | None
    prior_exchange_published_at_utc: str | None
    prior_accounting_basis: str | None
    prior_reporting_quarter: str | None
    prior_year_basic_eps: float | None
    price_day_minus_2: float | None
    price_reference_session: str | None
    price_source: str | None
    corporate_action_comparable: bool
    corporate_action_version: str | None = None


@dataclass(frozen=True)
class H002Signal:
    hypothesis_id: str
    signal_version: str
    rule_sha256: str
    symbol: str
    current_event_id: str
    decision_timestamp_utc: str
    expected_eps: float | None
    actual_eps: float | None
    unexpected_eps: float | None
    price_day_minus_2: float | None
    ue: float | None
    bucket: str
    eligible: bool
    no_signal_reasons: tuple[str, ...]
    prior_event_id: str | None
    price_reference_session: str | None
    price_source: str | None
    corporate_action_version: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_rule_sha256(rule: dict[str, Any] | None = None) -> str:
    payload = H002_RULE if rule is None else rule
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_frozen_rule() -> None:
    actual = canonical_rule_sha256()
    if actual != H002_RULE_SHA256:
        raise EarningsSignalError(
            "H002 frozen rule changed without a signal-version change: "
            f"expected {H002_RULE_SHA256}, got {actual}"
        )


def _utc(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EarningsSignalError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise EarningsSignalError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _normalized_token(value: str | None) -> str | None:
    return " ".join(value.strip().casefold().split()) if value else None


def compute_h002_signal(values: H002SignalInput) -> H002Signal:
    """Compute H002-UE-v1 without inventing missing or incomparable inputs.

    The signal is intentionally narrow. Expected EPS is the same reporting
    quarter one year earlier. The surprise is scaled by the official closing
    price two NSE sessions before the current filing date. No winsorization,
    momentum, valuation, guidance, or post-result information is permitted.
    """

    validate_frozen_rule()
    current_published = _utc(
        values.current_exchange_published_at_utc,
        field="current_exchange_published_at_utc",
    )

    reasons: list[str] = []
    if values.actual_basic_eps is None:
        reasons.append("missing_actual_basic_eps")
    if values.prior_event_id is None:
        reasons.append("missing_prior_same_quarter_event")
    if values.prior_year_basic_eps is None:
        reasons.append("missing_prior_year_basic_eps")
    if values.prior_exchange_published_at_utc is None:
        reasons.append("missing_prior_publication_timestamp")
    else:
        prior_published = _utc(
            values.prior_exchange_published_at_utc,
            field="prior_exchange_published_at_utc",
        )
        if prior_published >= current_published:
            raise EarningsSignalError(
                "prior EPS source was not public before the current filing"
            )

    current_basis = _normalized_token(values.current_accounting_basis)
    prior_basis = _normalized_token(values.prior_accounting_basis)
    if prior_basis is None:
        reasons.append("missing_prior_accounting_basis")
    elif current_basis != prior_basis:
        reasons.append("accounting_basis_mismatch")

    current_quarter = _normalized_token(values.current_reporting_quarter)
    prior_quarter = _normalized_token(values.prior_reporting_quarter)
    if prior_quarter is None:
        reasons.append("missing_prior_reporting_quarter")
    elif current_quarter != prior_quarter:
        reasons.append("reporting_quarter_mismatch")

    if values.price_day_minus_2 is None:
        reasons.append("missing_price_day_minus_2")
    elif values.price_day_minus_2 <= 0:
        reasons.append("invalid_price_day_minus_2")
    if not values.price_reference_session:
        reasons.append("missing_price_reference_session")
    if not values.price_source:
        reasons.append("missing_price_source")

    if not values.corporate_action_comparable:
        reasons.append("eps_not_comparable_across_corporate_action")
    elif values.corporate_action_version is None:
        reasons.append("missing_corporate_action_version")

    if reasons:
        return H002Signal(
            hypothesis_id="H002",
            signal_version=H002_SIGNAL_VERSION,
            rule_sha256=H002_RULE_SHA256,
            symbol=values.symbol.upper(),
            current_event_id=values.current_event_id,
            decision_timestamp_utc=current_published.isoformat().replace("+00:00", "Z"),
            expected_eps=values.prior_year_basic_eps,
            actual_eps=values.actual_basic_eps,
            unexpected_eps=None,
            price_day_minus_2=values.price_day_minus_2,
            ue=None,
            bucket="NO_SIGNAL",
            eligible=False,
            no_signal_reasons=tuple(reasons),
            prior_event_id=values.prior_event_id,
            price_reference_session=values.price_reference_session,
            price_source=values.price_source,
            corporate_action_version=values.corporate_action_version,
        )

    actual = float(values.actual_basic_eps)
    expected = float(values.prior_year_basic_eps)
    price = float(values.price_day_minus_2)
    surprise = actual - expected
    ue = surprise / price
    if ue > 0:
        bucket = "POSITIVE"
    elif ue < 0:
        bucket = "NEGATIVE"
    else:
        bucket = "ZERO"

    return H002Signal(
        hypothesis_id="H002",
        signal_version=H002_SIGNAL_VERSION,
        rule_sha256=H002_RULE_SHA256,
        symbol=values.symbol.upper(),
        current_event_id=values.current_event_id,
        decision_timestamp_utc=current_published.isoformat().replace("+00:00", "Z"),
        expected_eps=expected,
        actual_eps=actual,
        unexpected_eps=surprise,
        price_day_minus_2=price,
        ue=ue,
        bucket=bucket,
        eligible=True,
        no_signal_reasons=(),
        prior_event_id=values.prior_event_id,
        price_reference_session=values.price_reference_session,
        price_source=values.price_source,
        corporate_action_version=values.corporate_action_version,
    )
