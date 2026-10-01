from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_v2_p001 import run_rm001_v2_p001


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
        description="Run frozen RM001-v2 P001 historical size-risk attribution"
    )
    parser.add_argument("--v1-risk-state", type=Path, required=True)
    parser.add_argument("--v2-risk-state", type=Path, required=True)
    parser.add_argument("--i002-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    v1_bytes = args.v1_risk_state.read_bytes()
    v2_bytes = args.v2_risk_state.read_bytes()
    control_bytes = args.i002_control.read_bytes()
    v1 = load_canonical_gzip_json(v1_bytes)
    v2 = load_canonical_gzip_json(v2_bytes)
    control = load_canonical_gzip_json(control_bytes)

    report = run_rm001_v2_p001(
        v1_risk_state=v1,
        v2_risk_state=v2,
        sealed_i002_artifact=control,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "rm001-v2-p001-report.json.gz").write_bytes(
        report_bytes
    )
    summary = {
        "schema_version": 1,
        "pilot_id": report["pilot_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "decision_session": report["decision_session"],
        "v1_risk_state_sha256": report["v1_risk_state_sha256"],
        "v2_risk_state_sha256": report["v2_risk_state_sha256"],
        "sealed_i002_artifact_sha256": report[
            "sealed_i002_artifact_sha256"
        ],
        "identity_overlap": report["identity_overlap"],
        "idiosyncratic": report["idiosyncratic"],
        "factor_daily_variances": report["factor_daily_variances"],
        "sealed_i002_portfolio_risk": report[
            "sealed_i002_portfolio_risk"
        ],
        "interpretation_limits": report["interpretation_limits"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
