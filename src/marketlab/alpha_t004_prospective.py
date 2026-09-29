from __future__ import annotations

import copy
import math
from collections import defaultdict, deque
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, cross_sectional_percentile, digest
from marketlab.alpha_corporate_actions import (
    action_index,
    blocked_actions,
    validate_action_ledger,
)
from marketlab.alpha_delivery import DeliveryObservation, delivery_features
from marketlab.alpha_market import (
    DailyEquityObservation,
    build_price_volume_features_from_history,
    eligible_history_for_ae001,
)
from marketlab.alpha_model import ridge_model_from_record, score_ridge_values
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.alpha_t004 import validate_frozen_t004_models

IST = ZoneInfo("Asia/Kolkata")
T004_TRIAL_ID = "AE001-T004"
T004_PREDICTION_LEDGER_ID = "AE001-T004-PREDICTION-LEDGER-v1"
T004_START_DATE = date(2026, 9, 30)
MIN_COMMON_STOCKS = 500
FROZEN_MODEL_ARTIFACT_SHA256 = (
    "e6e7bdc0bf95c5b0e2ddcb1a52d3f5473f33c1e6057031d4a69123dea2db3967"
)
BASE_MODEL_SHA256 = (
    "5ffe30f85ee1bbae920ed661d5cb8c9c68afd72e2e1541c0faef42716b5de2e7"
)
AUGMENTED_MODEL_SHA256 = (
    "4b8626288f1dcfb1f881046559fe906acdeaa5c9fe31d759e4412ee1e7649d3f"
)


def select_sc001_eligible_attempt(
    source_ledger: dict[str, Any],
    *,
    session_date: str | None = None,
) -> dict[str, Any] | None:
    """Select the first eligible SC001 observation for one/latest session."""

    validate_source_ledger(source_ledger)
    eligible = [
        attempt
        for attempt in source_ledger["attempts"]
        if attempt.get("eligible_before_cutoff") is True
        and (
            session_date is None
            or str(attempt.get("session_date")) == session_date
        )
    ]
    if not eligible:
        return None
    if session_date is None:
        latest_session = max(str(row["session_date"]) for row in eligible)
        eligible = [
            row for row in eligible if str(row["session_date"]) == latest_session
        ]
    eligible.sort(key=lambda row: int(row["seq"]))
    return eligible[0]


def conservative_prediction_deadline_utc(session_date: str) -> datetime:
    """Conservative deadline: next calendar day at the standard 09:15 IST open."""

    day = date.fromisoformat(session_date) + timedelta(days=1)
    return datetime.combine(day, time(9, 15), IST).astimezone(UTC)


def prediction_deadline_open(sealed_at_utc: str, *, session_date: str) -> bool:
    try:
        sealed = datetime.fromisoformat(sealed_at_utc)
    except ValueError as exc:
        raise AlphaContractError("T004 seal timestamp is invalid") from exc
    if sealed.tzinfo is None:
        raise AlphaContractError("T004 seal timestamp must be timezone-aware")
    return sealed.astimezone(UTC) < conservative_prediction_deadline_utc(
        session_date
    )


def _coerce_market_row(raw: Any) -> DailyEquityObservation:
    if isinstance(raw, DailyEquityObservation):
        return raw
    if not isinstance(raw, dict):
        raise AlphaContractError("T004 market row must be an object")
    try:
        return DailyEquityObservation(**raw)
    except TypeError as exc:
        raise AlphaContractError("T004 market row is malformed") from exc


def _coerce_delivery_row(raw: Any) -> DeliveryObservation:
    if isinstance(raw, DeliveryObservation):
        return raw
    if not isinstance(raw, dict):
        raise AlphaContractError("T004 delivery row must be an object")
    try:
        return DeliveryObservation(**raw)
    except TypeError as exc:
        raise AlphaContractError("T004 delivery row is malformed") from exc


def build_t004_feature_snapshot(
    *,
    market_sessions: list[dict[str, Any]],
    delivery_sessions: list[dict[str, Any]],
    action_ledger: dict[str, Any],
    feature_session: str,
    sc001_attempt: dict[str, Any],
) -> dict[str, Any]:
    """Build the current T004 27-feature common-row cross-section.

    The final market/delivery session must be the exact SC001 current session.
    Historical sessions may be reconstructed after cutoff.
    """

    validate_action_ledger(action_ledger)
    if date.fromisoformat(feature_session) < T004_START_DATE:
        raise AlphaContractError("T004 feature session precedes frozen start")
    if sc001_attempt.get("eligible_before_cutoff") is not True:
        raise AlphaContractError("T004 requires an eligible SC001 attempt")
    if str(sc001_attempt.get("session_date")) != feature_session:
        raise AlphaContractError("T004 SC001 attempt session mismatch")
    if len(market_sessions) < 61:
        raise AlphaContractError("T004 requires 61 market sessions")
    if len(market_sessions) != len(delivery_sessions):
        raise AlphaContractError("T004 market/delivery session counts differ")

    market_dates = [str(row.get("session_date")) for row in market_sessions]
    delivery_dates = [str(row.get("session_date")) for row in delivery_sessions]
    if market_dates != delivery_dates:
        raise AlphaContractError("T004 market/delivery session dates differ")
    if market_dates != sorted(market_dates) or len(market_dates) != len(
        set(market_dates)
    ):
        raise AlphaContractError("T004 history sessions are not canonical")
    if market_dates[-1] != feature_session:
        raise AlphaContractError("T004 history does not end at feature session")

    current_market_sha = str(
        sc001_attempt.get("market", {}).get("raw_sha256") or ""
    )
    current_delivery_sha = str(
        sc001_attempt.get("delivery", {}).get("raw_sha256") or ""
    )
    if str(market_sessions[-1].get("raw_sha256") or "") != current_market_sha:
        raise AlphaContractError(
            "T004 current market source does not match SC001 bytes"
        )
    if (
        str(delivery_sessions[-1].get("raw_sha256") or "")
        != current_delivery_sha
    ):
        raise AlphaContractError(
            "T004 current delivery source does not match SC001 bytes"
        )
    current_quality = delivery_sessions[-1].get("source_quality")
    if not (
        isinstance(current_quality, dict)
        and current_quality.get("status") == "READY"
    ):
        raise AlphaContractError("T004 current delivery source is not quality-ready")

    market_histories: dict[
        tuple[str, str], deque[DailyEquityObservation]
    ] = defaultdict(lambda: deque(maxlen=61))
    market_indices: dict[tuple[str, str], deque[int]] = defaultdict(
        lambda: deque(maxlen=61)
    )
    delivery_histories: dict[
        tuple[str, str], deque[DeliveryObservation]
    ] = defaultdict(lambda: deque(maxlen=21))
    delivery_indices: dict[tuple[str, str], deque[int]] = defaultdict(
        lambda: deque(maxlen=21)
    )

    market_manifest = []
    delivery_manifest = []
    current_market_by_identity: dict[
        tuple[str, str], DailyEquityObservation
    ] = {}

    for session_index, (market_session, delivery_session) in enumerate(
        zip(market_sessions, delivery_sessions, strict=True)
    ):
        session_date = market_dates[session_index]
        raw_market_sha = str(market_session.get("raw_sha256") or "")
        if len(raw_market_sha) != 64:
            raise AlphaContractError(
                f"{session_date}: T004 market SHA-256 is required"
            )
        market_manifest.append(
            {
                "session_date": session_date,
                "raw_sha256": raw_market_sha,
                "source_role": (
                    "SC001_CURRENT"
                    if session_date == feature_session
                    else "HISTORICAL_RECONSTRUCTION"
                ),
            }
        )

        market_by_symbol: dict[str, DailyEquityObservation] = {}
        seen_identity: set[tuple[str, str]] = set()
        for raw in market_session.get("equities", []):
            row = _coerce_market_row(raw)
            if row.session_date != session_date:
                raise AlphaContractError(
                    f"{session_date}: T004 market row session mismatch"
                )
            identity = (row.symbol, row.isin)
            if identity in seen_identity:
                raise AlphaContractError(
                    f"{session_date}: duplicate T004 market identity"
                )
            if row.symbol in market_by_symbol:
                raise AlphaContractError(
                    f"{session_date}: duplicate T004 market symbol"
                )
            seen_identity.add(identity)
            market_by_symbol[row.symbol] = row
            market_histories[identity].append(row)
            market_indices[identity].append(session_index)
            if session_date == feature_session:
                current_market_by_identity[identity] = row

        raw_delivery_sha = delivery_session.get("raw_sha256")
        quality = delivery_session.get("source_quality")
        quality_status = (
            str(quality.get("status"))
            if isinstance(quality, dict)
            else "UNAVAILABLE"
        )
        delivery_manifest.append(
            {
                "session_date": session_date,
                "raw_sha256": raw_delivery_sha,
                "source_quality_status": quality_status,
                "source_role": (
                    "SC001_CURRENT"
                    if session_date == feature_session
                    else "HISTORICAL_RECONSTRUCTION"
                ),
            }
        )

        if quality_status != "READY":
            continue
        delivery_by_symbol: dict[str, DeliveryObservation] = {}
        for raw in delivery_session.get("rows", []):
            row = _coerce_delivery_row(raw)
            if row.session_date != session_date:
                raise AlphaContractError(
                    f"{session_date}: T004 delivery row session mismatch"
                )
            if row.symbol in delivery_by_symbol:
                raise AlphaContractError(
                    f"{session_date}: duplicate T004 delivery symbol"
                )
            delivery_by_symbol[row.symbol] = row

        for symbol, delivery_row in delivery_by_symbol.items():
            market_row = market_by_symbol.get(symbol)
            if market_row is None:
                continue
            identity = (symbol, market_row.isin)
            delivery_histories[identity].append(delivery_row)
            delivery_indices[identity].append(session_index)

    actions = action_index(action_ledger)
    raw_rows = []
    exclusions: dict[str, int] = defaultdict(int)
    current_index = len(market_dates) - 1
    expected_market_indices = list(
        range(current_index - 60, current_index + 1)
    )
    expected_delivery_indices = list(
        range(current_index - 20, current_index + 1)
    )

    for identity in sorted(current_market_by_identity):
        symbol, isin = identity
        market_history = list(market_histories[identity])
        observed_market_indices = list(market_indices[identity])
        if (
            len(market_history) != 61
            or observed_market_indices != expected_market_indices
        ):
            exclusions["MARKET_HISTORY_NOT_CONTIGUOUS"] += 1
            continue
        if not eligible_history_for_ae001(market_history):
            exclusions["LIQUIDITY_OR_HISTORY_INELIGIBLE"] += 1
            continue

        state = actions.get(symbol.upper())
        if state is not None and state.get("status") != "READY":
            exclusions["ACTION_AUDIT_UNRESOLVED"] += 1
            continue
        if blocked_actions(
            actions,
            symbol=symbol,
            start_exclusive=market_history[0].session_date,
            end_inclusive=feature_session,
        ):
            exclusions["CORPORATE_ACTION_LOOKBACK_BLOCKED"] += 1
            continue

        delivery_history = list(delivery_histories.get(identity, ()))
        observed_delivery_indices = list(delivery_indices.get(identity, ()))
        if (
            len(delivery_history) != 21
            or observed_delivery_indices != expected_delivery_indices
        ):
            exclusions["DELIVERY_HISTORY_NOT_CONTIGUOUS"] += 1
            continue

        base_values = build_price_volume_features_from_history(market_history)
        try:
            extra_values = delivery_features(
                delivery_history,
                market_current=market_history[-1],
            )
        except AlphaContractError:
            exclusions["DELIVERY_FEATURE_INCOMPLETE"] += 1
            continue
        values = {**base_values, **extra_values}
        if len(values) != 27:
            raise AlphaContractError("T004 prospective feature count is not 27")
        for name, value in values.items():
            if value is not None and not math.isfinite(float(value)):
                raise AlphaContractError(
                    f"T004 prospective feature is non-finite: {name}"
                )
        raw_rows.append(
            {
                "symbol": symbol,
                "isin": isin,
                "raw_values": values,
            }
        )

    feature_names = sorted(
        raw_rows[0]["raw_values"] if raw_rows else []
    )
    ranked_by_feature: dict[str, dict[str, float | None]] = {}
    for feature in feature_names:
        values = {
            f"{row['symbol']}|{row['isin']}": row["raw_values"][feature]
            for row in raw_rows
        }
        ranked_by_feature[feature] = cross_sectional_percentile(values)

    ranked_rows = []
    for row in raw_rows:
        key = f"{row['symbol']}|{row['isin']}"
        ranked_rows.append(
            {
                **row,
                "values": {
                    feature: ranked_by_feature[feature][key]
                    for feature in feature_names
                },
            }
        )

    universe_sha256 = digest(
        [
            {"symbol": row["symbol"], "isin": row["isin"]}
            for row in ranked_rows
        ]
    )
    source_manifest = {
        "market": market_manifest,
        "delivery": delivery_manifest,
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
    }
    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "snapshot_id": "AE001-T004-PROSPECTIVE-FEATURES-v1",
        "trial_id": T004_TRIAL_ID,
        "feature_session": feature_session,
        "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
        "current_market_sha256": current_market_sha,
        "current_delivery_sha256": current_delivery_sha,
        "source_manifest": source_manifest,
        "source_manifest_sha256": digest(source_manifest),
        "transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "common_row_count": len(ranked_rows),
        "universe_sha256": universe_sha256,
        "exclusions": dict(sorted(exclusions.items())),
        "rows": ranked_rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    snapshot["snapshot_sha256"] = digest(snapshot)
    return snapshot


def validate_t004_feature_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("snapshot_id") != "AE001-T004-PROSPECTIVE-FEATURES-v1":
        raise AlphaContractError("unexpected T004 prospective snapshot id")
    if snapshot.get("trial_id") != T004_TRIAL_ID:
        raise AlphaContractError("unexpected T004 prospective trial id")
    if snapshot.get("outcomes_attached") is not False:
        raise AlphaContractError("T004 prospective snapshot contains outcomes")
    unsigned = copy.deepcopy(snapshot)
    stored = str(unsigned.pop("snapshot_sha256", ""))
    if stored != digest(unsigned):
        raise AlphaContractError("T004 prospective snapshot hash mismatch")
    rows = snapshot.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("T004 prospective rows must be a list")
    if int(snapshot.get("common_row_count", -1)) != len(rows):
        raise AlphaContractError("T004 prospective row count mismatch")


def build_t004_prediction_artifact(
    *,
    feature_snapshot: dict[str, Any],
    frozen_models: dict[str, Any],
    sealed_at_utc: str,
) -> dict[str, Any]:
    validate_t004_feature_snapshot(feature_snapshot)
    validate_frozen_t004_models(frozen_models)
    if (
        frozen_models["artifact_sha256"]
        != FROZEN_MODEL_ARTIFACT_SHA256
    ):
        raise AlphaContractError("T004 frozen model artifact SHA mismatch")
    if (
        frozen_models["base_model"]["model_sha256"]
        != BASE_MODEL_SHA256
        or frozen_models["augmented_model"]["model_sha256"]
        != AUGMENTED_MODEL_SHA256
    ):
        raise AlphaContractError("T004 frozen ridge model SHA mismatch")

    feature_session = str(feature_snapshot["feature_session"])
    if not prediction_deadline_open(
        sealed_at_utc,
        session_date=feature_session,
    ):
        raise AlphaContractError("T004 prospective prediction missed seal deadline")
    rows = feature_snapshot["rows"]
    if len(rows) < MIN_COMMON_STOCKS:
        raise AlphaContractError(
            f"T004 requires at least {MIN_COMMON_STOCKS} common rows"
        )

    base_model = ridge_model_from_record(frozen_models["base_model"])
    augmented_model = ridge_model_from_record(frozen_models["augmented_model"])
    values = [row["values"] for row in rows]
    base_scores = score_ridge_values(base_model, values)
    augmented_scores = score_ridge_values(augmented_model, values)

    identities = [
        f"{row['symbol']}|{row['isin']}" for row in rows
    ]
    base_rank = cross_sectional_percentile(
        dict(zip(identities, base_scores, strict=True))
    )
    augmented_rank = cross_sectional_percentile(
        dict(zip(identities, augmented_scores, strict=True))
    )

    predictions = []
    for row, identity, base, augmented in zip(
        rows,
        identities,
        base_scores,
        augmented_scores,
        strict=True,
    ):
        predictions.append(
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "values": row["values"],
                "base_prediction": base,
                "base_percentile": base_rank[identity],
                "augmented_prediction": augmented,
                "augmented_percentile": augmented_rank[identity],
            }
        )

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": "AE001-T004-PROSPECTIVE-PREDICTION-v1",
        "trial_id": T004_TRIAL_ID,
        "feature_session": feature_session,
        "sealed_at_utc": datetime.fromisoformat(sealed_at_utc)
        .astimezone(UTC)
        .isoformat(),
        "conservative_deadline_utc": conservative_prediction_deadline_utc(
            feature_session
        ).isoformat(),
        "sc001_attempt_sha256": feature_snapshot["sc001_attempt_sha256"],
        "current_market_sha256": feature_snapshot["current_market_sha256"],
        "current_delivery_sha256": feature_snapshot["current_delivery_sha256"],
        "feature_snapshot_sha256": feature_snapshot["snapshot_sha256"],
        "source_manifest_sha256": feature_snapshot["source_manifest_sha256"],
        "universe_sha256": feature_snapshot["universe_sha256"],
        "common_row_count": len(predictions),
        "frozen_model_artifact_sha256": frozen_models["artifact_sha256"],
        "base_model_sha256": base_model.model_sha256,
        "augmented_model_sha256": augmented_model.model_sha256,
        "predictions": predictions,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def validate_t004_prediction_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("artifact_id") != "AE001-T004-PROSPECTIVE-PREDICTION-v1":
        raise AlphaContractError("unexpected T004 prediction artifact id")
    if artifact.get("outcomes_attached") is not False:
        raise AlphaContractError("T004 prediction artifact contains outcomes")
    if artifact.get("live_capital_allowed") is not False:
        raise AlphaContractError("T004 prediction artifact permits live capital")
    unsigned = copy.deepcopy(artifact)
    stored = str(unsigned.pop("artifact_sha256", ""))
    if stored != digest(unsigned):
        raise AlphaContractError("T004 prediction artifact hash mismatch")
    forbidden = {
        "target_excess_return",
        "stock_return",
        "benchmark_return",
        "outcome",
    }
    for row in artifact.get("predictions", []):
        if forbidden & set(row):
            raise AlphaContractError("T004 prediction row contains outcome fields")


def _prediction_ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_t004_prediction_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": T004_PREDICTION_LEDGER_ID,
        "record_count": 0,
        "records": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _prediction_ledger_hash(ledger)
    return ledger


def validate_t004_prediction_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != T004_PREDICTION_LEDGER_ID:
        raise AlphaContractError("unexpected T004 prediction ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("T004 prediction ledger permits live capital")
    records = ledger.get("records")
    if not isinstance(records, list):
        raise AlphaContractError("T004 prediction ledger records must be a list")
    if ledger.get("record_count") != len(records):
        raise AlphaContractError("T004 prediction ledger count mismatch")
    seen_sessions: set[str] = set()
    for index, record in enumerate(records, start=1):
        if record.get("seq") != index:
            raise AlphaContractError("T004 prediction ledger sequence mismatch")
        session = str(record.get("feature_session") or "")
        if not session or session in seen_sessions:
            raise AlphaContractError("T004 prediction session must be unique")
        seen_sessions.add(session)
        stored = str(record.get("record_sha256") or "")
        unsigned = dict(record)
        unsigned.pop("record_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("T004 prediction ledger record hash mismatch")
    if str(ledger.get("ledger_sha256") or "") != _prediction_ledger_hash(ledger):
        raise AlphaContractError("T004 prediction ledger hash mismatch")


def prediction_session_recorded(
    ledger: dict[str, Any],
    session_date: str,
) -> bool:
    validate_t004_prediction_ledger(ledger)
    return any(
        record.get("feature_session") == session_date
        for record in ledger["records"]
    )


def append_t004_prediction_record(
    ledger: dict[str, Any],
    *,
    feature_session: str,
    status: str,
    sealed_at_utc: str,
    sc001_attempt_sha256: str,
    common_row_count: int | None,
    prediction_artifact_path: str | None,
    prediction_artifact_sha256: str | None,
    prediction_gzip_sha256: str | None,
    feature_artifact_path: str | None,
    feature_snapshot_sha256: str | None,
    feature_gzip_sha256: str | None,
    reason: str | None = None,
) -> dict[str, Any]:
    validate_t004_prediction_ledger(ledger)
    if prediction_session_recorded(ledger, feature_session):
        raise AlphaContractError("T004 prediction session is already recorded")
    if status not in {
        "SEALED",
        "INELIGIBLE_COMMON_STOCKS",
        "MISSED_SEAL_DEADLINE",
    }:
        raise AlphaContractError("unsupported T004 prediction ledger status")

    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    record: dict[str, Any] = {
        "seq": len(updated["records"]) + 1,
        "feature_session": feature_session,
        "status": status,
        "sealed_at_utc": sealed_at_utc,
        "sc001_attempt_sha256": sc001_attempt_sha256,
        "common_row_count": common_row_count,
        "prediction_artifact_path": prediction_artifact_path,
        "prediction_artifact_sha256": prediction_artifact_sha256,
        "prediction_gzip_sha256": prediction_gzip_sha256,
        "feature_artifact_path": feature_artifact_path,
        "feature_snapshot_sha256": feature_snapshot_sha256,
        "feature_gzip_sha256": feature_gzip_sha256,
        "reason": reason,
        "live_capital_allowed": False,
    }
    record["record_sha256"] = digest(record)
    updated["records"].append(record)
    updated["record_count"] = len(updated["records"])
    updated["ledger_sha256"] = _prediction_ledger_hash(updated)
    validate_t004_prediction_ledger(updated)
    return updated
