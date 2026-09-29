from __future__ import annotations

import copy
import statistics
from datetime import UTC, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_corporate_actions import blocked_actions, parse_share_changing_actions
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_model import evaluate_cross_sectional_predictions
from marketlab.alpha_trials import append_trial_event, trial_state
from marketlab.events import sha256_bytes
from marketlab.marketdata import IndexDailyPrice

T004_OUTCOME_LEDGER_ID = "AE001-T004-OUTCOME-LEDGER-v1"
T004_HORIZONS = (5, 20)
T004_PRIMARY_MIN_DECISIONS = 60
T004_PRIMARY_MIN_VALID_PAIRED_IC = 50


def new_t004_outcome_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": T004_OUTCOME_LEDGER_ID,
        "outcome_count": 0,
        "outcomes": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def validate_t004_outcome_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != T004_OUTCOME_LEDGER_ID:
        raise AlphaContractError("unexpected T004 outcome ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("T004 outcome ledger cannot allow live capital")
    outcomes = ledger.get("outcomes")
    if not isinstance(outcomes, list):
        raise AlphaContractError("T004 outcomes must be a list")
    if ledger.get("outcome_count") != len(outcomes):
        raise AlphaContractError("T004 outcome count mismatch")
    seen: set[tuple[str, int]] = set()
    for index, row in enumerate(outcomes, start=1):
        if row.get("seq") != index:
            raise AlphaContractError("T004 outcome sequence mismatch")
        key = (str(row.get("decision_session") or ""), int(row.get("horizon_sessions") or 0))
        if not key[0] or key[1] not in T004_HORIZONS or key in seen:
            raise AlphaContractError("T004 outcome identity is invalid or duplicated")
        seen.add(key)
        stored = str(row.get("outcome_entry_sha256") or "")
        unsigned = dict(row)
        unsigned.pop("outcome_entry_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("T004 outcome entry hash mismatch")
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("T004 outcome ledger hash mismatch")


def _stock_map(session: dict[str, Any]) -> dict[tuple[str, str], DailyEquityObservation]:
    result = {}
    for raw in session.get("equities", []):
        row = raw if isinstance(raw, DailyEquityObservation) else DailyEquityObservation(**raw)
        key = (row.symbol, row.isin)
        if key in result:
            raise AlphaContractError(f"duplicate T004 outcome stock identity: {key}")
        result[key] = row
    return result


def _benchmark(session: dict[str, Any]) -> IndexDailyPrice:
    raw = session.get("benchmark")
    if raw is None:
        raise AlphaContractError("T004 outcome session lacks benchmark")
    return raw if isinstance(raw, IndexDailyPrice) else IndexDailyPrice(**raw)


def build_t004_horizon_outcome(
    *,
    decision_artifact: dict[str, Any],
    market_sessions: list[dict[str, Any]],
    corporate_action_payload: object,
    corporate_action_raw: bytes,
    horizon_sessions: int,
) -> dict[str, Any]:
    if horizon_sessions not in T004_HORIZONS:
        raise AlphaContractError("unsupported T004 outcome horizon")
    if decision_artifact.get("outcomes_attached") is not False:
        raise AlphaContractError("T004 decision artifact must remain outcome-free")

    decision_session = str(decision_artifact.get("session_date") or "")
    sessions = sorted(
        [
            row
            for row in market_sessions
            if str(row.get("session_date") or "") > decision_session
        ],
        key=lambda row: str(row["session_date"]),
    )
    if len(sessions) < horizon_sessions:
        raise AlphaContractError(
            f"T004 H{horizon_sessions} outcome is not mature for {decision_session}"
        )
    holding = sessions[:horizon_sessions]
    entry = holding[0]
    exit_row = holding[-1]
    entry_session = str(entry["session_date"])
    exit_session = str(exit_row["session_date"])

    entry_stocks = _stock_map(entry)
    exit_stocks = _stock_map(exit_row)
    benchmark_entry = _benchmark(entry)
    benchmark_exit = _benchmark(exit_row)
    benchmark_return = (
        benchmark_exit.close_price / benchmark_entry.open_price - 1.0
    )

    base_predictions = decision_artifact.get("base_predictions")
    augmented_predictions = decision_artifact.get("augmented_predictions")
    if not isinstance(base_predictions, list) or not isinstance(
        augmented_predictions, list
    ):
        raise AlphaContractError("T004 decision predictions are missing")
    base_identity = [
        (str(row["symbol"]), str(row["isin"])) for row in base_predictions
    ]
    augmented_identity = [
        (str(row["symbol"]), str(row["isin"])) for row in augmented_predictions
    ]
    if base_identity != augmented_identity:
        raise AlphaContractError("T004 decision base/augmented identities differ")

    base_by_identity = {
        (str(row["symbol"]), str(row["isin"])): float(row["prediction"])
        for row in base_predictions
    }
    augmented_by_identity = {
        (str(row["symbol"]), str(row["isin"])): float(row["prediction"])
        for row in augmented_predictions
    }
    action_states = parse_share_changing_actions(corporate_action_payload)

    valid_rows = []
    exclusions = {
        "missing_entry_identity": 0,
        "missing_exit_identity": 0,
        "corporate_action_blocked": 0,
        "corporate_action_unresolved": 0,
    }
    for identity in base_identity:
        symbol, isin = identity
        entry_stock = entry_stocks.get(identity)
        if entry_stock is None:
            exclusions["missing_entry_identity"] += 1
            continue
        exit_stock = exit_stocks.get(identity)
        if exit_stock is None:
            exclusions["missing_exit_identity"] += 1
            continue

        state = action_states.get(symbol)
        if state is not None and state.get("status") != "READY":
            exclusions["corporate_action_unresolved"] += 1
            continue
        if state is not None and blocked_actions(
            {symbol: state},
            symbol=symbol,
            start_exclusive=entry_session,
            end_inclusive=exit_session,
        ):
            exclusions["corporate_action_blocked"] += 1
            continue

        stock_return = exit_stock.close_price / entry_stock.open_price - 1.0
        target = stock_return - benchmark_return
        valid_rows.append(
            {
                "symbol": symbol,
                "isin": isin,
                "target_excess_return": target,
                "base_prediction": base_by_identity[identity],
                "augmented_prediction": augmented_by_identity[identity],
            }
        )

    base_eval_rows = [
        {
            "symbol": row["symbol"],
            "isin": row["isin"],
            "feature_session": decision_session,
            "prediction": row["base_prediction"],
            "target_excess_return": row["target_excess_return"],
        }
        for row in valid_rows
    ]
    augmented_eval_rows = [
        {
            "symbol": row["symbol"],
            "isin": row["isin"],
            "feature_session": decision_session,
            "prediction": row["augmented_prediction"],
            "target_excess_return": row["target_excess_return"],
        }
        for row in valid_rows
    ]
    base_metrics = evaluate_cross_sectional_predictions(base_eval_rows)
    augmented_metrics = evaluate_cross_sectional_predictions(augmented_eval_rows)

    base_session = (
        base_metrics["session_metrics"][0]
        if base_metrics["session_metrics"]
        else None
    )
    augmented_session = (
        augmented_metrics["session_metrics"][0]
        if augmented_metrics["session_metrics"]
        else None
    )
    valid_paired_ic = (
        base_session is not None
        and augmented_session is not None
        and base_session.get("rank_ic") is not None
        and augmented_session.get("rank_ic") is not None
    )
    metric_delta = None
    if base_session is not None and augmented_session is not None:
        metric_delta = {
            "rank_ic": (
                None
                if base_session.get("rank_ic") is None
                or augmented_session.get("rank_ic") is None
                else float(augmented_session["rank_ic"])
                - float(base_session["rank_ic"])
            ),
            "top_minus_bottom_spread": (
                float(augmented_session["top_minus_bottom_spread"])
                - float(base_session["top_minus_bottom_spread"])
            ),
            "top_decile_excess": (
                float(augmented_session["top_decile_mean_excess"])
                - float(base_session["top_decile_mean_excess"])
            ),
        }

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": f"AE001-T004-H{horizon_sessions}-OUTCOME-v1",
        "trial_id": "AE001-T004",
        "decision_session": decision_session,
        "decision_artifact_sha256": decision_artifact["artifact_sha256"],
        "horizon_sessions": horizon_sessions,
        "entry_session": entry_session,
        "exit_session": exit_session,
        "benchmark_return": benchmark_return,
        "holding_session_evidence": [
            {
                "session_date": str(row["session_date"]),
                "udiff_sha256": str(row["udiff_sha256"]),
                "benchmark_sha256": str(row["benchmark_sha256"]),
            }
            for row in holding
        ],
        "corporate_action_raw_sha256": sha256_bytes(corporate_action_raw),
        "decision_row_count": len(base_identity),
        "valid_outcome_row_count": len(valid_rows),
        "exclusions": exclusions,
        "base_metrics": base_metrics,
        "augmented_metrics": augmented_metrics,
        "paired_metric_delta": metric_delta,
        "valid_paired_ic": valid_paired_ic,
        "rows": valid_rows,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def append_t004_outcome(
    ledger: dict[str, Any],
    *,
    outcome_artifact: dict[str, Any],
    artifact_path: str,
) -> dict[str, Any]:
    validate_t004_outcome_ledger(ledger)
    key = (
        str(outcome_artifact["decision_session"]),
        int(outcome_artifact["horizon_sessions"]),
    )
    if any(
        (row["decision_session"], int(row["horizon_sessions"])) == key
        for row in ledger["outcomes"]
    ):
        raise AlphaContractError(
            f"T004 outcome already exists for {key[0]} H{key[1]}"
        )
    entry: dict[str, Any] = {
        "seq": len(ledger["outcomes"]) + 1,
        "decision_session": key[0],
        "horizon_sessions": key[1],
        "artifact_path": artifact_path,
        "artifact_sha256": outcome_artifact["artifact_sha256"],
        "entry_session": outcome_artifact["entry_session"],
        "exit_session": outcome_artifact["exit_session"],
        "valid_outcome_row_count": outcome_artifact["valid_outcome_row_count"],
        "valid_paired_ic": outcome_artifact["valid_paired_ic"],
        "live_capital_allowed": False,
    }
    entry["outcome_entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["outcomes"].append(entry)
    updated["outcome_count"] = len(updated["outcomes"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_t004_outcome_ledger(updated)
    return updated


def _session_metric(outcome: dict[str, Any], model_key: str) -> dict[str, Any] | None:
    metrics = outcome[f"{model_key}_metrics"]["session_metrics"]
    return metrics[0] if metrics else None


def _aggregate_report(
    outcome_artifacts: list[dict[str, Any]],
    *,
    model_key: str,
) -> dict[str, Any]:
    rows = []
    for artifact in outcome_artifacts:
        metric = _session_metric(artifact, model_key)
        if metric is not None:
            rows.append(metric)
    return {"session_metrics": rows}


def _mean_metric(
    outcome_artifacts: list[dict[str, Any]],
    *,
    model_key: str,
    field: str,
) -> float | None:
    values = []
    for artifact in outcome_artifacts:
        metric = _session_metric(artifact, model_key)
        if metric is not None and metric.get(field) is not None:
            values.append(float(metric[field]))
    return statistics.mean(values) if values else None


def _primary_result_event(
    trial_ledger: dict[str, Any],
) -> dict[str, Any] | None:
    state = trial_state(trial_ledger, "AE001-T004")
    for event in state["results"]:
        if event["payload"].get("result_kind") == "PRIMARY_5D":
            return event
    return None


def _secondary_result_event(
    trial_ledger: dict[str, Any],
) -> dict[str, Any] | None:
    state = trial_state(trial_ledger, "AE001-T004")
    for event in state["results"]:
        if event["payload"].get("result_kind") == "SECONDARY_20D":
            return event
    return None


def find_t004_primary_cohort(
    *,
    decisions: list[dict[str, Any]],
    outcome_ledger: dict[str, Any],
) -> list[str] | None:
    validate_t004_outcome_ledger(outcome_ledger)
    if len(decisions) < T004_PRIMARY_MIN_DECISIONS:
        return None
    h5 = {
        row["decision_session"]: row
        for row in outcome_ledger["outcomes"]
        if int(row["horizon_sessions"]) == 5
    }
    for size in range(T004_PRIMARY_MIN_DECISIONS, len(decisions) + 1):
        prefix = decisions[:size]
        sessions = [str(row["session_date"]) for row in prefix]
        if not all(session in h5 for session in sessions):
            return None
        valid = sum(bool(h5[session]["valid_paired_ic"]) for session in sessions)
        if valid >= T004_PRIMARY_MIN_VALID_PAIRED_IC:
            return sessions
    return None


def finalize_t004_results(
    *,
    trial_ledger: dict[str, Any],
    decision_ledger: dict[str, Any],
    outcome_ledger: dict[str, Any],
    outcome_artifacts: list[dict[str, Any]],
    recorded_at_utc: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validate_t004_outcome_ledger(outcome_ledger)
    now = recorded_at_utc or datetime.now(UTC).isoformat()
    updated = copy.deepcopy(trial_ledger)
    emitted: list[dict[str, Any]] = []
    by_key = {
        (artifact["decision_session"], int(artifact["horizon_sessions"])): artifact
        for artifact in outcome_artifacts
    }

    primary = _primary_result_event(updated)
    if primary is None:
        cohort = find_t004_primary_cohort(
            decisions=decision_ledger["decisions"],
            outcome_ledger=outcome_ledger,
        )
        if cohort is not None:
            artifacts = [by_key[(session, 5)] for session in cohort]
            base_report = _aggregate_report(artifacts, model_key="base")
            augmented_report = _aggregate_report(artifacts, model_key="augmented")
            paired = paired_report_difference_inference(
                augmented_report,
                base_report,
                max_lag=4,
            )
            rank = paired["metrics"]["rank_ic"]
            spread = paired["metrics"]["top_minus_bottom_spread"]
            supported = (
                rank["mean"] is not None
                and float(rank["mean"]) > 0
                and rank["p_value_two_sided"] is not None
                and float(rank["p_value_two_sided"]) < 0.05
                and spread["mean"] is not None
                and float(spread["mean"]) > 0
                and spread["p_value_two_sided"] is not None
                and float(spread["p_value_two_sided"]) < 0.05
            )
            payload = {
                "result_kind": "PRIMARY_5D",
                "status": "SUPPORTED" if supported else "NOT_SUPPORTED",
                "cohort_rule": "T004_P2_SMALLEST_QUALIFYING_CANONICAL_PREFIX",
                "cohort_size": len(cohort),
                "cohort_decision_sessions": cohort,
                "valid_paired_ic_session_count": sum(
                    by_key[(session, 5)]["valid_paired_ic"] for session in cohort
                ),
                "base_mean_rank_ic": _mean_metric(
                    artifacts, model_key="base", field="rank_ic"
                ),
                "augmented_mean_rank_ic": _mean_metric(
                    artifacts, model_key="augmented", field="rank_ic"
                ),
                "base_mean_top_minus_bottom_spread": _mean_metric(
                    artifacts, model_key="base", field="top_minus_bottom_spread"
                ),
                "augmented_mean_top_minus_bottom_spread": _mean_metric(
                    artifacts,
                    model_key="augmented",
                    field="top_minus_bottom_spread",
                ),
                "paired_augmented_minus_base": paired,
                "tc001_status": "NOT_IMPLEMENTED_REQUIRED_BEFORE_PORTFOLIO_PROMOTION",
                "live_capital_allowed": False,
            }
            updated = append_trial_event(
                updated,
                event_type="TRIAL_RESULT_RECORDED",
                trial_id="AE001-T004",
                recorded_at_utc=now,
                payload=payload,
            )
            emitted.append(updated["events"][-1])
            primary = updated["events"][-1]

    secondary = _secondary_result_event(updated)
    if primary is not None and secondary is None:
        cohort = list(primary["payload"]["cohort_decision_sessions"])
        if all((session, 20) in by_key for session in cohort):
            artifacts = [by_key[(session, 20)] for session in cohort]
            base_report = _aggregate_report(artifacts, model_key="base")
            augmented_report = _aggregate_report(artifacts, model_key="augmented")
            paired = paired_report_difference_inference(
                augmented_report,
                base_report,
                max_lag=19,
            )
            payload = {
                "result_kind": "SECONDARY_20D",
                "status": "REPORTED_NON_RESCUING_SECONDARY",
                "primary_result_event_sha256": primary["event_sha256"],
                "cohort_size": len(cohort),
                "cohort_decision_sessions": cohort,
                "base_mean_rank_ic": _mean_metric(
                    artifacts, model_key="base", field="rank_ic"
                ),
                "augmented_mean_rank_ic": _mean_metric(
                    artifacts, model_key="augmented", field="rank_ic"
                ),
                "base_mean_top_minus_bottom_spread": _mean_metric(
                    artifacts, model_key="base", field="top_minus_bottom_spread"
                ),
                "augmented_mean_top_minus_bottom_spread": _mean_metric(
                    artifacts,
                    model_key="augmented",
                    field="top_minus_bottom_spread",
                ),
                "paired_augmented_minus_base": paired,
                "rescues_failed_primary": False,
                "live_capital_allowed": False,
            }
            updated = append_trial_event(
                updated,
                event_type="TRIAL_RESULT_RECORDED",
                trial_id="AE001-T004",
                recorded_at_utc=now,
                payload=payload,
            )
            emitted.append(updated["events"][-1])

    return updated, emitted
