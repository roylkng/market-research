from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.po001_s001 import run_po001_s001_replica


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


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


def _compact(artifact: dict) -> dict:
    active = [
        row
        for row in artifact["rows"]
        if float(row["target_weight"]) > 1e-12
    ]
    return {
        "artifact_sha256": artifact["artifact_sha256"],
        "holding_count_gt_1e12": len(active),
        "invested_weight": artifact["invested_weight"],
        "expected_5d_excess_return": artifact["expected_excess_return"],
        "annualized_volatility": (
            float(artifact["total_variance_daily"]) * 252.0
        ) ** 0.5,
        "total_variance_daily": artifact["total_variance_daily"],
        "risk_penalty": artifact["risk_penalty"],
        "total_transaction_cost_fraction": artifact[
            "total_transaction_cost_fraction"
        ],
        "objective_utility": artifact["objective_utility"],
        "maximum_observed_participation": artifact[
            "maximum_observed_participation"
        ],
        "maximum_coordinate_kkt_violation": artifact["solver"]["kkt"][
            "maximum_coordinate_kkt_violation"
        ],
        "budget_slack": artifact["solver"]["kkt"]["budget_slack"],
        "budget_dual": artifact["solver"]["budget_dual"],
        "total_coordinate_sweeps": artifact["solver"][
            "total_coordinate_sweeps"
        ],
        "outer_bisection_iterations": artifact["solver"][
            "outer_bisection_iterations"
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one frozen PO001 S001 numerical-stability replica"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--alpha-model", type=Path, required=True)
    parser.add_argument("--control-risk", type=Path, required=True)
    parser.add_argument("--treatment-risk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    alpha_model = _load_json(args.alpha_model)
    control_risk = load_canonical_gzip_json(args.control_risk.read_bytes())
    treatment_risk = load_canonical_gzip_json(
        args.treatment_risk.read_bytes()
    )

    report = run_po001_s001_replica(
        delivery_feature_panel=features,
        market_panel=market,
        pinned_alpha_model=alpha_model,
        control_risk_state=control_risk,
        treatment_risk_state=treatment_risk,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "replica-report.json.gz").write_bytes(report_bytes)

    summary = {
        "schema_version": 1,
        "study_id": report["study_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "common_identity_count": report["common_identity_count"],
        "control": _compact(
            report["control_rm001_v1"]["artifact"]
        ),
        "treatment": _compact(
            report["treatment_rm001_v3"]["artifact"]
        ),
        "realized_outcome_opened": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
