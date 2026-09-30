from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_fundamental_trial import run_t008_trial
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.universe import load_universe_snapshot


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


def _compact_horizon(value: dict) -> dict:
    return {
        "horizon_sessions": value["horizon_sessions"],
        "pooled_weighted_delta_rank_ic": value[
            "pooled_weighted_delta_rank_ic"
        ],
        "pooled_weighted_delta_quintile_spread": value[
            "pooled_weighted_delta_quintile_spread"
        ],
        "cluster_bootstrap": value["cluster_bootstrap"],
        "endpoint_supported": value["endpoint_supported"],
        "folds": [
            {
                "fold": fold["fold"],
                "validation_target_period": fold[
                    "validation_target_period"
                ],
                "training_target_periods": fold[
                    "training_target_periods"
                ],
                "earliest_validation_decision_session": fold[
                    "earliest_validation_decision_session"
                ],
                "training_event_count": fold["training_event_count"],
                "validation_event_count": fold["validation_event_count"],
                "training_last_exit_session": fold[
                    "training_last_exit_session"
                ],
                "base_model_sha256": fold["base_model_sha256"],
                "augmented_model_sha256": fold[
                    "augmented_model_sha256"
                ],
                "base": fold["base"],
                "augmented": fold["augmented"],
                "delta_rank_ic": fold["delta_rank_ic"],
                "delta_quintile_spread": fold[
                    "delta_quintile_spread"
                ],
                "decision_week_count": fold["decision_week_count"],
                "mean_augmented_minus_base_prediction": fold[
                    "mean_augmented_minus_base_prediction"
                ],
            }
            for fold in value["folds"]
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AE001 T008 fundamental alpha trial"
    )
    parser.add_argument("--d004-panel", type=Path, required=True)
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--delivery-feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--trial-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    d004 = _load_json(args.d004_panel)
    market_bytes = args.market_panel.read_bytes()
    delivery_bytes = args.delivery_feature_panel.read_bytes()
    action_bytes = args.action_ledger.read_bytes()
    market = load_canonical_gzip_json(market_bytes)
    delivery = load_canonical_gzip_json(delivery_bytes)
    actions = load_canonical_gzip_json(action_bytes)
    trial_ledger = _load_json(args.trial_ledger)
    universe = load_universe_snapshot(args.universe)
    identity_map = {
        member.symbol.upper(): member.isin
        for member in universe.members
        if member.isin
    }

    report = run_t008_trial(
        d004_panel=d004,
        delivery_feature_panel=delivery,
        market_panel=market,
        action_ledger=actions,
        universe_identity_by_symbol=identity_map,
        trial_ledger=trial_ledger,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "t008-report.json.gz").write_bytes(report_bytes)

    summary = {
        "schema_version": 1,
        "trial_id": report["trial_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "evidence_class": report["evidence_class"],
        "source": report["source"],
        "feature_contract": report["feature_contract"],
        "primary_20d": _compact_horizon(report["primary_20d"]),
        "secondary_5d": _compact_horizon(report["secondary_5d"]),
        "interpretation": report["interpretation"],
        "secondary_may_rescue_primary": report[
            "secondary_may_rescue_primary"
        ],
        "prospective_claim_allowed": report[
            "prospective_claim_allowed"
        ],
        "historical_delivery_publication_timing_verified": report[
            "historical_delivery_publication_timing_verified"
        ],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
