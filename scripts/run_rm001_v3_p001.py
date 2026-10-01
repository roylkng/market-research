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


def _load_json_gzip(path: Path) -> dict:
    return load_canonical_gzip_json(path.read_bytes())


def _compact_portfolio(value: dict) -> dict:
    return {
        "position_count": value["position_count"],
        "total_variance_daily_delta": value[
            "total_variance_daily_delta"
        ],
        "factor_variance_daily_delta": value[
            "factor_variance_daily_delta"
        ],
        "idiosyncratic_variance_daily_delta": value[
            "idiosyncratic_variance_daily_delta"
        ],
        "annualized_volatility_delta": value[
            "annualized_volatility_delta"
        ],
        "v2_annualized_volatility": value["v2"][
            "annualized_volatility"
        ],
        "v3_annualized_volatility": value["v3"][
            "annualized_volatility"
        ],
        "v2_factor_variance_daily": value["v2"][
            "factor_variance_daily"
        ],
        "v3_factor_variance_daily": value["v3"][
            "factor_variance_daily"
        ],
        "v2_idiosyncratic_variance_daily": value["v2"][
            "idiosyncratic_variance_daily"
        ],
        "v3_idiosyncratic_variance_daily": value["v3"][
            "idiosyncratic_variance_daily"
        ],
        "statistical_factor_exposures": value[
            "statistical_factor_exposures"
        ],
        "statistical_factor_variance_contributions_daily": value[
            "statistical_factor_variance_contributions_daily"
        ],
        "total_statistical_factor_variance_contribution_daily": value[
            "total_statistical_factor_variance_contribution_daily"
        ],
        "named_factor_exposure_delta": value[
            "named_factor_exposure_delta"
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen RM001-v3 P001 historical attribution"
    )
    parser.add_argument("--v2-risk-state", type=Path, required=True)
    parser.add_argument("--v3-risk-state", type=Path, required=True)
    parser.add_argument("--i002-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    v2_bytes = args.v2_risk_state.read_bytes()
    v3_bytes = args.v3_risk_state.read_bytes()
    control_bytes = args.i002_control.read_bytes()

    v2 = load_canonical_gzip_json(v2_bytes)
    v3 = load_canonical_gzip_json(v3_bytes)
    control = load_canonical_gzip_json(control_bytes)

    report = run_rm001_v3_p001(
        v2_risk_state=v2,
        v3_risk_state=v3,
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
        "v2_risk_state_sha256": report["v2_risk_state_sha256"],
        "v3_risk_state_sha256": report["v3_risk_state_sha256"],
        "v2_risk_artifact_sha256": sha256_bytes(v2_bytes),
        "v3_risk_artifact_sha256": sha256_bytes(v3_bytes),
        "i002_control_artifact_sha256": sha256_bytes(control_bytes),
        "treatment_isolation": report["treatment_isolation"],
        "identity": report["identity"],
        "statistical_basis": report["statistical_basis"],
        "complete_identity_idiosyncratic": report[
            "complete_identity_idiosyncratic"
        ],
        "sealed_i002_portfolio_risk": {
            key: _compact_portfolio(value)
            for key, value in report[
                "sealed_i002_portfolio_risk"
            ].items()
        },
        "interpretation_limits": report["interpretation_limits"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
