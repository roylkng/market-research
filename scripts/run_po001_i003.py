from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.po001_i003 import run_po001_i003


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


def _compact_surface(surface: dict) -> dict:
    return {
        key: value
        for key, value in surface.items()
        if key != "top_holdings"
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen PO001 I003 stock-specific impact snapshot"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--risk-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    actions = load_canonical_gzip_json(args.action_ledger.read_bytes())
    risk = load_canonical_gzip_json(args.risk_state.read_bytes())

    report = run_po001_i003(
        delivery_feature_panel=features,
        market_panel=market,
        action_ledger=actions,
        risk_state=risk,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "po001-i003-report.json.gz").write_bytes(report_bytes)

    summary = {
        "schema_version": 1,
        "study_id": report["study_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "decision_session": report["decision_session"],
        "horizon_sessions": report["horizon_sessions"],
        "realized_outcome_opened": report["realized_outcome_opened"],
        "reproduction_gates": report["reproduction_gates"],
        "common_identity_count": report["common_identity_count"],
        "training_example_count": report["training_example_count"],
        "training_last_exit_session": report["training_last_exit_session"],
        "execution_input_distribution": report[
            "execution_input_distribution"
        ],
        "observable_cost_bps": report["observable_cost_bps"],
        "v1_observable_cost_baseline": report[
            "v1_observable_cost_baseline"
        ],
        "v2_nav_surfaces": {
            key: _compact_surface(value)
            for key, value in report["v2_nav_surfaces"].items()
        },
        "primary_nav_inr": report["primary_nav_inr"],
        "primary_delta_vs_v1": report["primary_delta_vs_v1"],
        "impact_contract": report["impact_contract"],
        "interpretation_limits": report["interpretation_limits"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
