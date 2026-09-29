from __future__ import annotations

import copy
import math
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, cross_sectional_percentile, digest
from marketlab.alpha_corporate_actions import blocked_actions, parse_share_changing_actions
from marketlab.alpha_delivery import (
    DELIVERY_DEFINITIONS,
    DeliveryObservation,
    delivery_features,
    delivery_session_quality,
    parse_sec_bhavdata_full,
)
from marketlab.alpha_market import (
    DailyEquityObservation,
    build_price_volume_features_from_history,
    eligible_history_for_ae001,
    parse_udiff_eq_panel,
)
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_t004 import validate_frozen_t004_models
from marketlab.events import sha256_bytes

T004_DECISION_LEDGER_ID = "AE001-T004-DECISION-LEDGER-v1"
T004_MODEL_ARTIFACT_ID = "AE001-T004-FROZEN-MODELS-v1"
T004_MIN_COMMON_STOCKS = 500
T004_START_DATE = date(2026, 9, 30)
T004_DECISION_CUTOFF_UTC_HOUR = 13  # 18:30 IST
T004_DECISION_CUTOFF_UTC_MINUTE = 0


def new_t004_decision_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": T004_DECISION_LEDGER_ID,
        "decision_count": 0,
        "decisions": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _decision_ledger_hash(ledger)
    return ledger


def _decision_ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def validate_t004_decision_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != T004_DECISION_LEDGER_ID:
        raise AlphaContractError("unexpected T004 decision ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("T004 decision ledger cannot allow live capital")
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        raise AlphaContractError("T004 decisions must be a list")
    if ledger.get("decision_count") != len(decisions):
        raise AlphaContractError("T004 decision count mismatch")
    seen_dates: set[str] = set()
    for index, decision in enumerate(decisions, start=1):
        if decision.get("seq") != index:
            raise AlphaContractError("T004 decision sequence mismatch")
        session = str(decision.get("session_date") or "")
        if not session or session in seen_dates:
            raise AlphaContractError("T004 decision sessions must be unique")
        seen_dates.add(session)
        stored = str(decision.get("decision_entry_sha256") or "")
        unsigned = dict(decision)
        unsigned.pop("decision_entry_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("T004 decision entry hash mismatch")
    if str(ledger.get("ledger_sha256") or "") != _decision_ledger_hash(ledger):
        raise AlphaContractError("T004 decision ledger hash mismatch")


def t004_cutoff_utc(session_date: str) -> datetime:
    day = date.fromisoformat(session_date)
    return datetime(
        day.year,
        day.month,
        day.day,
        T004_DECISION_CUTOFF_UTC_HOUR,
        T004_DECISION_CUTOFF_UTC_MINUTE,
        tzinfo=UTC,
    )


def eligible_sc001_attempt(
    source_ledger: dict[str, Any],
    *,
    session_date: str,
) -> dict[str, Any]:
    attempts = [
        attempt
        for attempt in source_ledger.get("attempts", [])
        if attempt.get("session_date") == session_date
        and attempt.get("eligible_before_cutoff") is True
    ]
    if not attempts:
        raise AlphaContractError(
            f"{session_date}: no SC001 eligible-before-cutoff source attempt"
        )
    attempts.sort(
        key=lambda row: (
            str(row.get("captured_at_utc") or ""),
            int(row.get("seq") or 0),
        )
    )
    return attempts[0]


def _rank_feature_rows(rows: list[dict[str, Any]], feature_names: list[str]) -> list[dict[str, Any]]:
    ranked_by_feature: dict[str, dict[str, float | None]] = {}
    for feature in feature_names:
        values = {
            f"{row['symbol']}|{row['isin']}": row["values"].get(feature)
            for row in rows
        }
        ranked_by_feature[feature] = cross_sectional_percentile(values)
    ranked = []
    for row in sorted(rows, key=lambda candidate: (candidate["symbol"], candidate["isin"])):
        key = f"{row['symbol']}|{row['isin']}"
        ranked.append(
            {
                **{field: value for field, value in row.items() if field != "values"},
                "values": {
                    feature: ranked_by_feature[feature][key]
                    for feature in feature_names
                },
            }
        )
    return ranked


def _score_model(
    model: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    names = [str(value) for value in model["feature_names"]]
    medians = np.asarray(model["feature_medians"], dtype=float)
    means = np.asarray(model["feature_means"], dtype=float)
    scales = np.asarray(model["feature_scales"], dtype=float)
    coefficients = np.asarray(model["coefficients"], dtype=float)
    if not (
        len(names)
        == len(medians)
        == len(means)
        == len(scales)
        == len(coefficients)
    ):
        raise AlphaContractError("T004 frozen model dimensions disagree")

    matrix = np.empty((len(rows), len(names)), dtype=float)
    for row_index, row in enumerate(rows):
        values = row["values"]
        for column, name in enumerate(names):
            value = values.get(name)
            matrix[row_index, column] = np.nan if value is None else float(value)
    filled = np.where(np.isnan(matrix), medians, matrix)
    normalized = (filled - means) / scales
    predictions = float(model["intercept"]) + normalized @ coefficients

    return [
        {
            "symbol": row["symbol"],
            "isin": row["isin"],
            "prediction": float(predictions[index]),
        }
        for index, row in enumerate(rows)
    ]


def _market_histories(
    market_sessions: list[dict[str, Any]],
) -> tuple[
    dict[tuple[str, str], list[DailyEquityObservation]],
    dict[tuple[str, str], list[int]],
    dict[str, dict[str, DailyEquityObservation]],
]:
    histories: dict[tuple[str, str], list[DailyEquityObservation]] = {}
    indices: dict[tuple[str, str], list[int]] = {}
    by_session_symbol: dict[str, dict[str, DailyEquityObservation]] = {}
    for session_index, session in enumerate(market_sessions):
        day = str(session["session_date"])
        symbol_map: dict[str, DailyEquityObservation] = {}
        for raw in session["equities"]:
            row = (
                raw
                if isinstance(raw, DailyEquityObservation)
                else DailyEquityObservation(**raw)
            )
            if row.symbol in symbol_map:
                raise AlphaContractError(f"{day}: duplicate market symbol")
            symbol_map[row.symbol] = row
            identity = (row.symbol, row.isin)
            histories.setdefault(identity, []).append(row)
            indices.setdefault(identity, []).append(session_index)
        by_session_symbol[day] = symbol_map
    return histories, indices, by_session_symbol


def build_t004_current_feature_rows(
    *,
    prior_market_sessions: list[dict[str, Any]],
    current_market_raw: bytes,
    prior_delivery_sessions: list[dict[str, Any]],
    current_delivery_raw: bytes,
    session_date: str,
    corporate_action_payload: object,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the exact current-session T004 common cross-section.

    Prior source history may be reconstructed at decision time because every
    observation predates the current decision session. The current session raw
    bytes must come from SC001's prospective capture.
    """

    day = date.fromisoformat(session_date)
    if day < T004_START_DATE:
        raise AlphaContractError("T004 decision precedes frozen start boundary")

    prior_market = sorted(
        prior_market_sessions,
        key=lambda row: str(row["session_date"]),
    )
    if len(prior_market) < 60:
        raise AlphaContractError("T004 requires at least 60 prior market sessions")
    prior_market = prior_market[-60:]
    if str(prior_market[-1]["session_date"]) >= session_date:
        raise AlphaContractError("T004 prior market history crosses decision session")

    current_market = parse_udiff_eq_panel(
        current_market_raw,
        session_date=day,
    )
    current_market_session = {
        "session_date": session_date,
        "equities": [asdict(row) for row in current_market],
        "udiff_sha256": sha256_bytes(current_market_raw),
    }
    market_sessions = [*prior_market, current_market_session]
    histories, history_indices, market_by_session = _market_histories(market_sessions)

    prior_delivery = sorted(
        prior_delivery_sessions,
        key=lambda row: str(row["session_date"]),
    )
    if len(prior_delivery) < 20:
        raise AlphaContractError("T004 requires at least 20 prior delivery sessions")
    prior_delivery = prior_delivery[-20:]
    expected_prior_dates = [
        str(row["session_date"]) for row in prior_market[-20:]
    ]
    if [str(row["session_date"]) for row in prior_delivery] != expected_prior_dates:
        raise AlphaContractError(
            "T004 delivery history does not match the prior 20 market sessions"
        )

    current_delivery_rows = parse_sec_bhavdata_full(
        current_delivery_raw,
        session_date=day,
    )
    current_quality = delivery_session_quality(current_delivery_rows)
    if current_quality["status"] != "READY":
        raise AlphaContractError("T004 current delivery source fails P3 quality")

    delivery_sessions = [
        *prior_delivery,
        {
            "session_date": session_date,
            "source_quality": current_quality,
            "raw_sha256": sha256_bytes(current_delivery_raw),
            "rows": [asdict(row) for row in current_delivery_rows],
        },
    ]
    delivery_histories: dict[tuple[str, str], list[DeliveryObservation]] = {}
    delivery_indices: dict[tuple[str, str], list[int]] = {}
    for delivery_index, session in enumerate(delivery_sessions):
        session_day = str(session["session_date"])
        quality = session.get("source_quality")
        if not isinstance(quality, dict) or quality.get("status") != "READY":
            continue
        market_map = market_by_session.get(session_day)
        if market_map is None:
            raise AlphaContractError(
                f"{session_day}: delivery history lacks market identity map"
            )
        seen: set[str] = set()
        for raw in session["rows"]:
            delivery = (
                raw
                if isinstance(raw, DeliveryObservation)
                else DeliveryObservation(**raw)
            )
            if delivery.symbol in seen:
                raise AlphaContractError(f"{session_day}: duplicate delivery symbol")
            seen.add(delivery.symbol)
            market_row = market_map.get(delivery.symbol)
            if market_row is None:
                continue
            identity = (market_row.symbol, market_row.isin)
            delivery_histories.setdefault(identity, []).append(delivery)
            delivery_indices.setdefault(identity, []).append(delivery_index)

    action_states = parse_share_changing_actions(corporate_action_payload)
    all_feature_names = [
        definition.name
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]

    current_map = market_by_session[session_date]
    rows = []
    exclusions = {
        "market_history": 0,
        "liquidity": 0,
        "corporate_action": 0,
        "corporate_action_unresolved": 0,
        "delivery_history": 0,
        "delivery_value": 0,
    }

    for symbol in sorted(current_map):
        current = current_map[symbol]
        identity = (current.symbol, current.isin)
        market_history = histories.get(identity, [])
        market_positions = history_indices.get(identity, [])
        if (
            len(market_history) != 61
            or market_positions != list(range(61))
        ):
            exclusions["market_history"] += 1
            continue
        if not eligible_history_for_ae001(market_history):
            exclusions["liquidity"] += 1
            continue

        action_state = action_states.get(symbol)
        if action_state is not None and action_state.get("status") != "READY":
            exclusions["corporate_action_unresolved"] += 1
            continue
        if action_state is not None:
            action_index = {symbol: action_state}
            if blocked_actions(
                action_index,
                symbol=symbol,
                start_exclusive=market_history[0].session_date,
                end_inclusive=session_date,
            ):
                exclusions["corporate_action"] += 1
                continue

        delivery_history = delivery_histories.get(identity, [])
        delivery_positions = delivery_indices.get(identity, [])
        if (
            len(delivery_history) != 21
            or delivery_positions != list(range(21))
        ):
            exclusions["delivery_history"] += 1
            continue
        try:
            values = {
                **build_price_volume_features_from_history(market_history),
                **delivery_features(
                    delivery_history,
                    market_current=current,
                ),
            }
        except AlphaContractError:
            exclusions["delivery_value"] += 1
            continue
        if set(values) != set(all_feature_names):
            raise AlphaContractError("T004 feature set differs from frozen 27 features")
        if any(
            value is not None and not math.isfinite(float(value))
            for value in values.values()
        ):
            raise AlphaContractError("T004 feature row contains nonfinite value")
        rows.append(
            {
                "symbol": symbol,
                "isin": current.isin,
                "values": values,
            }
        )

    ranked = _rank_feature_rows(rows, all_feature_names)
    diagnostics = {
        "common_row_count": len(ranked),
        "exclusions": exclusions,
        "feature_names": all_feature_names,
        "feature_rows_sha256": digest(ranked),
    }
    return ranked, diagnostics


def build_t004_decision_artifact(
    *,
    session_date: str,
    sc001_attempt: dict[str, Any],
    prior_market_sessions: list[dict[str, Any]],
    current_market_raw: bytes,
    prior_delivery_sessions: list[dict[str, Any]],
    current_delivery_raw: bytes,
    corporate_action_payload: object,
    corporate_action_raw: bytes,
    frozen_models: dict[str, Any],
    sealed_at_utc: str,
) -> dict[str, Any]:
    validate_frozen_t004_models(frozen_models)
    if frozen_models.get("artifact_id") != T004_MODEL_ARTIFACT_ID:
        raise AlphaContractError("T004 decision uses unexpected model artifact")
    if sc001_attempt.get("eligible_before_cutoff") is not True:
        raise AlphaContractError("T004 decision requires SC001 cutoff eligibility")
    if sc001_attempt.get("session_date") != session_date:
        raise AlphaContractError("T004 decision/SC001 session mismatch")

    sealed = datetime.fromisoformat(sealed_at_utc)
    if sealed.tzinfo is None:
        raise AlphaContractError("T004 sealed_at_utc must be timezone-aware")
    sealed = sealed.astimezone(UTC)
    if sealed > t004_cutoff_utc(session_date):
        raise AlphaContractError("T004 prediction sealing missed decision cutoff")

    rows, diagnostics = build_t004_current_feature_rows(
        prior_market_sessions=prior_market_sessions,
        current_market_raw=current_market_raw,
        prior_delivery_sessions=prior_delivery_sessions,
        current_delivery_raw=current_delivery_raw,
        session_date=session_date,
        corporate_action_payload=corporate_action_payload,
    )
    if len(rows) < T004_MIN_COMMON_STOCKS:
        raise AlphaContractError(
            f"T004 common row count below frozen minimum: {len(rows)}"
        )

    base_predictions = _score_model(frozen_models["base_model"], rows)
    augmented_predictions = _score_model(
        frozen_models["augmented_model"],
        rows,
    )
    base_identity = [(row["symbol"], row["isin"]) for row in base_predictions]
    augmented_identity = [
        (row["symbol"], row["isin"]) for row in augmented_predictions
    ]
    if base_identity != augmented_identity:
        raise AlphaContractError("T004 base/augmented prediction rows differ")

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": "AE001-T004-DECISION-v1",
        "trial_id": "AE001-T004",
        "session_date": session_date,
        "sealed_at_utc": sealed.isoformat(),
        "decision_cutoff_utc": t004_cutoff_utc(session_date).isoformat(),
        "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
        "sc001_captured_at_utc": sc001_attempt["captured_at_utc"],
        "current_market_sha256": sha256_bytes(current_market_raw),
        "current_delivery_sha256": sha256_bytes(current_delivery_raw),
        "corporate_action_raw_sha256": sha256_bytes(corporate_action_raw),
        "frozen_model_artifact_sha256": frozen_models["artifact_sha256"],
        "base_model_sha256": frozen_models["base_model"]["model_sha256"],
        "augmented_model_sha256": frozen_models["augmented_model"]["model_sha256"],
        "common_row_count": len(rows),
        "feature_rows_sha256": diagnostics["feature_rows_sha256"],
        "feature_exclusions": diagnostics["exclusions"],
        "base_predictions": base_predictions,
        "augmented_predictions": augmented_predictions,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def append_t004_decision(
    ledger: dict[str, Any],
    *,
    decision_artifact: dict[str, Any],
    artifact_path: str,
) -> dict[str, Any]:
    validate_t004_decision_ledger(ledger)
    session_date = str(decision_artifact.get("session_date") or "")
    if any(row["session_date"] == session_date for row in ledger["decisions"]):
        raise AlphaContractError(f"T004 decision already exists for {session_date}")
    if decision_artifact.get("outcomes_attached") is not False:
        raise AlphaContractError("T004 canonical decision cannot contain outcomes")
    entry: dict[str, Any] = {
        "seq": len(ledger["decisions"]) + 1,
        "session_date": session_date,
        "artifact_path": artifact_path,
        "artifact_sha256": decision_artifact["artifact_sha256"],
        "sealed_at_utc": decision_artifact["sealed_at_utc"],
        "common_row_count": decision_artifact["common_row_count"],
        "sc001_attempt_sha256": decision_artifact["sc001_attempt_sha256"],
        "base_model_sha256": decision_artifact["base_model_sha256"],
        "augmented_model_sha256": decision_artifact["augmented_model_sha256"],
        "live_capital_allowed": False,
    }
    entry["decision_entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["decisions"].append(entry)
    updated["decision_count"] = len(updated["decisions"])
    updated["ledger_sha256"] = _decision_ledger_hash(updated)
    validate_t004_decision_ledger(updated)
    return updated
