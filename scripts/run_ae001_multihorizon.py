from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_multihorizon import run_action_safe_horizon_walkforward
from marketlab.events import sha256_bytes


def _fold(value: str) -> tuple[int, dict[str, str]]:
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "horizon fold must be HORIZON:START:END"
        )
    try:
        horizon = int(parts[0])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("horizon must be integer") from exc
    if not parts[1] or not parts[2]:
        raise argparse.ArgumentTypeError("fold dates are required")
    return horizon, {"start": parts[1], "end": parts[2]}


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
        description="Run AE001 action-safe 5/20/60-session walk-forward"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fold", type=_fold, action="append", required=True)
    parser.add_argument("--l2", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    actions = load_canonical_gzip_json(args.action_ledger.read_bytes())

    folds: dict[int, list[dict[str, str]]] = defaultdict(list)
    for horizon, fold in args.fold:
        folds[horizon].append(fold)

    report = run_action_safe_horizon_walkforward(
        feature_panel=features,
        market_panel=market,
        action_ledger=actions,
        folds_by_horizon=dict(folds),
        l2=args.l2,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "multihorizon-report.json.gz").write_bytes(report_bytes)

    horizons = {}
    for key, value in report["horizons"].items():
        horizons[key] = {
            "horizon_sessions": value["horizon_sessions"],
            "example_count": value["example_count"],
            "ridge": {
                metric: metric_value
                for metric, metric_value in value["ridge"].items()
                if metric != "session_metrics"
            },
            "ridge_time_series_inference": value[
                "ridge_time_series_inference"
            ],
            "best_single_feature_train_selected": {
                metric: metric_value
                for metric, metric_value in value[
                    "best_single_feature_train_selected"
                ].items()
                if metric != "session_metrics"
            },
            "best_single_feature_time_series_inference": value[
                "best_single_feature_time_series_inference"
            ],
            "selected_single_features_by_fold": [
                {
                    "fold": fold["fold"],
                    "selected_feature": fold["selected_feature"],
                    "selected_direction": fold["selected_direction"],
                    "selected_training_signed_rank_ic": fold[
                        "selected_training_signed_rank_ic"
                    ],
                }
                for fold in value["signed_single_feature_folds"]
            ],
        }

    summary = {
        "schema_version": 1,
        "walkforward_id": report["walkforward_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "feature_panel_sha256": report["feature_panel_sha256"],
        "market_panel_sha256": report["market_panel_sha256"],
        "corporate_action_ledger_sha256": report[
            "corporate_action_ledger_sha256"
        ],
        "horizons": horizons,
        "exclusions": report["exclusions"],
        "cost_model_status": report["cost_model_status"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
