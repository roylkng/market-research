from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ab001_p003 import run_ab001_p003
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


def _compact(report: dict) -> dict:
    return {
        key: value
        for key, value in report.items()
        if key != "session_metrics"
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AB001 P003 T005 futures-delta diagnostic"
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

    report = run_ab001_p003(
        market_panel=market,
        futures_feature_panel=features,
        action_ledger=actions,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "ab001-p003-report.json.gz").write_bytes(report_bytes)

    incremental = report["incremental_futures_delta_candidate"]
    reference = report["core_plus_delta_vs_full37_reference"]
    summary = {
        "schema_version": 1,
        "pilot_id": report["pilot_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "evidence_class": report["evidence_class"],
        "horizon_sessions": report["horizon_sessions"],
        "input_hashes": report["input_hashes"],
        "t005_reproduction_gate": {
            "core27": _compact(report["t005_reproduction_gate"]["core27"]),
            "full37": _compact(report["t005_reproduction_gate"]["full37"]),
            "expected_t005_report_sha256": report[
                "t005_reproduction_gate"
            ]["expected_t005_report_sha256"],
            "aggregate_absolute_tolerance": report[
                "t005_reproduction_gate"
            ]["aggregate_absolute_tolerance"],
        },
        "library": {
            "alpha_count": report["library"]["alpha_count"],
            "record_count": report["library"]["record_count"],
            "alphas": report["library"]["alphas"],
            "library_sha256": report["library"]["library_sha256"],
        },
        "standalone": {
            alpha_id: _compact(value)
            for alpha_id, value in report["standalone"].items()
        },
        "pairwise": report["pairwise"],
        "primary_core_delta_orthogonality": report[
            "primary_core_delta_orthogonality"
        ],
        "incremental_futures_delta_candidate": {
            "existing_alpha_ids": incremental["existing_alpha_ids"],
            "candidate_alpha_id": incremental["candidate_alpha_id"],
            "horizon_sessions": incremental["horizon_sessions"],
            "baseline": _compact(incremental["baseline"]),
            "challenger": _compact(incremental["challenger"]),
            "challenger_minus_baseline_inference": incremental[
                "challenger_minus_baseline_inference"
            ],
        },
        "core_plus_delta_vs_full37_reference": {
            "equal_weight_core_plus_delta": _compact(
                reference["equal_weight_core_plus_delta"]
            ),
            "full37_reference": _compact(
                reference["full37_reference"]
            ),
            "blend_minus_full37_inference": reference[
                "blend_minus_full37_inference"
            ],
        },
        "dynamic_blender_tested": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
