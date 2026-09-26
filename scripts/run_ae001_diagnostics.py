from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_diagnostics import (
    leave_one_feature_out_ridge_walkforward,
    report_time_series_inference,
    signed_single_feature_walkforward,
    summarize_ablation_delta,
)
from marketlab.alpha_history import (
    canonical_gzip_json,
    cross_sectionalize_panel,
    load_canonical_gzip_json,
)
from marketlab.alpha_walkforward import (
    build_one_session_examples,
    run_ridge_walkforward,
)
from marketlab.events import sha256_bytes


def _fold(value: str) -> dict[str, str]:
    parts = value.split(":", maxsplit=1)
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError("fold must be START:END")
    return {"start": parts[0], "end": parts[1]}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AE001 action-safe 1D baseline and ablation diagnostics"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fold", type=_fold, action="append", required=True)
    parser.add_argument("--l2", type=float, default=1.0)
    parser.add_argument("--newey-west-lag", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())

    ridge = run_ridge_walkforward(
        feature_panel=features,
        market_panel=market,
        folds=args.fold,
        l2=args.l2,
    )
    ranked = cross_sectionalize_panel(features)
    examples, exclusions = build_one_session_examples(
        feature_panel=ranked,
        market_panel=market,
    )
    feature_names = [str(row["name"]) for row in ranked["feature_definitions"]]

    singles = signed_single_feature_walkforward(
        examples,
        folds=args.fold,
        feature_names=feature_names,
    )
    ablations = leave_one_feature_out_ridge_walkforward(
        examples,
        folds=args.fold,
        feature_names=feature_names,
        l2=args.l2,
    )
    inference = {
        "ridge": report_time_series_inference(
            ridge["ridge"],
            max_lag=args.newey_west_lag,
        ),
        "best_single_feature_train_selected": report_time_series_inference(
            singles["best_single_feature_train_selected_oos"],
            max_lag=args.newey_west_lag,
        ),
    }

    report = {
        "schema_version": 1,
        "diagnostic_id": "AE001-DIAGNOSTICS-1D-ACTION-SAFE-v1",
        "engine_id": "AE001-v1-DEVELOPMENT",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "market_panel_sha256": market["panel_sha256"],
        "feature_panel_sha256": features["panel_sha256"],
        "ridge_walkforward_sha256": ridge["report_sha256"],
        "folds": args.fold,
        "l2": args.l2,
        "example_exclusions": exclusions,
        "ridge": ridge,
        "signed_single_features": singles,
        "leave_one_feature_out": ablations,
        "ablation_delta": summarize_ablation_delta(
            ridge["ridge"],
            ablations,
        ),
        "time_series_inference": inference,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "diagnostics-report.json.gz").write_bytes(report_bytes)

    per_feature = []
    for feature, feature_report in singles["per_feature_oos"].items():
        per_feature.append(
            {
                "feature": feature,
                "mean_rank_ic": feature_report["mean_rank_ic"],
                "mean_top_decile_excess": feature_report[
                    "mean_top_decile_excess"
                ],
                "mean_top_minus_bottom_spread": feature_report[
                    "mean_top_minus_bottom_spread"
                ],
            }
        )
    per_feature.sort(
        key=lambda row: (
            -float(row["mean_rank_ic"] or -999.0),
            row["feature"],
        )
    )
    summary = {
        "schema_version": 1,
        "diagnostic_id": report["diagnostic_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "market_panel_sha256": market["panel_sha256"],
        "feature_panel_sha256": features["panel_sha256"],
        "ridge": {
            key: value
            for key, value in ridge["ridge"].items()
            if key != "session_metrics"
        },
        "best_single_feature_train_selected": {
            key: value
            for key, value in singles[
                "best_single_feature_train_selected_oos"
            ].items()
            if key != "session_metrics"
        },
        "per_feature_oos": per_feature,
        "ablation_delta": report["ablation_delta"],
        "time_series_inference": inference,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
