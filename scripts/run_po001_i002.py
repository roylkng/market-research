from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.po001_i002 import run_po001_i002


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


def _compact_portfolio(portfolio: dict) -> dict:
    return {
        key: value
        for key, value in portfolio.items()
        if key not in {"positions"}
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen PO001 I002 walk-forward OOS integrated snapshot"
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

    artifact = run_po001_i002(
        delivery_feature_panel=features,
        market_panel=market,
        action_ledger=actions,
        risk_state=risk,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    artifact_bytes = canonical_gzip_json(artifact)
    (args.output / "po001-i002-artifact.json.gz").write_bytes(
        artifact_bytes
    )

    summary = {
        "schema_version": 1,
        "study_id": artifact["study_id"],
        "artifact_sha256": artifact["artifact_sha256"],
        "artifact_file_sha256": sha256_bytes(artifact_bytes),
        "evidence_class": artifact["evidence_class"],
        "decision_session": artifact["decision_session"],
        "source_end_date": artifact["source_end_date"],
        "horizon_sessions": artifact["horizon_sessions"],
        "realized_outcome_opened": artifact["realized_outcome_opened"],
        "alpha_source": artifact["alpha_source"],
        "risk_source": artifact["risk_source"],
        "cost_source": artifact["cost_source"],
        "frozen_parameters": artifact["frozen_parameters"],
        "common_identity_count": artifact["common_identity_count"],
        "top_decile_count": artifact["top_decile_count"],
        "alpha_distribution": artifact["alpha_distribution"],
        "portfolios": {
            name: _compact_portfolio(portfolio)
            for name, portfolio in artifact["portfolios"].items()
        },
        "interpretation_limits": artifact["interpretation_limits"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
