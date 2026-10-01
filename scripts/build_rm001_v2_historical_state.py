from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_v2 import (
    build_rm001_v2_exposure_panel,
    build_rm001_v2_factor_history,
    build_rm001_v2_risk_state,
)


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
        description="Build one historical RM001-v2 size-aware risk state"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--size-panel", type=Path, required=True)
    parser.add_argument("--as-of-session", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    feature_bytes = args.feature_panel.read_bytes()
    action_bytes = args.action_ledger.read_bytes()
    size_bytes = args.size_panel.read_bytes()

    market = load_canonical_gzip_json(market_bytes)
    features = load_canonical_gzip_json(feature_bytes)
    actions = load_canonical_gzip_json(action_bytes)
    sizes = load_canonical_gzip_json(size_bytes)

    exposures = build_rm001_v2_exposure_panel(
        feature_panel=features,
        market_panel=market,
        action_ledger=actions,
        size_panel=sizes,
    )
    history = build_rm001_v2_factor_history(
        exposure_panel=exposures,
        market_panel=market,
        action_ledger=actions,
    )
    state = build_rm001_v2_risk_state(
        exposure_panel=exposures,
        factor_history=history,
        as_of_session=args.as_of_session,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    exposure_bytes = canonical_gzip_json(exposures)
    history_bytes = canonical_gzip_json(history)
    state_bytes = canonical_gzip_json(state)
    (args.output / "exposure-panel.json.gz").write_bytes(exposure_bytes)
    (args.output / "factor-history.json.gz").write_bytes(history_bytes)
    (args.output / "risk-state.json.gz").write_bytes(state_bytes)

    covariance = state["factor_covariance_daily"]
    diagonal = {
        factor: covariance[index][index]
        for index, factor in enumerate(state["factor_names"])
    }
    idio_status_counts: dict[str, int] = {}
    for row in state["rows"]:
        status = str(row["idiosyncratic_status"])
        idio_status_counts[status] = idio_status_counts.get(status, 0) + 1

    summary = {
        "schema_version": 1,
        "model_id": state["model_id"],
        "as_of_session": state["as_of_session"],
        "input_market_artifact_sha256": sha256_bytes(market_bytes),
        "input_feature_artifact_sha256": sha256_bytes(feature_bytes),
        "input_action_artifact_sha256": sha256_bytes(action_bytes),
        "input_size_artifact_sha256": sha256_bytes(size_bytes),
        "exposure_panel_sha256": exposures["panel_sha256"],
        "factor_history_sha256": history["history_sha256"],
        "risk_state_sha256": state["state_sha256"],
        "exposure_count": exposures["exposure_count"],
        "factor_return_count": history["factor_return_count"],
        "residual_count": history["residual_count"],
        "security_count": state["security_count"],
        "factor_covariance_window": state["factor_covariance_window"],
        "factor_covariance_first_realized_session": state[
            "factor_covariance_first_realized_session"
        ],
        "factor_covariance_last_realized_session": state[
            "factor_covariance_last_realized_session"
        ],
        "factor_daily_variances": diagonal,
        "idiosyncratic_status_counts": dict(sorted(idio_status_counts.items())),
        "idiosyncratic_fallback_p75": state["idiosyncratic_fallback_p75"],
        "size_contract": state["size_contract"],
        "deferred_factors": state["deferred_factors"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
