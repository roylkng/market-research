from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_v3_p001 import run_rm001_v3_p001


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
        description="Run frozen RM001-v3 P001 historical risk attribution"
    )
    parser.add_argument("--v2-risk-state", type=Path, required=True)
    parser.add_argument("--v2-factor-history", type=Path, required=True)
    parser.add_argument("--v3-risk-state", type=Path, required=True)
    parser.add_argument("--i002-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    v2_risk_bytes = args.v2_risk_state.read_bytes()
    v2_history_bytes = args.v2_factor_history.read_bytes()
    v3_risk_bytes = args.v3_risk_state.read_bytes()
    control_bytes = args.i002_control.read_bytes()

    v2_risk = load_canonical_gzip_json(v2_risk_bytes)
    v2_history = load_canonical_gzip_json(v2_history_bytes)
    v3_risk = load_canonical_gzip_json(v3_risk_bytes)
    control = load_canonical_gzip_json(control_bytes)

    report = run_rm001_v3_p001(
        v2_risk_state=v2_risk,
        v2_factor_history=v2_history,
        v3_risk_state=v3_risk,
        sealed_i002_artifact=control,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "rm001-v3-p001-report.json.gz").write_bytes(
        report_bytes
    )

    summary = {
        "schema_version": 1,
        "pilot_id": report["pilot_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "decision_session": report["decision_session"],
        "input_v2_risk_artifact_sha256": sha256_bytes(v2_risk_bytes),
        "input_v2_factor_history_artifact_sha256": sha256_bytes(
            v2_history_bytes
        ),
        "input_v3_risk_artifact_sha256": sha256_bytes(v3_risk_bytes),
        "input_i002_control_artifact_sha256": sha256_bytes(control_bytes),
        "v2_risk_state_sha256": report["v2_risk_state_sha256"],
        "v2_factor_history_sha256": report["v2_factor_history_sha256"],
        "v3_risk_state_sha256": report["v3_risk_state_sha256"],
        "sealed_i002_artifact_sha256": report[
            "sealed_i002_artifact_sha256"
        ],
        "identity": report["identity"],
        "statistical_basis": report["statistical_basis"],
        "idiosyncratic": report["idiosyncratic"],
        "factor_daily_variances": report["factor_daily_variances"],
        "sealed_i002_portfolio_risk": report[
            "sealed_i002_portfolio_risk"
        ],
        "control_resolution": report["control_resolution"],
        "interpretation_limits": report["interpretation_limits"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
