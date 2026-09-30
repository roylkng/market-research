from __future__ import annotations

import copy
import statistics
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.ab001 import (
    build_alpha_library,
    incremental_alpha_contribution,
    pairwise_alpha_diagnostics,
    standalone_alpha_reports,
)
from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import newey_west_mean_inference
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_model import (
    ModelExample,
    fit_ridge,
    predict_ridge,
    project_examples,
    purge_training_examples,
)
from marketlab.alpha_multihorizon import build_action_safe_horizon_examples
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS

PILOT_ID = "AB001-P002-v1"
HORIZON = 20
RIDGE_L2 = 1.0
H024_CUTOFF_SESSION = "2026-09-11"
DECISION_CUTOFF = time(18, 30, 0)
ALPHA_AE001 = "AB001-P002-A1"
ALPHA_H024 = "AB001-P002-H024"
IST = ZoneInfo("Asia/Kolkata")

FOLDS = (
    {"start": "2026-04-01", "end": "2026-06-30"},
    {"start": "2026-07-01", "end": "2026-08-27"},
)

EXPECTED_MARKET_SHA = (
    "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
)
EXPECTED_BASE_FEATURE_SHA = (
    "300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8"
)
EXPECTED_ACTION_SHA = (
    "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
)
EXPECTED_AUGMENTED_FEATURE_SHA = (
    "99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90"
)
EXPECTED_H024_EVENT_PANEL_SHA = (
    "65b957a2a66144194690f0298602ca0118eb4af8e725cce5df7549da6b1baec4"
)
EXPECTED_H024_SOURCE_RAW_SHA = (
    "94bb81839c7d868736f830e88a3feb83538a04dfc7be01d546a7839e2bf3d101"
)


def _require_hash(
    payload: dict[str, Any],
    *,
    field: str,
    expected: str,
    name: str,
) -> None:
    observed = str(payload.get(field) or "")
    if observed != expected:
        raise AlphaContractError(
            f"AB001 P002 {name} does not reproduce frozen input: "
            f"{observed} != {expected}"
        )


def _verify_h024_event_panel(event_panel: dict[str, Any]) -> None:
    stored = str(event_panel.get("event_panel_sha256") or "")
    unsigned = copy.deepcopy(event_panel)
    unsigned.pop("event_panel_sha256", None)
    if digest(unsigned) != stored:
        raise AlphaContractError("AB001 P002 H024 event panel hash mismatch")
    if stored != EXPECTED_H024_EVENT_PANEL_SHA:
        raise AlphaContractError(
            "AB001 P002 H024 event panel is not the frozen challenge panel"
        )
    if event_panel.get("outcome_data_attached") is not False:
        raise AlphaContractError(
            "AB001 P002 H024 event panel unexpectedly contains outcomes"
        )
    if int(event_panel.get("event_count") or 0) != 209:
        raise AlphaContractError(
            "AB001 P002 H024 event count differs from frozen panel"
        )


def _parse_h024_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise AlphaContractError("AB001 P002 H024 timestamp is missing")
    try:
        return datetime.strptime(value.strip(), "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST)
    except ValueError as exc:
        raise AlphaContractError(
            f"AB001 P002 unsupported H024 timestamp: {value}"
        ) from exc


def _source_by_app(
    source_panel: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    records = source_panel.get("records")
    if not isinstance(records, list) or len(records) != 785:
        raise AlphaContractError(
            "AB001 P002 H024 source panel does not contain frozen 785 records"
        )
    result = {}
    for row in records:
        if not isinstance(row, dict):
            raise AlphaContractError("AB001 P002 malformed H024 source record")
        app_id = str(row.get("app_id") or "")
        if not app_id or app_id in result:
            raise AlphaContractError(
                "AB001 P002 H024 source app_id is missing or duplicated"
            )
        _parse_h024_timestamp(row.get("exchange_disseminated_at_ist"))
        result[app_id] = row
    return result


def _event_source_timestamp(
    event: dict[str, Any],
    *,
    source_by_app: dict[str, dict[str, Any]],
) -> tuple[datetime, bool]:
    app_ids = event.get("app_ids")
    if not isinstance(app_ids, list) or not app_ids:
        raise AlphaContractError("AB001 P002 H024 event app_ids are missing")
    symbol = str(event.get("symbol") or "").strip().upper()
    source_rows = []
    for app_id_raw in app_ids:
        app_id = str(app_id_raw)
        source = source_by_app.get(app_id)
        if source is None:
            raise AlphaContractError(
                f"AB001 P002 H024 event references unknown app_id {app_id}"
            )
        if str(source.get("symbol") or "").strip().upper() != symbol:
            raise AlphaContractError(
                f"AB001 P002 H024 app_id {app_id} symbol mismatch"
            )
        source_rows.append(source)
    earliest = min(
        _parse_h024_timestamp(row["exchange_disseminated_at_ist"])
        for row in source_rows
    )
    aggregate = _parse_h024_timestamp(
        event.get("exchange_disseminated_at_ist")
    )
    return earliest, aggregate != earliest


def _fold_train_validation(
    examples: list[ModelExample],
    *,
    fold: dict[str, str],
) -> tuple[list[ModelExample], list[ModelExample]]:
    start = str(fold["start"])
    end = str(fold["end"])
    train = purge_training_examples(
        examples,
        validation_start_session=start,
    )
    validation = [
        row for row in examples if start <= row.feature_session <= end
    ]
    if len(train) < 100:
        raise AlphaContractError(
            f"AB001 P002 fold {start}: insufficient purged training data"
        )
    if not validation:
        raise AlphaContractError(
            f"AB001 P002 fold {start}: validation is empty"
        )
    return train, validation


def _causal_h024_events(
    *,
    event_panel: dict[str, Any],
    source_panel: dict[str, Any],
    examples: list[ModelExample],
    market_session_dates: list[str],
) -> tuple[
    dict[str, set[tuple[str, str]]],
    dict[str, Any],
]:
    source_map = _source_by_app(source_panel)
    session_index = {
        session: index for index, session in enumerate(market_session_dates)
    }
    example_by_key = {
        (row.feature_session, row.symbol, row.isin): row
        for row in examples
    }
    if len(example_by_key) != len(examples):
        raise AlphaContractError(
            "AB001 P002 20D examples contain duplicate stock-session identities"
        )

    event_identities: dict[str, set[tuple[str, str]]] = defaultdict(set)
    reason_counts: dict[str, int] = defaultdict(int)
    timestamp_mismatches = 0
    accepted_events = []

    for event in event_panel["events"]:
        timestamp, mismatch = _event_source_timestamp(
            event,
            source_by_app=source_map,
        )
        timestamp_mismatches += int(mismatch)
        decision_session = timestamp.date().isoformat()
        session_position = session_index.get(decision_session)
        if session_position is None:
            reason_counts["DISCLOSED_NON_SESSION_DATE"] += 1
            continue
        if timestamp.time() > DECISION_CUTOFF:
            reason_counts["AFTER_1830_IST"] += 1
            continue
        if session_position + 1 >= len(market_session_dates):
            reason_counts["NO_NEXT_MARKET_SESSION"] += 1
            continue
        expected_entry = market_session_dates[session_position + 1]
        entry_session = str(event.get("entry_session_date") or "")
        if entry_session != expected_entry:
            reason_counts["ENTRY_NOT_IMMEDIATE_NEXT_SESSION"] += 1
            continue

        exit_index = session_position + HORIZON
        if exit_index >= len(market_session_dates):
            reason_counts["H20_NOT_MATURE_BY_MARKET_PANEL"] += 1
            continue
        exit_session = market_session_dates[exit_index]
        if exit_session > H024_CUTOFF_SESSION:
            reason_counts["H20_NOT_MATURE_BY_H024_CUTOFF"] += 1
            continue

        symbol = str(event.get("symbol") or "").strip().upper()
        isin = str(event.get("entry_isin") or "").strip()
        if not symbol or not isin:
            raise AlphaContractError("AB001 P002 H024 event identity is missing")
        example = example_by_key.get((decision_session, symbol, isin))
        if example is None:
            reason_counts["NO_COMMON_COMPLETE_AE001_ROW"] += 1
            continue
        if example.entry_session != entry_session:
            raise AlphaContractError(
                "AB001 P002 H024/AE001 entry-session alignment mismatch"
            )
        if example.exit_session != exit_session:
            raise AlphaContractError(
                "AB001 P002 H024/AE001 20D exit-session alignment mismatch"
            )
        event_identities[decision_session].add((symbol, isin))
        accepted_events.append(
            {
                "event_id": str(event["event_id"]),
                "symbol": symbol,
                "isin": isin,
                "decision_session": decision_session,
                "entry_session": entry_session,
                "exit_session": exit_session,
                "source_known_at_ist": timestamp.strftime(
                    "%d-%b-%Y %H:%M:%S"
                ),
            }
        )
        reason_counts["AE001_EOD_H20_COMMON_EVENT"] += 1

    if timestamp_mismatches != 0:
        raise AlphaContractError(
            "AB001 P002 source-derived H024 timestamps differ from sealed event display"
        )
    if not event_identities:
        raise AlphaContractError("AB001 P002 has zero causal H024 event sessions")

    diagnostics = {
        "sealed_h024_event_count": len(event_panel["events"]),
        "accepted_event_count": len(accepted_events),
        "accepted_distinct_symbol_count": len(
            {row["symbol"] for row in accepted_events}
        ),
        "accepted_decision_session_count": len(event_identities),
        "event_aggregate_timestamp_mismatch_count": timestamp_mismatches,
        "reason_counts": dict(sorted(reason_counts.items())),
        "accepted_events": accepted_events,
    }
    return dict(event_identities), diagnostics


def _reconstruct_ae001_oos(
    *,
    examples: list[ModelExample],
    feature_names: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predictions = []
    lineage = []
    for fold_index, fold in enumerate(FOLDS, start=1):
        train, validation = _fold_train_validation(examples, fold=fold)
        model = fit_ridge(
            train,
            feature_names=feature_names,
            l2=RIDGE_L2,
            model_id=f"AB001-P002-A1-F{fold_index:02d}",
        )
        oos = predict_ridge(
            model,
            validation,
            prediction_role="OOS",
        )
        predictions.extend(oos)
        lineage.append(
            {
                "fold": fold_index,
                "start": fold["start"],
                "end": fold["end"],
                "training_example_count": len(train),
                "validation_example_count": len(validation),
                "training_last_exit_session": model.training_last_exit_session,
                "model_sha256": model.model_sha256,
                "model": asdict(model),
            }
        )
    return predictions, lineage


def _common_prediction_streams(
    *,
    ae001_predictions: list[dict[str, Any]],
    examples: list[ModelExample],
    event_identities: dict[str, set[tuple[str, str]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    example_by_key = {
        (row.feature_session, row.symbol, row.isin): row
        for row in examples
    }
    ae001_by_key = {
        (
            str(row["feature_session"]),
            str(row["symbol"]),
            str(row["isin"]),
        ): row
        for row in ae001_predictions
    }
    if len(ae001_by_key) != len(ae001_predictions):
        raise AlphaContractError("AB001 P002 AE001 OOS predictions are duplicated")

    ae001_common = []
    h024_common = []
    common_sessions = []
    for session in sorted(event_identities):
        session_examples = sorted(
            (
                row
                for row in examples
                if row.feature_session == session
                and row.exit_session <= H024_CUTOFF_SESSION
            ),
            key=lambda row: (row.symbol, row.isin),
        )
        if not session_examples:
            continue
        event_set = event_identities[session]
        matched_events = {
            identity
            for identity in event_set
            if (session, identity[0], identity[1]) in example_by_key
        }
        if not matched_events:
            continue

        for example in session_examples:
            key = (session, example.symbol, example.isin)
            prediction = ae001_by_key.get(key)
            if prediction is None:
                raise AlphaContractError(
                    f"AB001 P002 missing AE001 OOS prediction for {key}"
                )
            ae001_common.append(prediction)
            h024_common.append(
                {
                    "model_id": ALPHA_H024,
                    "symbol": example.symbol,
                    "isin": example.isin,
                    "feature_session": example.feature_session,
                    "entry_session": example.entry_session,
                    "exit_session": example.exit_session,
                    "horizon_sessions": HORIZON,
                    "prediction": (
                        1.0
                        if (example.symbol, example.isin) in matched_events
                        else 0.0
                    ),
                    "target_excess_return": example.target_excess_return,
                    "prediction_role": "OOS",
                    "oos_only": True,
                    "live_capital_allowed": False,
                }
            )
        common_sessions.append(
            {
                "feature_session": session,
                "common_identity_count": len(session_examples),
                "event_identity_count": len(matched_events),
            }
        )

    ae001_keys = [
        (
            row["feature_session"],
            row["symbol"],
            row["isin"],
            row["exit_session"],
        )
        for row in ae001_common
    ]
    h024_keys = [
        (
            row["feature_session"],
            row["symbol"],
            row["isin"],
            row["exit_session"],
        )
        for row in h024_common
    ]
    if ae001_keys != h024_keys:
        raise AlphaContractError("AB001 P002 common alpha rows do not align")
    if len(common_sessions) < 3:
        raise AlphaContractError("AB001 P002 has fewer than three common sessions")
    return ae001_common, h024_common, {
        "common_session_count": len(common_sessions),
        "common_stock_session_count": len(ae001_common),
        "sessions": common_sessions,
    }


def _h024_event_lift(
    h024_predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in h024_predictions:
        by_session[str(row["feature_session"])].append(row)

    sessions = []
    for session in sorted(by_session):
        rows = by_session[session]
        event_targets = [
            float(row["target_excess_return"])
            for row in rows
            if float(row["prediction"]) == 1.0
        ]
        non_event_targets = [
            float(row["target_excess_return"])
            for row in rows
            if float(row["prediction"]) == 0.0
        ]
        if not event_targets or not non_event_targets:
            raise AlphaContractError(
                f"AB001 P002 {session}: event/non-event lift cannot be computed"
            )
        event_mean = statistics.mean(event_targets)
        non_event_mean = statistics.mean(non_event_targets)
        sessions.append(
            {
                "feature_session": session,
                "event_count": len(event_targets),
                "non_event_count": len(non_event_targets),
                "mean_event_excess": event_mean,
                "mean_non_event_excess": non_event_mean,
                "event_minus_non_event_excess": (
                    event_mean - non_event_mean
                ),
            }
        )
    inference = newey_west_mean_inference(
        [
            float(row["event_minus_non_event_excess"])
            for row in sessions
        ],
        max_lag=HORIZON - 1,
    )
    return {
        "schema_version": 1,
        "session_count": len(sessions),
        "event_observation_count": sum(
            int(row["event_count"]) for row in sessions
        ),
        "mean_session_event_excess": statistics.mean(
            float(row["mean_event_excess"]) for row in sessions
        ),
        "mean_session_non_event_excess": statistics.mean(
            float(row["mean_non_event_excess"]) for row in sessions
        ),
        "mean_session_event_lift": statistics.mean(
            float(row["event_minus_non_event_excess"]) for row in sessions
        ),
        "newey_west_event_lift_inference": inference,
        "session_metrics": sessions,
    }


def run_ab001_p002(
    *,
    market_panel: dict[str, Any],
    augmented_feature_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    h024_event_panel: dict[str, Any],
    h024_source_panel: dict[str, Any],
    h024_source_panel_raw_sha256: str,
) -> dict[str, Any]:
    _require_hash(
        market_panel,
        field="panel_sha256",
        expected=EXPECTED_MARKET_SHA,
        name="market panel",
    )
    _require_hash(
        augmented_feature_panel,
        field="panel_sha256",
        expected=EXPECTED_AUGMENTED_FEATURE_SHA,
        name="augmented feature panel",
    )
    _require_hash(
        action_ledger,
        field="ledger_sha256",
        expected=EXPECTED_ACTION_SHA,
        name="corporate-action ledger",
    )
    if augmented_feature_panel.get("base_feature_panel_sha256") != (
        EXPECTED_BASE_FEATURE_SHA
    ):
        raise AlphaContractError(
            "AB001 P002 augmented panel is not bound to frozen base panel"
        )
    if augmented_feature_panel.get("corporate_action_ledger_sha256") != (
        EXPECTED_ACTION_SHA
    ):
        raise AlphaContractError(
            "AB001 P002 augmented panel is not bound to frozen action ledger"
        )
    if h024_source_panel_raw_sha256 != EXPECTED_H024_SOURCE_RAW_SHA:
        raise AlphaContractError(
            "AB001 P002 H024 source-panel raw SHA mismatch"
        )
    _verify_h024_event_panel(h024_event_panel)

    ranked = (
        augmented_feature_panel
        if augmented_feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(augmented_feature_panel)
    )
    feature_names = [
        definition.name
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]
    observed_names = {
        str(row["name"])
        for row in ranked.get("feature_definitions", [])
    }
    if observed_names != set(feature_names):
        raise AlphaContractError(
            "AB001 P002 feature set differs from frozen 27 features"
        )

    examples_by_horizon, example_exclusions = (
        build_action_safe_horizon_examples(
            feature_panel=ranked,
            market_panel=market_panel,
            action_ledger=action_ledger,
            horizons=(HORIZON,),
        )
    )
    examples = project_examples(
        examples_by_horizon[HORIZON],
        feature_names=feature_names,
    )
    market_session_dates = [
        str(row["session_date"])
        for row in market_panel["sessions"]
    ]
    event_identities, event_diagnostics = _causal_h024_events(
        event_panel=h024_event_panel,
        source_panel=h024_source_panel,
        examples=examples,
        market_session_dates=market_session_dates,
    )

    ae001_all, fold_lineage = _reconstruct_ae001_oos(
        examples=examples,
        feature_names=feature_names,
    )
    ae001_common, h024_common, common_diagnostics = (
        _common_prediction_streams(
            ae001_predictions=ae001_all,
            examples=examples,
            event_identities=event_identities,
        )
    )

    source_payloads = {
        ALPHA_AE001: {
            "pilot_id": PILOT_ID,
            "alpha_id": ALPHA_AE001,
            "horizon_sessions": HORIZON,
            "market_panel_sha256": market_panel["panel_sha256"],
            "feature_panel_sha256": augmented_feature_panel["panel_sha256"],
            "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
            "fold_lineage": fold_lineage,
            "prediction_count": len(ae001_common),
            "prediction_records_sha256": digest(ae001_common),
        },
        ALPHA_H024: {
            "pilot_id": PILOT_ID,
            "alpha_id": ALPHA_H024,
            "horizon_sessions": HORIZON,
            "h024_event_panel_sha256": h024_event_panel[
                "event_panel_sha256"
            ],
            "h024_source_panel_raw_sha256": h024_source_panel_raw_sha256,
            "prediction_count": len(h024_common),
            "prediction_records_sha256": digest(h024_common),
            "event_diagnostics_sha256": digest(event_diagnostics),
        },
    }
    sources = [
        {
            "alpha_id": alpha_id,
            "alpha_version": "v1",
            "source_artifact_sha256": digest(payload),
            "predictions": (
                ae001_common if alpha_id == ALPHA_AE001 else h024_common
            ),
        }
        for alpha_id, payload in source_payloads.items()
    ]
    library = build_alpha_library(sources)
    standalone = standalone_alpha_reports(
        library,
        horizon_sessions=HORIZON,
    )
    pairwise = pairwise_alpha_diagnostics(
        library,
        horizon_sessions=HORIZON,
    )
    incremental = incremental_alpha_contribution(
        library,
        existing_alpha_ids=[ALPHA_AE001],
        candidate_alpha_id=ALPHA_H024,
        horizon_sessions=HORIZON,
        newey_west_lag=HORIZON - 1,
    )
    event_lift = _h024_event_lift(h024_common)

    report: dict[str, Any] = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "evidence_class": (
            "HISTORICAL_KNOWN_OUTCOME_CROSSFAMILY_COMBINATION_DIAGNOSTIC"
        ),
        "horizon_sessions": HORIZON,
        "historical_outcome_cutoff_session": H024_CUTOFF_SESSION,
        "input_hashes": {
            "market_panel_sha256": market_panel["panel_sha256"],
            "base_action_safe_feature_panel_sha256": (
                augmented_feature_panel["base_feature_panel_sha256"]
            ),
            "corporate_action_ledger_sha256": action_ledger[
                "ledger_sha256"
            ],
            "augmented_delivery_feature_panel_sha256": (
                augmented_feature_panel["panel_sha256"]
            ),
            "h024_event_panel_sha256": h024_event_panel[
                "event_panel_sha256"
            ],
            "h024_source_panel_raw_sha256": h024_source_panel_raw_sha256,
        },
        "fold_lineage": fold_lineage,
        "example_exclusions": example_exclusions,
        "h024_event_diagnostics": event_diagnostics,
        "common_row_diagnostics": common_diagnostics,
        "source_lineage": source_payloads,
        "library": library,
        "standalone": standalone,
        "pairwise": pairwise,
        "h024_event_lift": event_lift,
        "incremental_h024_candidate": incremental,
        "dynamic_blender_tested": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
