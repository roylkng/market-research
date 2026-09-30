from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ab001_p001 import run_ab001_p001
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes


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


def _compact_prediction_report(report: dict | None) -> dict | None:
    if report is None:
        return None
    return {
        key: value
        for key, value in report.items()
        if key != "session_metrics"
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AB001 P001 T003 OOS alpha-library pilot"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    actions = load_canonical_gzip_json(args.action_ledger.read_bytes())

    report = run_ab001_p001(
        market_panel=market,
        augmented_feature_panel=features,
        action_ledger=actions,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "ab001-p001-report.json.gz").write_bytes(report_bytes)

    dynamic_weights = report["dynamic_blend"]["weights_by_session"]
    weighting_status_counts: dict[str, int] = {}
    alpha_weight_sums: dict[str, float] = {}
    for row in dynamic_weights:
        status = str(row["weighting_status"])
        weighting_status_counts[status] = (
            weighting_status_counts.get(status, 0) + 1
        )
        for alpha, weight in row["weights"].items():
            alpha_weight_sums[alpha] = (
                alpha_weight_sums.get(alpha, 0.0) + float(weight)
            )
    count = len(dynamic_weights)
    mean_weights = {
        alpha: value / count
        for alpha, value in sorted(alpha_weight_sums.items())
    } if count else {}

    summary = {
        "schema_version": 1,
        "pilot_id": report["pilot_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "evidence_class": report["evidence_class"],
        "horizon_sessions": report["horizon_sessions"],
        "sealed_t003_report_sha256": report[
            "sealed_t003_report_sha256"
        ],
        "reconstruction": {
            key: value
            for key, value in report["reconstruction"].items()
            if key not in {"fold_lineage", "source_lineage"}
        },
        "fold_lineage": report["reconstruction"]["fold_lineage"],
        "source_lineage": report["reconstruction"]["source_lineage"],
        "library": {
            "library_sha256": report["library"]["library_sha256"],
            "alpha_count": report["library"]["alpha_count"],
            "record_count": report["library"]["record_count"],
            "alphas": report["library"]["alphas"],
        },
        "standalone": {
            alpha: _compact_prediction_report(alpha_report)
            for alpha, alpha_report in report["standalone"].items()
        },
        "pairwise": report["pairwise"],
        "incremental_augmented_candidate": {
            "existing_alpha_ids": report[
                "incremental_augmented_candidate"
            ]["existing_alpha_ids"],
            "candidate_alpha_id": report[
                "incremental_augmented_candidate"
            ]["candidate_alpha_id"],
            "baseline": _compact_prediction_report(
                report["incremental_augmented_candidate"]["baseline"]
            ),
            "challenger": _compact_prediction_report(
                report["incremental_augmented_candidate"]["challenger"]
            ),
            "challenger_minus_baseline_inference": report[
                "incremental_augmented_candidate"
            ]["challenger_minus_baseline_inference"],
        },
        "dynamic_blend": {
            "artifact_sha256": report["dynamic_blend"]["artifact_sha256"],
            "prediction_count": report["dynamic_blend"]["prediction_count"],
            "mature_oos_report": _compact_prediction_report(
                report["dynamic_blend"]["mature_oos_report"]
            ),
            "weighting_status_counts": weighting_status_counts,
            "mean_alpha_weights": mean_weights,
        },
        "dynamic_vs_augmented": {
            "baseline_alpha_id": report["dynamic_vs_augmented"][
                "baseline_alpha_id"
            ],
            "baseline": _compact_prediction_report(
                report["dynamic_vs_augmented"]["baseline"]
            ),
            "dynamic_blend": _compact_prediction_report(
                report["dynamic_vs_augmented"]["dynamic_blend"]
            ),
            "dynamic_minus_augmented_inference": report[
                "dynamic_vs_augmented"
            ]["dynamic_minus_augmented_inference"],
        },
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
