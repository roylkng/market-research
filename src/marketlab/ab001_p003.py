from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from marketlab.ab001 import (
    build_alpha_library,
    incremental_alpha_contribution,
    pairwise_alpha_diagnostics,
    standalone_alpha_reports,
)
from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_model import (
    ModelExample,
    evaluate_cross_sectional_predictions,
    fit_ridge,
    predict_ridge,
    project_examples,
    purge_training_examples,
)
from marketlab.alpha_multihorizon import build_action_safe_horizon_examples
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS

PILOT_ID = "AB001-P003-v1"
HORIZON = 5
RIDGE_L2 = 1.0
ALPHA_CORE = "AB001-P003-CORE27"
ALPHA_DELTA = "AB001-P003-FUTURES-DELTA"
ALPHA_FULL = "AB001-P003-FULL37"

FOLDS = (
    {"start": "2026-04-01", "end": "2026-06-30"},
    {"start": "2026-07-01", "end": "2026-09-18"},
)

EXPECTED_MARKET_SHA = (
    "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
)
EXPECTED_BASE_ACTION_SAFE_SHA = (
    "300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8"
)
EXPECTED_ACTION_SHA = (
    "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
)
EXPECTED_DELIVERY_SHA = (
    "99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90"
)
EXPECTED_FUTURES_SHA = (
    "02656c828a1d5fe22660c154a445ebd69a7492b56f1807da0d8c959a6f0c11d5"
)
EXPECTED_FUTURES_FEATURE_SHA = (
    "62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f"
)
EXPECTED_T005_REPORT_SHA = (
    "2c72c9207ad3cfe2bc73637e4c10b7ad378c9a6c1b347fa2dd8936831a7511e2"
)
REPRO_TOL = 1e-15
ADDITIVITY_TOL = 1e-15

EXPECTED_T005 = {
    "prediction_count": 23084,
    "session_count": 112,
    "base_mean_rank_ic": -0.0006030060148556494,
    "augmented_mean_rank_ic": 0.021664130700606535,
    "base_mean_top_minus_bottom_spread": 0.00008999948207925853,
    "augmented_mean_top_minus_bottom_spread": 0.003935681355715129,
}


def _feature_names() -> tuple[list[str], list[str]]:
    base = [
        *[definition.name for definition in PRICE_VOLUME_DEFINITIONS],
        *[definition.name for definition in DELIVERY_DEFINITIONS],
    ]
    futures = [definition.name for definition in FUTURES_DEFINITIONS]
    return base, [*base, *futures]


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
            f"AB001 P003 {name} does not reproduce frozen input: "
            f"{observed} != {expected}"
        )


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
            f"AB001 P003 fold {start}: insufficient purged training data"
        )
    if not validation:
        raise AlphaContractError(
            f"AB001 P003 fold {start}: validation is empty"
        )
    return train, validation


def _prediction_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row["feature_session"]),
        str(row["symbol"]),
        str(row["isin"]),
        str(row["entry_session"]),
        str(row["exit_session"]),
    )


def _reconstruct_oos_pair(
    *,
    examples: list[ModelExample],
    base_names: list[str],
    full_names: list[str],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    core_predictions: list[dict[str, Any]] = []
    full_predictions: list[dict[str, Any]] = []
    lineage = []

    base_examples = project_examples(examples, feature_names=base_names)
    full_examples = project_examples(examples, feature_names=full_names)

    for fold_index, fold in enumerate(FOLDS, start=1):
        base_train, base_validation = _fold_train_validation(
            base_examples,
            fold=fold,
        )
        full_train, full_validation = _fold_train_validation(
            full_examples,
            fold=fold,
        )
        base_keys = [
            (
                row.feature_session,
                row.symbol,
                row.isin,
                row.entry_session,
                row.exit_session,
            )
            for row in base_validation
        ]
        full_keys = [
            (
                row.feature_session,
                row.symbol,
                row.isin,
                row.entry_session,
                row.exit_session,
            )
            for row in full_validation
        ]
        if base_keys != full_keys:
            raise AlphaContractError(
                f"AB001 P003 fold {fold_index}: base/full validation rows differ"
            )
        if len(base_train) != len(full_train):
            raise AlphaContractError(
                f"AB001 P003 fold {fold_index}: base/full training rows differ"
            )

        base_model = fit_ridge(
            base_train,
            feature_names=base_names,
            l2=RIDGE_L2,
            model_id=f"AB001-P003-CORE27-F{fold_index:02d}",
        )
        full_model = fit_ridge(
            full_train,
            feature_names=full_names,
            l2=RIDGE_L2,
            model_id=f"AB001-P003-FULL37-F{fold_index:02d}",
        )
        base_oos = predict_ridge(
            base_model,
            base_validation,
            prediction_role="OOS",
        )
        full_oos = predict_ridge(
            full_model,
            full_validation,
            prediction_role="OOS",
        )
        core_predictions.extend(base_oos)
        full_predictions.extend(full_oos)
        lineage.append(
            {
                "fold": fold_index,
                "start": fold["start"],
                "end": fold["end"],
                "training_example_count": len(base_train),
                "validation_example_count": len(base_validation),
                "training_last_exit_session": base_model.training_last_exit_session,
                "core_model_sha256": base_model.model_sha256,
                "full_model_sha256": full_model.model_sha256,
            }
        )

    core_map = {_prediction_key(row): row for row in core_predictions}
    full_map = {_prediction_key(row): row for row in full_predictions}
    if len(core_map) != len(core_predictions) or len(full_map) != len(full_predictions):
        raise AlphaContractError("AB001 P003 duplicate reconstructed OOS row")
    if core_map.keys() != full_map.keys():
        raise AlphaContractError("AB001 P003 reconstructed OOS identity sets differ")

    delta_predictions = []
    max_additivity_error = 0.0
    for key in sorted(core_map):
        core = core_map[key]
        full = full_map[key]
        core_target = float(core["target_excess_return"])
        full_target = float(full["target_excess_return"])
        if core_target != full_target:
            raise AlphaContractError("AB001 P003 paired OOS targets differ")
        core_prediction = float(core["prediction"])
        full_prediction = float(full["prediction"])
        delta = full_prediction - core_prediction
        reconstructed = core_prediction + delta
        error = abs(reconstructed - full_prediction)
        max_additivity_error = max(max_additivity_error, error)
        if error > ADDITIVITY_TOL:
            raise AlphaContractError("AB001 P003 raw forecast additivity failed")

        delta_predictions.append(
            {
                "model_id": ALPHA_DELTA,
                "symbol": core["symbol"],
                "isin": core["isin"],
                "feature_session": core["feature_session"],
                "entry_session": core["entry_session"],
                "exit_session": core["exit_session"],
                "horizon_sessions": HORIZON,
                "prediction": delta,
                "target_excess_return": core_target,
                "prediction_role": "OOS",
                "oos_only": True,
                "live_capital_allowed": False,
            }
        )

    if max_additivity_error > ADDITIVITY_TOL:
        raise AlphaContractError("AB001 P003 additivity audit exceeds tolerance")

    return core_predictions, delta_predictions, full_predictions, lineage


def _assert_close(
    observed: float,
    expected: float,
    *,
    label: str,
) -> None:
    if not math.isclose(
        float(observed),
        float(expected),
        rel_tol=0.0,
        abs_tol=REPRO_TOL,
    ):
        raise AlphaContractError(
            f"AB001 P003 T005 reproduction mismatch for {label}: "
            f"{observed} != {expected}"
        )


def _reproduction_gate(
    core_predictions: list[dict[str, Any]],
    full_predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    core = evaluate_cross_sectional_predictions(core_predictions)
    full = evaluate_cross_sectional_predictions(full_predictions)
    if int(core["prediction_count"]) != EXPECTED_T005["prediction_count"]:
        raise AlphaContractError("AB001 P003 T005 base prediction count mismatch")
    if int(full["prediction_count"]) != EXPECTED_T005["prediction_count"]:
        raise AlphaContractError("AB001 P003 T005 full prediction count mismatch")
    if int(core["session_count"]) != EXPECTED_T005["session_count"]:
        raise AlphaContractError("AB001 P003 T005 base session count mismatch")
    if int(full["session_count"]) != EXPECTED_T005["session_count"]:
        raise AlphaContractError("AB001 P003 T005 full session count mismatch")

    _assert_close(
        core["mean_rank_ic"],
        EXPECTED_T005["base_mean_rank_ic"],
        label="base mean rank IC",
    )
    _assert_close(
        full["mean_rank_ic"],
        EXPECTED_T005["augmented_mean_rank_ic"],
        label="full mean rank IC",
    )
    _assert_close(
        core["mean_top_minus_bottom_spread"],
        EXPECTED_T005["base_mean_top_minus_bottom_spread"],
        label="base spread",
    )
    _assert_close(
        full["mean_top_minus_bottom_spread"],
        EXPECTED_T005["augmented_mean_top_minus_bottom_spread"],
        label="full spread",
    )
    return {
        "core27": core,
        "full37": full,
        "expected_t005_report_sha256": EXPECTED_T005_REPORT_SHA,
        "aggregate_absolute_tolerance": REPRO_TOL,
    }


def _common_normalized_maps(
    library: dict[str, Any],
    alpha_ids: list[str],
) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    by_alpha: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = {
        alpha: {} for alpha in alpha_ids
    }
    for row in library["records"]:
        alpha = str(row["alpha_id"])
        if alpha not in by_alpha:
            continue
        key = (
            str(row["feature_session"]),
            str(row["symbol"]),
            str(row["isin"]),
        )
        by_alpha[alpha][key] = row
    key_sets = [set(rows) for rows in by_alpha.values()]
    common = set.intersection(*key_sets) if key_sets else set()
    if not common:
        raise AlphaContractError("AB001 P003 normalized common rows are empty")
    return {
        alpha: {key: rows[key] for key in sorted(common)}
        for alpha, rows in by_alpha.items()
    }


def _blend_vs_full_reference(
    library: dict[str, Any],
) -> dict[str, Any]:
    maps = _common_normalized_maps(
        library,
        [ALPHA_CORE, ALPHA_DELTA, ALPHA_FULL],
    )
    blend_predictions = []
    full_predictions = []
    for key in sorted(maps[ALPHA_CORE]):
        core = maps[ALPHA_CORE][key]
        delta = maps[ALPHA_DELTA][key]
        full = maps[ALPHA_FULL][key]
        targets = {
            float(core["target_excess_return"]),
            float(delta["target_excess_return"]),
            float(full["target_excess_return"]),
        }
        if len(targets) != 1:
            raise AlphaContractError("AB001 P003 normalized common targets differ")
        target = targets.pop()
        blend_predictions.append(
            {
                "symbol": key[1],
                "isin": key[2],
                "feature_session": key[0],
                "prediction": (
                    float(core["normalized_score"])
                    + float(delta["normalized_score"])
                )
                / 2.0,
                "target_excess_return": target,
            }
        )
        full_predictions.append(
            {
                "symbol": key[1],
                "isin": key[2],
                "feature_session": key[0],
                "prediction": float(full["normalized_score"]),
                "target_excess_return": target,
            }
        )
    blend_report = evaluate_cross_sectional_predictions(blend_predictions)
    full_report = evaluate_cross_sectional_predictions(full_predictions)
    return {
        "equal_weight_core_plus_delta": blend_report,
        "full37_reference": full_report,
        "blend_minus_full37_inference": paired_report_difference_inference(
            blend_report,
            full_report,
            max_lag=HORIZON - 1,
        ),
    }


def run_ab001_p003(
    *,
    market_panel: dict[str, Any],
    futures_feature_panel: dict[str, Any],
    action_ledger: dict[str, Any],
) -> dict[str, Any]:
    _require_hash(
        market_panel,
        field="panel_sha256",
        expected=EXPECTED_MARKET_SHA,
        name="market panel",
    )
    _require_hash(
        futures_feature_panel,
        field="panel_sha256",
        expected=EXPECTED_FUTURES_FEATURE_SHA,
        name="futures feature panel",
    )
    _require_hash(
        action_ledger,
        field="ledger_sha256",
        expected=EXPECTED_ACTION_SHA,
        name="corporate-action ledger",
    )
    if futures_feature_panel.get("base_feature_panel_sha256") != EXPECTED_DELIVERY_SHA:
        raise AlphaContractError(
            "AB001 P003 futures panel is not based on frozen delivery panel"
        )
    if futures_feature_panel.get("futures_panel_sha256") != EXPECTED_FUTURES_SHA:
        raise AlphaContractError("AB001 P003 futures source panel mismatch")
    if futures_feature_panel.get("corporate_action_ledger_sha256") != EXPECTED_ACTION_SHA:
        raise AlphaContractError("AB001 P003 futures/action binding mismatch")
    base_action = futures_feature_panel.get("base_action_safe_feature_panel_sha256")
    if base_action not in (None, EXPECTED_BASE_ACTION_SAFE_SHA):
        raise AlphaContractError("AB001 P003 action-safe lineage mismatch")

    ranked = (
        futures_feature_panel
        if futures_feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(futures_feature_panel)
    )
    base_names, full_names = _feature_names()
    observed_names = {
        str(row["name"]) for row in ranked.get("feature_definitions", [])
    }
    if observed_names != set(full_names):
        raise AlphaContractError("AB001 P003 feature set differs from frozen T005")

    examples_by_horizon, exclusions = build_action_safe_horizon_examples(
        feature_panel=ranked,
        market_panel=market_panel,
        action_ledger=action_ledger,
        horizons=(HORIZON,),
    )
    examples = examples_by_horizon[HORIZON]
    core, delta, full, lineage = _reconstruct_oos_pair(
        examples=examples,
        base_names=base_names,
        full_names=full_names,
    )
    reproduction = _reproduction_gate(core, full)

    source_lineage = {
        ALPHA_CORE: {
            "construction": "T005_CORE27_OOS_RIDGE",
            "prediction_count": len(core),
            "prediction_records_sha256": digest(core),
            "fold_lineage": lineage,
        },
        ALPHA_DELTA: {
            "construction": "T005_FULL37_MINUS_CORE27_RAW_OOS_FORECAST",
            "prediction_count": len(delta),
            "prediction_records_sha256": digest(delta),
            "additivity_tolerance": ADDITIVITY_TOL,
        },
        ALPHA_FULL: {
            "construction": "T005_FULL37_OOS_RIDGE_REFERENCE",
            "prediction_count": len(full),
            "prediction_records_sha256": digest(full),
            "fold_lineage": lineage,
        },
    }

    prediction_streams = {
        ALPHA_CORE: core,
        ALPHA_DELTA: delta,
        ALPHA_FULL: full,
    }
    library = build_alpha_library(
        [
            {
                "alpha_id": alpha_id,
                "alpha_version": "v1",
                "source_artifact_sha256": digest(source_lineage[alpha_id]),
                "predictions": prediction_streams[alpha_id],
            }
            for alpha_id in (ALPHA_CORE, ALPHA_DELTA, ALPHA_FULL)
        ]
    )
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
        existing_alpha_ids=[ALPHA_CORE],
        candidate_alpha_id=ALPHA_DELTA,
        horizon_sessions=HORIZON,
        newey_west_lag=HORIZON - 1,
    )
    reference = _blend_vs_full_reference(library)

    core_delta_pair = next(
        row
        for row in pairwise
        if {
            row["left_alpha_id"],
            row["right_alpha_id"],
        }
        == {ALPHA_CORE, ALPHA_DELTA}
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "evidence_class": (
            "HISTORICAL_KNOWN_OUTCOME_COMBINATION_DIAGNOSTIC"
        ),
        "horizon_sessions": HORIZON,
        "input_hashes": {
            "market_panel_sha256": market_panel["panel_sha256"],
            "action_safe_base_feature_panel_sha256": EXPECTED_BASE_ACTION_SAFE_SHA,
            "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
            "delivery_augmented_feature_panel_sha256": EXPECTED_DELIVERY_SHA,
            "futures_panel_sha256": futures_feature_panel["futures_panel_sha256"],
            "futures_augmented_feature_panel_sha256": futures_feature_panel[
                "panel_sha256"
            ],
            "sealed_t005_report_sha256": EXPECTED_T005_REPORT_SHA,
        },
        "fold_lineage": lineage,
        "example_exclusions": exclusions,
        "t005_reproduction_gate": reproduction,
        "source_lineage": source_lineage,
        "library": library,
        "standalone": standalone,
        "pairwise": pairwise,
        "primary_core_delta_orthogonality": core_delta_pair,
        "incremental_futures_delta_candidate": incremental,
        "core_plus_delta_vs_full37_reference": reference,
        "dynamic_blender_tested": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
