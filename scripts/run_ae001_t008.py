from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_fundamental_trial import run_t008_trial
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


def _compact_horizon(value: dict) -> dict:
    return {
        key: val
        for key, val in value.items()
        if key not in {"oos_predictions"}
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AE001 T008 fundamental alpha trial"
    )
    parser.add_argument("--d004-panel", type=Path, required=True)
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--trial-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    d004 = _load_json(args.d004_panel)
    market_bytes = args.market_panel.read_bytes()
    action_bytes = args.action_ledger.read_bytes()
    market = load_canonical_gzip_json(market_bytes)
    actions = load_canonical_gzip_json(action_bytes)
    trials = _load_json(args.trial_ledger)

    report = run_t008_trial(
        d004_panel=d004,
        market_panel=market,
        action_ledger=actions,
        trial_ledger=trials,
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
        "source_panel_sha256": report["source_panel_sha256"],
        "market_panel_sha256": report["market_panel_sha256"],
        "corporate_action_ledger_sha256": report[
            "corporate_action_ledger_sha256"
        ],
        "trial_registration_event_sha256": report[
            "trial_registration_event_sha256"
        ],
        "feature_names": report["feature_names"],
        "feature_transform": report["feature_transform"],
        "entry_rule": report["entry_rule"],
        "primary": _compact_horizon(report["primary"]),
        "secondary": _compact_horizon(report["secondary"]),
        "primary_label_exclusions": report["primary_label_exclusions"],
        "secondary_label_exclusions": report["secondary_label_exclusions"],
        "sample_gates": report["sample_gates"],
        "primary_success_gates": report["primary_success_gates"],
        "primary_supported": report["primary_supported"],
        "secondary_can_rescue_primary": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
