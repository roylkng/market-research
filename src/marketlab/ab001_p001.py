from __future__ import annotations

from dataclasses import asdict
from typing import Any

from marketlab.ab001 import (
    build_alpha_library,
    dynamic_blend,
    incremental_alpha_contribution,
    pairwise_alpha_diagnostics,
    standalone_alpha_reports,
)
from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import (
    feature_predictions,
    learn_feature_direction,
    paired_report_difference_inference,
)
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_model import (
    evaluate_cross_sectional_predictions,
    fit_ridge,
    predict_ridge,
    project_examples,
    purge_training_examples,
)
from marketlab.alpha_multihorizon import build_action_safe_horizon_examples
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS

PILOT_ID = "AB001-P001-v1"
HORIZON = 5
RIDGE_L2 = 1.0
FOLDS = (
    {"start": "2026-04-01", "end": "2026-06-30"},
    {"start": "2026-07-01", "end": "2026-09-18"},
)
ALPHA_AUGMENTED = "AB001-P001-A1"
ALPHA_BASE = "AB001-P001-A2"
ALPHA_SINGLE = "AB001-P001-A3"

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
SEALED_T003_REPORT_SHA = (
    "0b9cb3003b76548f35bb66ff24c3090f0e9b236a0219a6d35bcdd92a70732270"
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
            f"AB001 P001 {name} does not reproduce frozen input: "
            f"{observed} != {expected}"
        )


def _fold_train_validation(
    examples,
    *,
    fold: dict[str, str],
):
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
            f"AB001 P001 fold {start}: insufficient purged training data"
        )
    if not validation:
        raise AlphaContractError(
            f"AB001 P001 fold {start}: validation is empty"
        )
    return train, validation


def _reconstruct_sources(
    *,
    market_panel: dict[str, Any],
    augmented_feature_panel: dict[str, Any],
    action_ledger: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
            "AB001 P001 augmented panel is not bound to frozen base feature panel"
        )
    if augmented_feature_panel.get("corporate_action_ledger_sha256") != (
        EXPECTED_ACTION_SHA
    ):
        raise AlphaContractError(
            "AB001 P001 augmented panel is not bound to frozen action ledger"
        )

    ranked = (
        augmented_feature_panel
        if augmented_feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(augmented_feature_panel)
    )

    base_names = [definition.name for definition in PRICE_VOLUME_DEFINITIONS]
    delivery_names = [definition.name for definition in DELIVERY_DEFINITIONS]
    augmented_names = [*base_names, *delivery_names]
    definitions = ranked.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("AB001 P001 feature definitions are missing")
    observed_names = {str(row["name"]) for row in definitions}
    if observed_names != set(augmented_names):
        raise AlphaContractError(
            "AB001 P001 feature set differs from frozen T003 27 features"
        )

    examples_by_horizon, exclusions = build_action_safe_horizon_examples(
        feature_panel=ranked,
        market_panel=market_panel,
        action_ledger=action_ledger,
        horizons=(HORIZON,),
    )
    examples_augmented = project_examples(
        examples_by_horizon[HORIZON],
        feature_names=augmented_names,
    )
    examples_base = project_examples(
        examples_by_horizon[HORIZON],
        feature_names=base_names,
    )

    augmented_predictions = []
    base_predictions = []
    single_predictions = []
    fold_lineage = []

    for fold_index, fold in enumerate(FOLDS, start=1):
        aug_train, aug_validation = _fold_train_validation(
            examples_augmented,
            fold=fold,
        )
        base_train, base_validation = _fold_train_validation(
            examples_base,
            fold=fold,
        )
        if [
            (row.feature_session, row.symbol, row.isin)
            for row in aug_validation
        ] != [
            (row.feature_session, row.symbol, row.isin)
            for row in base_validation
        ]:
            raise AlphaContractError(
                f"AB001 P001 fold {fold_index}: base/augmented validation rows differ"
            )

        augmented_model = fit_ridge(
            aug_train,
            feature_names=augmented_names,
            l2=RIDGE_L2,
            model_id=f"AB001-P001-A1-F{fold_index:02d}",
        )
        base_model = fit_ridge(
            base_train,
            feature_names=base_names,
            l2=RIDGE_L2,
            model_id=f"AB001-P001-A2-F{fold_index:02d}",
        )
        aug_oos = predict_ridge(
            augmented_model,
            aug_validation,
            prediction_role="OOS",
        )
        base_oos = predict_ridge(
            base_model,
            base_validation,
            prediction_role="OOS",
        )
        augmented_predictions.extend(aug_oos)
        base_predictions.extend(base_oos)

        learned = []
        for feature in augmented_names:
            direction, train_report = learn_feature_direction(
                aug_train,
                feature_name=feature,
            )
            learned.append(
                {
                    "feature": feature,
                    "direction": direction,
                    "training_mean_rank_ic_raw_direction": float(
                        train_report["mean_rank_ic"]
                    ),
                    "training_signed_rank_ic": abs(
                        float(train_report["mean_rank_ic"])
                    ),
                }
            )
        learned.sort(
            key=lambda row: (
                -float(row["training_signed_rank_ic"]),
                str(row["feature"]),
            )
        )
        selected = learned[0]
        single_oos = feature_predictions(
            aug_validation,
            feature_name=str(selected["feature"]),
            direction=int(selected["direction"]),
            model_id=f"AB001-P001-A3-F{fold_index:02d}",
            prediction_role="OOS",
        )
        single_predictions.extend(single_oos)

        fold_lineage.append(
            {
                "fold": fold_index,
                "start": fold["start"],
                "end": fold["end"],
                "training_example_count": len(aug_train),
                "validation_example_count": len(aug_validation),
                "augmented_model_sha256": augmented_model.model_sha256,
                "base_model_sha256": base_model.model_sha256,
                "selected_single_feature": selected["feature"],
                "selected_single_direction": selected["direction"],
                "selected_single_training_signed_rank_ic": selected[
                    "training_signed_rank_ic"
                ],
                "augmented_model": asdict(augmented_model),
                "base_model": asdict(base_model),
            }
        )

    streams = {
        ALPHA_AUGMENTED: augmented_predictions,
        ALPHA_BASE: base_predictions,
        ALPHA_SINGLE: single_predictions,
    }
    sources = []
    source_lineage = {}
    for alpha_id, predictions in streams.items():
        source_payload = {
            "pilot_id": PILOT_ID,
            "alpha_id": alpha_id,
            "horizon_sessions": HORIZON,
            "market_panel_sha256": market_panel["panel_sha256"],
            "feature_panel_sha256": augmented_feature_panel["panel_sha256"],
            "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
            "sealed_t003_report_sha256": SEALED_T003_REPORT_SHA,
            "fold_lineage": fold_lineage,
            "prediction_count": len(predictions),
            "prediction_records_sha256": digest(predictions),
        }
        source_sha = digest(source_payload)
        sources.append(
            {
                "alpha_id": alpha_id,
                "alpha_version": "v1",
                "source_artifact_sha256": source_sha,
                "predictions": predictions,
            }
        )
        source_lineage[alpha_id] = {
            **source_payload,
            "source_artifact_sha256": source_sha,
        }

    reconstruction = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "horizon_sessions": HORIZON,
        "folds": list(FOLDS),
        "ridge_l2": RIDGE_L2,
        "base_feature_names": base_names,
        "delivery_feature_names": delivery_names,
        "augmented_feature_names": augmented_names,
        "example_count": len(examples_augmented),
        "example_exclusions": exclusions,
        "fold_lineage": fold_lineage,
        "source_lineage": source_lineage,
        "ranked_feature_panel_sha256": ranked["panel_sha256"],
        "live_capital_allowed": False,
    }
    reconstruction["reconstruction_sha256"] = digest(reconstruction)
    return sources, reconstruction


def _dynamic_vs_augmented(
    *,
    library: dict[str, Any],
    dynamic: dict[str, Any],
) -> dict[str, Any]:
    blend_rows = [
        row
        for row in dynamic["predictions"]
        if row.get("target_excess_return") is not None
    ]
    blend_keys = {
        (
            str(row["feature_session"]),
            str(row["symbol"]),
            str(row["isin"]),
        )
        for row in blend_rows
    }
    augmented_rows = [
        row
        for row in library["records"]
        if (
            row["alpha_id"] == ALPHA_AUGMENTED
            and int(row["horizon_sessions"]) == HORIZON
            and row["outcome_status"] == "COMPLETE"
            and (
                str(row["feature_session"]),
                str(row["symbol"]),
                str(row["isin"]),
            )
            in blend_keys
        )
    ]
    if len(augmented_rows) != len(blend_rows):
        raise AlphaContractError(
            "AB001 P001 dynamic/augmented comparison rows do not align"
        )
    augmented_report = evaluate_cross_sectional_predictions(
        [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "feature_session": row["feature_session"],
                "prediction": row["normalized_score"],
                "target_excess_return": row["target_excess_return"],
            }
            for row in augmented_rows
        ]
    )
    blend_report = evaluate_cross_sectional_predictions(blend_rows)
    inference = paired_report_difference_inference(
        blend_report,
        augmented_report,
        max_lag=HORIZON - 1,
    )
    return {
        "baseline_alpha_id": ALPHA_AUGMENTED,
        "baseline": augmented_report,
        "dynamic_blend": blend_report,
        "dynamic_minus_augmented_inference": inference,
    }


def run_ab001_p001(
    *,
    market_panel: dict[str, Any],
    augmented_feature_panel: dict[str, Any],
    action_ledger: dict[str, Any],
) -> dict[str, Any]:
    sources, reconstruction = _reconstruct_sources(
        market_panel=market_panel,
        augmented_feature_panel=augmented_feature_panel,
        action_ledger=action_ledger,
    )
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
        existing_alpha_ids=[ALPHA_BASE, ALPHA_SINGLE],
        candidate_alpha_id=ALPHA_AUGMENTED,
        horizon_sessions=HORIZON,
        newey_west_lag=HORIZON - 1,
    )
    dynamic = dynamic_blend(
        library,
        alpha_ids=[ALPHA_AUGMENTED, ALPHA_BASE, ALPHA_SINGLE],
        horizon_sessions=HORIZON,
        lookback_sessions=60,
    )
    dynamic_comparison = _dynamic_vs_augmented(
        library=library,
        dynamic=dynamic,
    )

    result: dict[str, Any] = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_OOS_COMBINATION_DIAGNOSTIC",
        "horizon_sessions": HORIZON,
        "sealed_t003_report_sha256": SEALED_T003_REPORT_SHA,
        "reconstruction": reconstruction,
        "library": library,
        "standalone": standalone,
        "pairwise": pairwise,
        "incremental_augmented_candidate": incremental,
        "dynamic_blend": dynamic,
        "dynamic_vs_augmented": dynamic_comparison,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result
