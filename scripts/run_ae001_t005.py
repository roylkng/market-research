from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_futures_trial import run_futures_incremental_trial
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
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


def _compact(report: dict) -> dict:
    return {
        key: value
        for key, value in report.items()
        if key != "session_metrics"
    }


def _comparison_summary(value: dict) -> dict:
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
        description="Run frozen AE001 T005 stock-futures incremental trial"
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

    report = run_futures_incremental_trial(
        market_panel=market,
        feature_panel=features,
        action_ledger=actions,
        trial_ledger=trials,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "t005-report.json.gz").write_bytes(report_bytes)

    primary = report["primary_5d"]
    inference = primary["augmented_minus_base_inference"]["metrics"]
    primary_supported = (
        float(inference["rank_ic"]["mean"]) > 0
        and float(inference["rank_ic"]["p_value_two_sided"]) < 0.05
        and float(inference["top_minus_bottom_spread"]["mean"]) > 0
        and float(
            inference["top_minus_bottom_spread"]["p_value_two_sided"]
        )
        < 0.05
    )
    summary = {
        "schema_version": 1,
        "trial_id": report["trial_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "evidence_class": report["evidence_class"],
        "market_panel_sha256": report["market_panel_sha256"],
        "feature_panel_sha256": report["feature_panel_sha256"],
        "base_feature_panel_sha256": report["base_feature_panel_sha256"],
        "futures_panel_sha256": report["futures_panel_sha256"],
        "corporate_action_ledger_sha256": report[
            "corporate_action_ledger_sha256"
        ],
        "primary_5d": _comparison_summary(report["primary_5d"]),
        "secondary_1d": _comparison_summary(report["secondary_1d"]),
        "diagnostic_20d": _comparison_summary(report["diagnostic_20d"]),
        "primary_success_criteria_supported": primary_supported,
        "historical_fo_publication_timestamp_verified": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
