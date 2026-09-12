from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

ANALYST_ACTIONS = {
    "REJECT",
    "WATCH",
    "PORTFOLIO_ELIGIBLE",
    "HOLD_REVIEW",
}
VALIDATION_ROLES = {"DEVELOPMENT", "PROSPECTIVE_VALIDATION"}
CALIBRATION_STATUSES = {
    "UNAVAILABLE",
    "UNCALIBRATED",
    "EXPERIMENTAL",
    "CALIBRATED",
}
INVALIDATION_SEVERITIES = {"SOFT", "HARD"}
SIGNAL_KEYS = ("h019", "h021", "h013", "h020")
FORECAST_NUMERIC_FIELDS = (
    "expected_benchmark_relative_return_pct",
    "p10_benchmark_relative_return_pct",
    "p50_benchmark_relative_return_pct",
    "p90_benchmark_relative_return_pct",
    "probability_beat_benchmark",
    "expected_mae_pct",
)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _number_or_none(value: object) -> bool:
    return value is None or (
        isinstance(value, (int, float)) and not isinstance(value, bool)
    )


def _canonical_payload(decision: dict) -> dict:
    payload = dict(decision)
    payload.pop("decision_id", None)
    payload.pop("record_sha256", None)
    return payload


def decision_sha256(decision: dict) -> str:
    payload = json.dumps(
        _canonical_payload(decision),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_decision(decision: dict, *, require_seal: bool = True) -> list[str]:
    errors: list[str] = []
    if decision.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if decision.get("object_type") != "ANALYST_DECISION":
        errors.append("object_type must equal ANALYST_DECISION")
    if decision.get("live_capital_allowed") is not False:
        errors.append("live_capital_allowed must be false")

    timestamp = _parse_timestamp(decision.get("decision_timestamp"))
    if timestamp is None:
        errors.append("decision_timestamp must be an offset-aware ISO timestamp")

    for field in ("symbol", "isin", "company_name", "sector", "benchmark"):
        value = decision.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    horizon = decision.get("horizon_sessions")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon <= 0:
        errors.append("horizon_sessions must be a positive integer")

    role = decision.get("validation_role")
    if role not in VALIDATION_ROLES:
        errors.append(f"validation_role must be one of {sorted(VALIDATION_ROLES)}")

    thesis = decision.get("business_thesis")
    if not isinstance(thesis, str) or not thesis.strip():
        errors.append("business_thesis must be a non-empty string")

    evidence = decision.get("thesis_evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("thesis_evidence must be a non-empty list")
    else:
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"thesis_evidence[{index}] must be an object")
                continue
            available_at = _parse_timestamp(item.get("available_at"))
            if available_at is None:
                errors.append(
                    f"thesis_evidence[{index}].available_at must be offset-aware ISO"
                )
            elif timestamp is not None and available_at > timestamp:
                errors.append(f"thesis_evidence[{index}] is future-dated")
            if not item.get("source_ref"):
                errors.append(f"thesis_evidence[{index}].source_ref is required")

    valuation = decision.get("valuation_assumptions")
    if not isinstance(valuation, dict):
        errors.append("valuation_assumptions must be an object")

    signals = decision.get("signal_states")
    if not isinstance(signals, dict):
        errors.append("signal_states must be an object")
    else:
        for key in SIGNAL_KEYS:
            item = signals.get(key)
            if not isinstance(item, dict):
                errors.append(f"signal_states.{key} must be an object")
                continue
            if not isinstance(item.get("state"), str) or not item["state"].strip():
                errors.append(f"signal_states.{key}.state must be non-empty")
            evidence_ref = item.get("evidence_ref")
            if evidence_ref is not None and not isinstance(evidence_ref, str):
                errors.append(f"signal_states.{key}.evidence_ref must be string or null")

    for field in ("market_regime", "sector_regime"):
        value = decision.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    catalysts = decision.get("catalysts")
    if not isinstance(catalysts, list):
        errors.append("catalysts must be a list")

    invalidations = decision.get("invalidations")
    if not isinstance(invalidations, list):
        errors.append("invalidations must be a list")
    else:
        for index, item in enumerate(invalidations):
            if not isinstance(item, dict):
                errors.append(f"invalidations[{index}] must be an object")
                continue
            if item.get("severity") not in INVALIDATION_SEVERITIES:
                errors.append(
                    f"invalidations[{index}].severity must be SOFT or HARD"
                )
            if not isinstance(item.get("condition"), str) or not item["condition"].strip():
                errors.append(f"invalidations[{index}].condition must be non-empty")

    scenarios = decision.get("scenarios")
    if not isinstance(scenarios, dict):
        errors.append("scenarios must be an object")
    else:
        for key in ("bear", "base", "bull"):
            item = scenarios.get(key)
            if not isinstance(item, dict):
                errors.append(f"scenarios.{key} must be an object")
                continue
            if not isinstance(item.get("narrative"), str) or not item["narrative"].strip():
                errors.append(f"scenarios.{key}.narrative must be non-empty")
            value = item.get("benchmark_relative_return_pct")
            if not _number_or_none(value):
                errors.append(
                    f"scenarios.{key}.benchmark_relative_return_pct must be numeric or null"
                )

    forecast = decision.get("forecast")
    if not isinstance(forecast, dict):
        errors.append("forecast must be an object")
    else:
        calibration = forecast.get("calibration_status")
        if calibration not in CALIBRATION_STATUSES:
            errors.append(
                f"forecast.calibration_status must be one of {sorted(CALIBRATION_STATUSES)}"
            )
        for field in FORECAST_NUMERIC_FIELDS:
            if not _number_or_none(forecast.get(field)):
                errors.append(f"forecast.{field} must be numeric or null")
        probability = forecast.get("probability_beat_benchmark")
        if probability is not None:
            if not 0.0 <= float(probability) <= 1.0:
                errors.append("forecast.probability_beat_benchmark must be within [0,1]")
            if calibration not in {"EXPERIMENTAL", "CALIBRATED"}:
                errors.append(
                    "numeric probability requires EXPERIMENTAL or CALIBRATED status"
                )
        quantiles = [
            forecast.get("p10_benchmark_relative_return_pct"),
            forecast.get("p50_benchmark_relative_return_pct"),
            forecast.get("p90_benchmark_relative_return_pct"),
        ]
        if all(value is not None for value in quantiles):
            p10, p50, p90 = (float(value) for value in quantiles)
            if not p10 <= p50 <= p90:
                errors.append("forecast quantiles must satisfy p10 <= p50 <= p90")

    missing = decision.get("missing_information")
    if not isinstance(missing, list) or any(not isinstance(item, str) for item in missing):
        errors.append("missing_information must be a list of strings")

    action = decision.get("analyst_action")
    if action not in ANALYST_ACTIONS:
        errors.append(f"analyst_action must be one of {sorted(ANALYST_ACTIONS)}")

    if require_seal:
        record_sha = decision.get("record_sha256")
        expected_sha = decision_sha256(decision)
        if record_sha != expected_sha:
            errors.append("record_sha256 does not match canonical decision payload")
        decision_id = decision.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id.endswith(expected_sha[:12]):
            errors.append("decision_id does not match canonical decision digest")

    return errors


def seal_decision(payload: dict) -> dict:
    decision = dict(payload)
    decision.pop("decision_id", None)
    decision.pop("record_sha256", None)
    errors = validate_decision(decision, require_seal=False)
    if errors:
        raise ValueError(errors)

    digest = decision_sha256(decision)
    timestamp = _parse_timestamp(decision["decision_timestamp"])
    assert timestamp is not None
    symbol = str(decision["symbol"]).upper()
    decision["decision_id"] = (
        f"ADO1-{symbol}-{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{digest[:12]}"
    )
    decision["record_sha256"] = digest
    sealed_errors = validate_decision(decision)
    if sealed_errors:
        raise ValueError(sealed_errors)
    return decision


def hard_invalidation_conditions(decision: dict) -> set[str]:
    errors = validate_decision(decision)
    if errors:
        raise ValueError(errors)
    return {
        str(item["condition"])
        for item in decision["invalidations"]
        if item["severity"] == "HARD"
    }
