from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_delivery_trial import (
    PROTOCOL_ID,
    TRIAL_ID,
    run_delivery_incremental_trial,
)
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_trials import require_protocol_amendment
from marketlab.events import sha256_bytes


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


def _folds(payload: dict, horizon: str) -> list[dict[str, str]]:
    return [
        {"start": start, "end": end}
        for start, end in payload["folds"][horizon]
    ]


def _compact(report: dict) -> dict:
    return {
        key: value
        for key, value in report.items()
        if key != "session_metrics"
    }


def _horizon_summary(value: dict) -> dict:
    return {
        "horizon_sessions": value["horizon_sessions"],
        "base": _compact(value["base"]["ridge"]),
        "augmented": _compact(value["augmented"]["ridge"]),
        "augmented_minus_base_inference": value[
            "augmented_minus_base_inference"
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AE001 T003 delivery incremental trial"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--trial-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    actions = load_canonical_gzip_json(args.action_ledger.read_bytes())
    trials = _load_json(args.trial_ledger)
    protocol = require_protocol_amendment(
        trials,
        trial_id=TRIAL_ID,
        protocol_id=PROTOCOL_ID,
    )
    frozen = protocol["payload"]

    report = run_delivery_incremental_trial(
        market_panel=market,
        feature_panel=features,
        action_ledger=actions,
        trial_ledger=trials,
        folds_1d=_folds(frozen, "1"),
        folds_5d=_folds(frozen, "5"),
        folds_20d=_folds(frozen, "20"),
        l2=float(frozen["ridge_l2"]),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "delivery-trial-report.json.gz").write_bytes(report_bytes)
    summary = {
        "schema_version": 1,
        "trial_id": TRIAL_ID,
        "trial_protocol_id": PROTOCOL_ID,
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "market_panel_sha256": report["market_panel_sha256"],
        "feature_panel_sha256": report["feature_panel_sha256"],
        "corporate_action_ledger_sha256": report[
            "corporate_action_ledger_sha256"
        ],
        "trial_ledger_sha256": report["trial_ledger_sha256"],
        "base_feature_count": len(report["base_feature_names"]),
        "delivery_feature_count": len(report["delivery_feature_names"]),
        "augmented_feature_count": len(report["augmented_feature_names"]),
        "primary_1d": _horizon_summary(report["primary_1d"]),
        "secondary_5d": _horizon_summary(report["secondary_5d"]),
        "diagnostic_20d": _horizon_summary(report["diagnostic_20d"]),
        "horizon_60_excluded_by_frozen_trial": True,
        "cost_model_status": report["cost_model_status"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
