from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_v3 import build_rm001_v3_risk_state


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
        description="Build one historical RM001-v3 statistical risk state"
    )
    parser.add_argument("--v2-risk-state", type=Path, required=True)
    parser.add_argument("--v2-factor-history", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    risk_bytes = args.v2_risk_state.read_bytes()
    history_bytes = args.v2_factor_history.read_bytes()
    v2_risk = load_canonical_gzip_json(risk_bytes)
    v2_history = load_canonical_gzip_json(history_bytes)

    state = build_rm001_v3_risk_state(
        v2_risk_state=v2_risk,
        v2_factor_history=v2_history,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    state_bytes = canonical_gzip_json(state)
    (args.output / "risk-state.json.gz").write_bytes(state_bytes)

    covariance = state["factor_covariance_daily"]
    factor_daily_variances = {
        factor: covariance[index][index]
        for index, factor in enumerate(state["factor_names"])
    }
    status_counts: dict[str, int] = {}
    for row in state["rows"]:
        status = str(row["statistical_status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    summary = {
        "schema_version": 1,
        "model_id": state["model_id"],
        "as_of_session": state["as_of_session"],
        "input_v2_risk_artifact_sha256": sha256_bytes(risk_bytes),
        "input_v2_factor_history_artifact_sha256": sha256_bytes(history_bytes),
        "parent_v2_risk_state_sha256": state["parent_v2_risk_state_sha256"],
        "parent_v2_factor_history_sha256": state[
            "parent_v2_factor_history_sha256"
        ],
        "risk_state_sha256": state["state_sha256"],
        "risk_state_artifact_sha256": sha256_bytes(state_bytes),
        "security_count": state["security_count"],
        "factor_count": len(state["factor_names"]),
        "named_factor_names": state["named_factor_names"],
        "statistical_factor_names": state["statistical_factor_names"],
        "statistical_window": state["statistical_window"],
        "risk_estimation_window": state["risk_estimation_window"],
        "complete_statistical_identity_count": state[
            "complete_statistical_identity_count"
        ],
        "fallback_identity_count": state["fallback_identity_count"],
        "singular_values": state["singular_values"],
        "adjacent_singular_relative_gaps": state[
            "adjacent_singular_relative_gaps"
        ],
        "statistical_explained_variance_ratio": state[
            "statistical_explained_variance_ratio"
        ],
        "statistical_explained_variance_ratio_total": sum(
            state["statistical_explained_variance_ratio"]
        ),
        "statistical_sign_anchors": state["statistical_sign_anchors"],
        "factor_daily_variances": factor_daily_variances,
        "statistical_status_counts": dict(sorted(status_counts.items())),
        "deferred_factors": state["deferred_factors"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
