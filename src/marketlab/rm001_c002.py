from __future__ import annotations

import copy
import hashlib
import math
import statistics
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_diagnostics import newey_west_mean_inference
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.rm001 import portfolio_risk
from marketlab.rm001_calibration import (
    CAL1_MODEL_ID,
    CALIBRATION_SCALE,
    portfolio_risk_cal1,
)

STUDY_ID = "RM001-C002-v1"
FORECAST_LEDGER_ID = "RM001-C002-FORECAST-LEDGER-v1"
OUTCOME_LEDGER_ID = "RM001-C002-OUTCOME-LEDGER-v1"
START_DECISION_DATE = date(2026, 10, 5)
IST = ZoneInfo("Asia/Kolkata")
SEAL_CUTOFF = time(9, 5)
PROBE_SIZE = 30
HASH_PROBE_COUNT = 8
TAIL_FACTORS = (
    "BETA60_RELATIVE",
    "MOMENTUM20",
    "VOLATILITY60",
    "LIQUIDITY",
)
MIN_COMMON_IDENTITIES = 500
MIN_VALID_PROBES_PER_DATE = 12
MIN_EVALUATED_DATES = 20
NEWEY_WEST_LAG = 5
LOG_RATIO_EPSILON = 1e-12


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_forecast_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": FORECAST_LEDGER_ID,
        "entry_count": 0,
        "entries": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def new_outcome_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": OUTCOME_LEDGER_ID,
        "entry_count": 0,
        "entries": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def _validate_ledger(
    ledger: dict[str, Any],
    *,
    expected_id: str,
    allowed_statuses: set[str],
) -> None:
    if ledger.get("ledger_id") != expected_id:
        raise AlphaContractError(f"unexpected {expected_id} ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError(f"{expected_id} cannot allow live capital")
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        raise AlphaContractError(f"{expected_id} entries must be a list")
    if int(ledger.get("entry_count") or 0) != len(entries):
        raise AlphaContractError(f"{expected_id} entry count mismatch")
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if int(entry.get("seq") or 0) != index:
            raise AlphaContractError(f"{expected_id} sequence mismatch")
        target = str(entry.get("target_session_date") or "")
        if not target or target in seen:
            raise AlphaContractError(f"{expected_id} target session invalid")
        seen.add(target)
        if str(entry.get("status") or "") not in allowed_statuses:
            raise AlphaContractError(f"{expected_id} status is unsupported")
        stored = str(entry.get("entry_sha256") or "")
        unsigned = copy.deepcopy(entry)
        unsigned.pop("entry_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError(f"{expected_id} entry hash mismatch")
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError(f"{expected_id} ledger hash mismatch")


def validate_forecast_ledger(ledger: dict[str, Any]) -> None:
    _validate_ledger(
        ledger,
        expected_id=FORECAST_LEDGER_ID,
        allowed_statuses={"SEALED", "MISSED_0905_CUTOFF"},
    )


def validate_outcome_ledger(ledger: dict[str, Any]) -> None:
    _validate_ledger(
        ledger,
        expected_id=OUTCOME_LEDGER_ID,
        allowed_statuses={"SCORED", "UNAVAILABLE"},
    )


def forecast_seal_cutoff_utc(target_session_date: str) -> datetime:
    """Frozen conservative cutoff: 09:05 IST on the next calendar day."""

    target = date.fromisoformat(target_session_date)
    observation = target + timedelta(days=1)
    return datetime.combine(observation, SEAL_CUTOFF, IST).astimezone(UTC)


def eligible_sc001_targets(source_ledger: dict[str, Any]) -> list[dict[str, Any]]:
    validate_source_ledger(source_ledger)
    rows = [
        row
        for row in source_ledger.get("attempts", [])
        if row.get("eligible_before_cutoff") is True
        and date.fromisoformat(str(row["session_date"])) >= START_DECISION_DATE
    ]
    rows.sort(
        key=lambda row: (
            str(row["session_date"]),
            str(row["captured_at_utc"]),
            int(row["seq"]),
        )
    )
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique.setdefault(str(row["session_date"]), row)
    return [unique[key] for key in sorted(unique)]


def next_unhandled_target(
    *,
    source_ledger: dict[str, Any],
    forecast_ledger: dict[str, Any],
) -> dict[str, Any] | None:
    validate_forecast_ledger(forecast_ledger)
    handled = {
        str(entry["target_session_date"])
        for entry in forecast_ledger["entries"]
    }
    for row in eligible_sc001_targets(source_ledger):
        if str(row["session_date"]) not in handled:
            return row
    return None


def build_probe_library_v1(
    raw_risk_state: dict[str, Any],
) -> dict[str, list[tuple[str, str]]]:
    rows = raw_risk_state.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("C002 raw risk-state rows are missing")
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        identity = (str(row["symbol"]), str(row["isin"]))
        if identity in by_identity:
            raise AlphaContractError("C002 risk state contains duplicate identity")
        by_identity[identity] = row
    identities = sorted(by_identity)
    if len(identities) < MIN_COMMON_IDENTITIES:
        raise AlphaContractError(
            f"C002 common risk universe below minimum: {len(identities)}"
        )

    probes: dict[str, list[tuple[str, str]]] = {}
    for index in range(HASH_PROBE_COUNT):
        name = f"HASH{index:02d}"
        ranked = sorted(
            identities,
            key=lambda identity: (
                hashlib.sha256(
                    (
                        f"RM001-C002|{name}|"
                        f"{identity[0]}|{identity[1]}"
                    ).encode()
                ).hexdigest(),
                identity[0],
                identity[1],
            ),
        )
        probes[name] = ranked[:PROBE_SIZE]

    for factor in TAIL_FACTORS:
        values = []
        for identity in identities:
            exposures = by_identity[identity].get("exposures")
            if not isinstance(exposures, dict) or factor not in exposures:
                raise AlphaContractError(
                    f"C002 raw state lacks factor {factor}"
                )
            value = float(exposures[factor])
            if not math.isfinite(value):
                raise AlphaContractError(
                    f"C002 nonfinite factor exposure: {factor}"
                )
            values.append((identity, value))
        probes[f"{factor}_LOW"] = [
            identity
            for identity, _ in sorted(
                values,
                key=lambda item: (
                    item[1],
                    item[0][0],
                    item[0][1],
                ),
            )[:PROBE_SIZE]
        ]
        probes[f"{factor}_HIGH"] = [
            identity
            for identity, _ in sorted(
                values,
                key=lambda item: (
                    -item[1],
                    item[0][0],
                    item[0][1],
                ),
            )[:PROBE_SIZE]
        ]

    expected = HASH_PROBE_COUNT + 2 * len(TAIL_FACTORS)
    if len(probes) != expected:
        raise AlphaContractError("C002 probe-count invariant failed")
    for name, members in probes.items():
        if len(members) != PROBE_SIZE or len(set(members)) != PROBE_SIZE:
            raise AlphaContractError(
                f"C002 probe membership invariant failed: {name}"
            )
    return dict(sorted(probes.items()))


def _positions(members: list[tuple[str, str]]) -> list[dict[str, Any]]:
    weight = 1.0 / len(members)
    return [
        {
            "symbol": symbol,
            "isin": isin,
            "weight": weight,
        }
        for symbol, isin in members
    ]


def build_forecast_artifact(
    *,
    target_session_date: str,
    sc001_attempt: dict[str, Any],
    raw_risk_state: dict[str, Any],
    calibrated_risk_state: dict[str, Any],
    sealed_at_utc: str,
) -> dict[str, Any]:
    if date.fromisoformat(target_session_date) < START_DECISION_DATE:
        raise AlphaContractError("C002 target precedes frozen start")
    if sc001_attempt.get("eligible_before_cutoff") is not True:
        raise AlphaContractError("C002 requires eligible SC001 source attempt")
    if str(sc001_attempt.get("session_date") or "") != target_session_date:
        raise AlphaContractError("C002 SC001 target mismatch")
    if str(raw_risk_state.get("as_of_session") or "") != target_session_date:
        raise AlphaContractError("C002 raw state as-of mismatch")
    if str(calibrated_risk_state.get("as_of_session") or "") != target_session_date:
        raise AlphaContractError("C002 calibrated state as-of mismatch")
    if calibrated_risk_state.get("parent_risk_state_sha256") != raw_risk_state.get(
        "state_sha256"
    ):
        raise AlphaContractError("C002 calibrated/raw state binding mismatch")
    if float(calibrated_risk_state.get("calibration_scale")) != CALIBRATION_SCALE:
        raise AlphaContractError("C002 calibration scale differs from frozen value")

    sealed = datetime.fromisoformat(sealed_at_utc)
    if sealed.tzinfo is None:
        raise AlphaContractError("C002 seal timestamp must be timezone-aware")
    sealed = sealed.astimezone(UTC)
    cutoff = forecast_seal_cutoff_utc(target_session_date)
    if sealed > cutoff:
        raise AlphaContractError("C002 forecast missed 09:05 IST seal cutoff")

    probes = build_probe_library_v1(raw_risk_state)
    probe_rows = []
    for name, members in probes.items():
        positions = _positions(members)
        raw = portfolio_risk(raw_risk_state, positions=positions)
        calibrated = portfolio_risk_cal1(
            calibrated_risk_state,
            positions=positions,
        )
        expected = float(raw["total_variance_daily"]) * CALIBRATION_SCALE
        if abs(
            float(calibrated["total_variance_daily"]) - expected
        ) > 5e-14:
            raise AlphaContractError(
                "C002 calibrated portfolio variance scaling invariant failed"
            )
        probe_rows.append(
            {
                "probe_name": name,
                "members": [
                    {"symbol": symbol, "isin": isin}
                    for symbol, isin in members
                ],
                "members_sha256": digest(
                    [
                        {"symbol": symbol, "isin": isin}
                        for symbol, isin in members
                    ]
                ),
                "raw_v1_predicted_variance": raw[
                    "total_variance_daily"
                ],
                "cal1_predicted_variance": calibrated[
                    "total_variance_daily"
                ],
            }
        )

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "status": "SEALED_FORECAST_NO_OUTCOME",
        "target_session_date": target_session_date,
        "sealed_at_utc": sealed.isoformat(),
        "seal_cutoff_utc": cutoff.isoformat(),
        "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
        "current_market_raw_sha256": sc001_attempt["market"]["raw_sha256"],
        "raw_risk_state_sha256": raw_risk_state["state_sha256"],
        "calibrated_risk_state_sha256": calibrated_risk_state["state_sha256"],
        "calibration_scale": CALIBRATION_SCALE,
        "common_identity_count": len(raw_risk_state["rows"]),
        "probe_count": len(probe_rows),
        "probes": probe_rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def append_forecast_entry(
    ledger: dict[str, Any],
    *,
    target_session_date: str,
    status: str,
    sc001_attempt_sha256: str,
    observed_at_utc: str,
    reason: str | None = None,
    forecast_artifact_path: str | None = None,
    forecast_artifact_sha256: str | None = None,
    raw_risk_state_sha256: str | None = None,
    calibrated_risk_state_sha256: str | None = None,
) -> dict[str, Any]:
    validate_forecast_ledger(ledger)
    if status not in {"SEALED", "MISSED_0905_CUTOFF"}:
        raise AlphaContractError("C002 forecast status unsupported")
    if any(
        str(entry["target_session_date"]) == target_session_date
        for entry in ledger["entries"]
    ):
        raise AlphaContractError("C002 target forecast already recorded")
    if status == "SEALED":
        if not forecast_artifact_path or not forecast_artifact_sha256:
            raise AlphaContractError("C002 sealed forecast artifact is required")
        if not raw_risk_state_sha256 or not calibrated_risk_state_sha256:
            raise AlphaContractError("C002 sealed risk-state hashes are required")
    entry: dict[str, Any] = {
        "seq": len(ledger["entries"]) + 1,
        "target_session_date": target_session_date,
        "status": status,
        "sc001_attempt_sha256": sc001_attempt_sha256,
        "observed_at_utc": observed_at_utc,
        "reason": reason,
        "forecast_artifact_path": forecast_artifact_path,
        "forecast_artifact_sha256": forecast_artifact_sha256,
        "raw_risk_state_sha256": raw_risk_state_sha256,
        "calibrated_risk_state_sha256": calibrated_risk_state_sha256,
        "live_capital_allowed": False,
    }
    entry["entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["entries"].append(entry)
    updated["entry_count"] = len(updated["entries"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_forecast_ledger(updated)
    return updated


def qlike_loss(predicted_variance: float, realized_squared_return: float) -> float:
    predicted = float(predicted_variance)
    realized = float(realized_squared_return)
    if not math.isfinite(predicted) or predicted <= 0:
        raise AlphaContractError(
            "C002 predicted variance must be finite and positive"
        )
    if not math.isfinite(realized) or realized < 0:
        raise AlphaContractError(
            "C002 realized squared return must be finite and non-negative"
        )
    return math.log(predicted) + realized / predicted


def build_outcome_artifact(
    *,
    forecast_artifact: dict[str, Any],
    realized_session_date: str,
    realized_returns: dict[tuple[str, str], float],
    unavailable_identities: dict[tuple[str, str], str] | None = None,
) -> dict[str, Any]:
    if forecast_artifact.get("outcomes_attached") is not False:
        raise AlphaContractError("C002 forecast artifact already contains outcome")
    target = str(forecast_artifact["target_session_date"])
    if realized_session_date <= target:
        raise AlphaContractError("C002 realized session must follow target")

    unavailable = unavailable_identities or {}
    rows = []
    for probe in forecast_artifact["probes"]:
        members = [
            (str(row["symbol"]), str(row["isin"]))
            for row in probe["members"]
        ]
        blocked = [
            (identity, unavailable[identity])
            for identity in members
            if identity in unavailable
        ]
        if blocked:
            reasons = sorted({reason for _, reason in blocked})
            rows.append(
                {
                    "probe_name": probe["probe_name"],
                    "status": "UNAVAILABLE",
                    "reason": "MEMBER_UNAVAILABLE",
                    "member_reason_counts": {
                        reason: sum(item_reason == reason for _, item_reason in blocked)
                        for reason in reasons
                    },
                    "unavailable_member_count": len(blocked),
                }
            )
            continue
        missing = [identity for identity in members if identity not in realized_returns]
        if missing:
            rows.append(
                {
                    "probe_name": probe["probe_name"],
                    "status": "UNAVAILABLE",
                    "reason": "MISSING_MEMBER_RETURN",
                    "missing_member_count": len(missing),
                }
            )
            continue
        weight = 1.0 / len(members)
        realized_return = sum(
            weight * float(realized_returns[identity])
            for identity in members
        )
        realized_squared = realized_return * realized_return
        raw_var = float(probe["raw_v1_predicted_variance"])
        cal_var = float(probe["cal1_predicted_variance"])
        raw_loss = qlike_loss(raw_var, realized_squared)
        cal_loss = qlike_loss(cal_var, realized_squared)
        rows.append(
            {
                "probe_name": probe["probe_name"],
                "status": "SCORED",
                "realized_return": realized_return,
                "realized_squared_return": realized_squared,
                "raw_v1_predicted_variance": raw_var,
                "cal1_predicted_variance": cal_var,
                "raw_v1_qlike": raw_loss,
                "cal1_qlike": cal_loss,
                "cal1_minus_raw_qlike": cal_loss - raw_loss,
            }
        )

    scored = [row for row in rows if row["status"] == "SCORED"]
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "status": (
            "SCORED"
            if len(scored) >= MIN_VALID_PROBES_PER_DATE
            else "UNAVAILABLE"
        ),
        "target_session_date": target,
        "realized_session_date": realized_session_date,
        "forecast_artifact_sha256": forecast_artifact["artifact_sha256"],
        "valid_probe_count": len(scored),
        "minimum_valid_probe_count": MIN_VALID_PROBES_PER_DATE,
        "probe_outcomes": rows,
        "live_capital_allowed": False,
    }
    if scored:
        artifact["raw_v1_mean_qlike"] = statistics.mean(
            float(row["raw_v1_qlike"]) for row in scored
        )
        artifact["cal1_mean_qlike"] = statistics.mean(
            float(row["cal1_qlike"]) for row in scored
        )
        artifact["cal1_minus_raw_mean_qlike"] = statistics.mean(
            float(row["cal1_minus_raw_qlike"]) for row in scored
        )
        artifact["raw_v1_mean_predicted_variance"] = statistics.mean(
            float(row["raw_v1_predicted_variance"]) for row in scored
        )
        artifact["cal1_mean_predicted_variance"] = statistics.mean(
            float(row["cal1_predicted_variance"]) for row in scored
        )
        artifact["mean_realized_squared_return"] = statistics.mean(
            float(row["realized_squared_return"]) for row in scored
        )
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def append_outcome_entry(
    ledger: dict[str, Any],
    *,
    forecast_entry_sha256: str,
    outcome_artifact: dict[str, Any],
    outcome_artifact_path: str,
) -> dict[str, Any]:
    validate_outcome_ledger(ledger)
    target = str(outcome_artifact["target_session_date"])
    if any(
        str(entry["target_session_date"]) == target
        for entry in ledger["entries"]
    ):
        raise AlphaContractError("C002 target outcome already recorded")
    status = str(outcome_artifact["status"])
    if status not in {"SCORED", "UNAVAILABLE"}:
        raise AlphaContractError("C002 outcome artifact status unsupported")
    entry: dict[str, Any] = {
        "seq": len(ledger["entries"]) + 1,
        "target_session_date": target,
        "realized_session_date": outcome_artifact["realized_session_date"],
        "status": status,
        "forecast_entry_sha256": forecast_entry_sha256,
        "outcome_artifact_path": outcome_artifact_path,
        "outcome_artifact_sha256": outcome_artifact["artifact_sha256"],
        "valid_probe_count": outcome_artifact["valid_probe_count"],
        "cal1_minus_raw_mean_qlike": outcome_artifact.get(
            "cal1_minus_raw_mean_qlike"
        ),
        "live_capital_allowed": False,
    }
    entry["entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["entries"].append(entry)
    updated["entry_count"] = len(updated["entries"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_outcome_ledger(updated)
    return updated


def prospective_summary(outcome_artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [
        artifact
        for artifact in outcome_artifacts
        if artifact.get("status") == "SCORED"
        and int(artifact.get("valid_probe_count") or 0)
        >= MIN_VALID_PROBES_PER_DATE
    ]
    scored.sort(key=lambda row: str(row["target_session_date"]))
    deltas = [
        float(row["cal1_minus_raw_mean_qlike"])
        for row in scored
    ]
    inference = newey_west_mean_inference(
        deltas,
        max_lag=NEWEY_WEST_LAG,
    )
    if len(scored) < MIN_EVALUATED_DATES:
        status = "INSUFFICIENT_PROSPECTIVE_SAMPLE"
    elif (
        inference.get("mean") is not None
        and inference.get("ci95_high") is not None
        and float(inference["mean"]) < 0.0
        and float(inference["ci95_high"]) < 0.0
    ):
        status = "CAL1_SUPERIOR_PROSPECTIVE_RISK_CALIBRATION"
    else:
        status = "NO_CAL1_PROSPECTIVE_SUPERIORITY"

    raw_predicted = [
        float(row["raw_v1_mean_predicted_variance"]) for row in scored
    ]
    cal_predicted = [
        float(row["cal1_mean_predicted_variance"]) for row in scored
    ]
    realized = [
        float(row["mean_realized_squared_return"]) for row in scored
    ]
    summary: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "status": status,
        "evaluated_date_count": len(scored),
        "minimum_evaluated_date_count": MIN_EVALUATED_DATES,
        "paired_cal1_minus_raw_inference": inference,
        "calibration_scale": CALIBRATION_SCALE,
        "dates": [row["target_session_date"] for row in scored],
        "live_capital_allowed": False,
    }
    if scored:
        summary["raw_v1_aggregate_calibration_ratio"] = (
            sum(realized) / sum(raw_predicted)
        )
        summary["cal1_aggregate_calibration_ratio"] = (
            sum(realized) / sum(cal_predicted)
        )
        summary["raw_v1_mean_predicted_variance"] = statistics.mean(raw_predicted)
        summary["cal1_mean_predicted_variance"] = statistics.mean(cal_predicted)
        summary["mean_realized_squared_return"] = statistics.mean(realized)
    summary["summary_sha256"] = digest(summary)
    return summary
