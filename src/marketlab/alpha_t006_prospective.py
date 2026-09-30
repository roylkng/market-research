from __future__ import annotations

import copy
import math
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_corporate_actions import (
    blocked_actions,
    parse_share_changing_actions,
)
from marketlab.alpha_delivery import (
    DELIVERY_DEFINITIONS,
    DeliveryObservation,
    delivery_features,
    delivery_session_quality,
    parse_sec_bhavdata_full,
)
from marketlab.alpha_futures import (
    FUTURES_DEFINITIONS,
    FuturesContractObservation,
    futures_features,
    parse_fo_udiff_stock_futures,
)
from marketlab.alpha_market import (
    build_price_volume_features_from_history,
    eligible_history_for_ae001,
    parse_udiff_eq_panel,
)
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_t004_prospective import (
    _market_histories,
    _rank_feature_rows,
    _score_model,
    t004_cutoff_utc,
)
from marketlab.alpha_t006 import validate_frozen_t006_models
from marketlab.events import sha256_bytes

T006_DECISION_LEDGER_ID = "AE001-T006-DECISION-LEDGER-v1"
T006_START_DATE = date(2026, 10, 1)
T006_MIN_COMMON_STOCKS = 100


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_t006_decision_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": T006_DECISION_LEDGER_ID,
        "decision_count": 0,
        "decisions": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_t006_decision_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != T006_DECISION_LEDGER_ID:
        raise AlphaContractError("unexpected T006 decision ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("T006 decision ledger cannot allow live capital")
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        raise AlphaContractError("T006 decisions must be a list")
    if ledger.get("decision_count") != len(decisions):
        raise AlphaContractError("T006 decision count mismatch")
    seen: set[str] = set()
    for index, row in enumerate(decisions, start=1):
        if row.get("seq") != index:
            raise AlphaContractError("T006 decision sequence mismatch")
        session = str(row.get("session_date") or "")
        if not session or session in seen:
            raise AlphaContractError("T006 decision sessions must be unique")
        seen.add(session)
        stored = str(row.get("decision_entry_sha256") or "")
        unsigned = dict(row)
        unsigned.pop("decision_entry_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("T006 decision entry hash mismatch")
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("T006 decision ledger hash mismatch")


def eligible_sc002_attempt(
    source_ledger: dict[str, Any],
    *,
    session_date: str,
) -> dict[str, Any]:
    attempts = [
        row
        for row in source_ledger.get("attempts", [])
        if row.get("session_date") == session_date
        and row.get("eligible_before_cutoff") is True
    ]
    if not attempts:
        raise AlphaContractError(
            f"{session_date}: no SC002 eligible-before-cutoff source attempt"
        )
    attempts.sort(
        key=lambda row: (
            str(row.get("captured_at_utc") or ""),
            int(row.get("seq") or 0),
        )
    )
    return attempts[0]


def build_t006_current_feature_rows(
    *,
    prior_market_sessions: list[dict[str, Any]],
    current_market_raw: bytes,
    prior_delivery_sessions: list[dict[str, Any]],
    current_delivery_raw: bytes,
    current_futures_raw: bytes,
    session_date: str,
    corporate_action_payload: object,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    day = date.fromisoformat(session_date)
    if day < T006_START_DATE:
        raise AlphaContractError("T006 decision precedes frozen start boundary")

    prior_market = sorted(
        prior_market_sessions,
        key=lambda row: str(row["session_date"]),
    )
    if len(prior_market) < 60:
        raise AlphaContractError("T006 requires at least 60 prior market sessions")
    prior_market = prior_market[-60:]
    if str(prior_market[-1]["session_date"]) >= session_date:
        raise AlphaContractError("T006 prior market history crosses decision session")

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
    histories, history_indices, market_by_session = _market_histories(
        market_sessions
    )

    prior_delivery = sorted(
        prior_delivery_sessions,
        key=lambda row: str(row["session_date"]),
    )
    if len(prior_delivery) < 20:
        raise AlphaContractError("T006 requires at least 20 prior delivery sessions")
    prior_delivery = prior_delivery[-20:]
    expected_prior_dates = [
        str(row["session_date"]) for row in prior_market[-20:]
    ]
    if [str(row["session_date"]) for row in prior_delivery] != expected_prior_dates:
        raise AlphaContractError(
            "T006 delivery history does not match prior market sessions"
        )

    current_delivery_rows = parse_sec_bhavdata_full(
        current_delivery_raw,
        session_date=day,
    )
    current_delivery_quality = delivery_session_quality(current_delivery_rows)
    if current_delivery_quality["status"] != "READY":
        raise AlphaContractError("T006 current delivery source fails quality")

    delivery_sessions = [
        *prior_delivery,
        {
            "session_date": session_date,
            "source_quality": current_delivery_quality,
            "raw_sha256": sha256_bytes(current_delivery_raw),
            "rows": [asdict(row) for row in current_delivery_rows],
        },
    ]
    delivery_histories: dict[
        tuple[str, str], list[DeliveryObservation]
    ] = {}
    delivery_indices: dict[tuple[str, str], list[int]] = {}
    for delivery_index, session in enumerate(delivery_sessions):
        session_day = str(session["session_date"])
        quality = session.get("source_quality")
        if not isinstance(quality, dict) or quality.get("status") != "READY":
            continue
        market_map = market_by_session.get(session_day)
        if market_map is None:
            raise AlphaContractError(
                f"{session_day}: T006 delivery history lacks market map"
            )
        seen: set[str] = set()
        for raw in session["rows"]:
            delivery = (
                raw
                if isinstance(raw, DeliveryObservation)
                else DeliveryObservation(**raw)
            )
            if delivery.symbol in seen:
                raise AlphaContractError(
                    f"{session_day}: duplicate T006 delivery symbol"
                )
            seen.add(delivery.symbol)
            market_row = market_map.get(delivery.symbol)
            if market_row is None:
                continue
            identity = (market_row.symbol, market_row.isin)
            delivery_histories.setdefault(identity, []).append(delivery)
            delivery_indices.setdefault(identity, []).append(delivery_index)

    futures_rows, futures_diagnostics = parse_fo_udiff_stock_futures(
        current_futures_raw,
        session_date=day,
    )
    contracts_by_symbol: dict[str, list[FuturesContractObservation]] = {}
    for contract in futures_rows:
        contracts_by_symbol.setdefault(contract.symbol, []).append(contract)

    action_states = parse_share_changing_actions(corporate_action_payload)
    all_names = [
        definition.name
        for definition in [
            *PRICE_VOLUME_DEFINITIONS,
            *DELIVERY_DEFINITIONS,
            *FUTURES_DEFINITIONS,
        ]
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
        "no_stock_futures": 0,
        "invalid_futures_structure": 0,
    }

    for symbol in sorted(current_map):
        current = current_map[symbol]
        identity = (current.symbol, current.isin)
        market_history = histories.get(identity, [])
        market_positions = history_indices.get(identity, [])
        if len(market_history) != 61 or market_positions != list(range(61)):
            exclusions["market_history"] += 1
            continue
        if not eligible_history_for_ae001(market_history):
            exclusions["liquidity"] += 1
            continue

        action_state = action_states.get(symbol)
        if action_state is not None and action_state.get("status") != "READY":
            exclusions["corporate_action_unresolved"] += 1
            continue
        if action_state is not None and blocked_actions(
            {symbol: action_state},
            symbol=symbol,
            start_exclusive=market_history[0].session_date,
            end_inclusive=session_date,
        ):
            exclusions["corporate_action"] += 1
            continue

        delivery_history = delivery_histories.get(identity, [])
        delivery_positions = delivery_indices.get(identity, [])
        if len(delivery_history) != 21 or delivery_positions != list(range(21)):
            exclusions["delivery_history"] += 1
            continue

        contracts = contracts_by_symbol.get(symbol)
        if not contracts:
            exclusions["no_stock_futures"] += 1
            continue

        try:
            values = {
                **build_price_volume_features_from_history(market_history),
                **delivery_features(
                    delivery_history,
                    market_current=current,
                ),
                **futures_features(
                    contracts,
                    market_current=current,
                ),
            }
        except AlphaContractError as exc:
            if "futures" in str(exc).lower() or "T005" in str(exc):
                exclusions["invalid_futures_structure"] += 1
            else:
                exclusions["delivery_value"] += 1
            continue

        if set(values) != set(all_names):
            raise AlphaContractError("T006 feature set differs from frozen 37")
        if any(
            value is not None and not math.isfinite(float(value))
            for value in values.values()
        ):
            raise AlphaContractError("T006 feature row contains nonfinite value")
        rows.append(
            {
                "symbol": symbol,
                "isin": current.isin,
                "values": values,
            }
        )

    ranked = _rank_feature_rows(rows, all_names)
    diagnostics = {
        "common_row_count": len(ranked),
        "exclusions": exclusions,
        "futures_parser": futures_diagnostics,
        "feature_names": all_names,
        "feature_rows_sha256": digest(ranked),
    }
    return ranked, diagnostics


def build_t006_decision_artifact(
    *,
    session_date: str,
    sc001_attempt: dict[str, Any],
    sc002_attempt: dict[str, Any],
    prior_market_sessions: list[dict[str, Any]],
    current_market_raw: bytes,
    prior_delivery_sessions: list[dict[str, Any]],
    current_delivery_raw: bytes,
    current_futures_raw: bytes,
    corporate_action_payload: object,
    corporate_action_raw: bytes,
    frozen_models: dict[str, Any],
    sealed_at_utc: str | None = None,
) -> dict[str, Any]:
    validate_frozen_t006_models(frozen_models)
    if sc001_attempt.get("eligible_before_cutoff") is not True:
        raise AlphaContractError("T006 requires SC001 cutoff eligibility")
    if sc002_attempt.get("eligible_before_cutoff") is not True:
        raise AlphaContractError("T006 requires SC002 cutoff eligibility")
    if (
        sc001_attempt.get("session_date") != session_date
        or sc002_attempt.get("session_date") != session_date
    ):
        raise AlphaContractError("T006 source-ledger session mismatch")

    rows, diagnostics = build_t006_current_feature_rows(
        prior_market_sessions=prior_market_sessions,
        current_market_raw=current_market_raw,
        prior_delivery_sessions=prior_delivery_sessions,
        current_delivery_raw=current_delivery_raw,
        current_futures_raw=current_futures_raw,
        session_date=session_date,
        corporate_action_payload=corporate_action_payload,
    )
    if len(rows) < T006_MIN_COMMON_STOCKS:
        raise AlphaContractError(
            f"T006 common row count below frozen minimum: {len(rows)}"
        )

    base = _score_model(frozen_models["base_model"], rows)
    augmented = _score_model(frozen_models["augmented_model"], rows)
    base_ids = [(row["symbol"], row["isin"]) for row in base]
    augmented_ids = [(row["symbol"], row["isin"]) for row in augmented]
    if base_ids != augmented_ids:
        raise AlphaContractError("T006 base/augmented prediction rows differ")

    sealed = (
        datetime.now(UTC)
        if sealed_at_utc is None
        else datetime.fromisoformat(sealed_at_utc)
    )
    if sealed.tzinfo is None:
        raise AlphaContractError("T006 sealed_at_utc must be timezone-aware")
    sealed = sealed.astimezone(UTC)
    if sealed > t004_cutoff_utc(session_date):
        raise AlphaContractError("T006 prediction sealing missed decision cutoff")

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": "AE001-T006-DECISION-v1",
        "trial_id": "AE001-T006",
        "session_date": session_date,
        "sealed_at_utc": sealed.isoformat(),
        "decision_cutoff_utc": t004_cutoff_utc(session_date).isoformat(),
        "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
        "sc002_attempt_sha256": sc002_attempt["attempt_sha256"],
        "sc001_captured_at_utc": sc001_attempt["captured_at_utc"],
        "sc002_captured_at_utc": sc002_attempt["captured_at_utc"],
        "current_market_sha256": sha256_bytes(current_market_raw),
        "current_delivery_sha256": sha256_bytes(current_delivery_raw),
        "current_futures_sha256": sha256_bytes(current_futures_raw),
        "corporate_action_raw_sha256": sha256_bytes(corporate_action_raw),
        "prior_market_support_sha256": digest(prior_market_sessions),
        "prior_delivery_support_sha256": digest(prior_delivery_sessions),
        "frozen_model_artifact_sha256": frozen_models["artifact_sha256"],
        "base_model_sha256": frozen_models["base_model"]["model_sha256"],
        "augmented_model_sha256": frozen_models["augmented_model"][
            "model_sha256"
        ],
        "common_row_count": len(rows),
        "feature_rows_sha256": diagnostics["feature_rows_sha256"],
        "feature_exclusions": diagnostics["exclusions"],
        "futures_parser_diagnostics": diagnostics["futures_parser"],
        "base_predictions": base,
        "augmented_predictions": augmented,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def append_t006_decision(
    ledger: dict[str, Any],
    *,
    decision_artifact: dict[str, Any],
    artifact_path: str,
) -> dict[str, Any]:
    validate_t006_decision_ledger(ledger)
    session = str(decision_artifact.get("session_date") or "")
    if any(row["session_date"] == session for row in ledger["decisions"]):
        raise AlphaContractError(f"T006 decision already exists for {session}")
    if decision_artifact.get("outcomes_attached") is not False:
        raise AlphaContractError("T006 canonical decision cannot contain outcomes")

    entry = {
        "seq": len(ledger["decisions"]) + 1,
        "session_date": session,
        "artifact_path": artifact_path,
        "artifact_sha256": decision_artifact["artifact_sha256"],
        "sealed_at_utc": decision_artifact["sealed_at_utc"],
        "common_row_count": decision_artifact["common_row_count"],
        "sc001_attempt_sha256": decision_artifact["sc001_attempt_sha256"],
        "sc002_attempt_sha256": decision_artifact["sc002_attempt_sha256"],
        "base_model_sha256": decision_artifact["base_model_sha256"],
        "augmented_model_sha256": decision_artifact["augmented_model_sha256"],
        "live_capital_allowed": False,
    }
    entry["decision_entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["decisions"].append(entry)
    updated["decision_count"] = len(updated["decisions"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_t006_decision_ledger(updated)
    return updated
