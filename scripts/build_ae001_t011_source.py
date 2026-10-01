from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_t011 import (
    EXPECTED_ACTION_LEDGER_SHA256,
    build_t011_lagged_feature_panel,
    summarize_t011_source,
)
from marketlab.events import sha256_bytes


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build source-only AE001 T011 lagged-futures panel"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--current27-panel", type=Path, required=True)
    parser.add_argument("--t005-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    action_bytes = args.action_ledger.read_bytes()
    current_bytes = args.current27_panel.read_bytes()
    t005_bytes = args.t005_panel.read_bytes()

    market = load_canonical_gzip_json(market_bytes)
    actions = load_canonical_gzip_json(action_bytes)
    current27 = load_canonical_gzip_json(current_bytes)
    t005 = load_canonical_gzip_json(t005_bytes)
    if actions.get("ledger_sha256") != EXPECTED_ACTION_LEDGER_SHA256:
        raise AlphaContractError("T011 action ledger differs from frozen T005")

    panel = build_t011_lagged_feature_panel(
        market_panel=market,
        current27_panel=current27,
        t005_panel=t005,
    )
    report = summarize_t011_source(panel)

    args.output.mkdir(parents=True, exist_ok=True)
    panel_bytes = canonical_gzip_json(panel)
    (args.output / "t011-feature-panel.json.gz").write_bytes(panel_bytes)
    (args.output / "market-panel.json.gz").write_bytes(market_bytes)
    (args.output / "corporate-action-ledger.json.gz").write_bytes(action_bytes)

    manifest = {
        "schema_version": 1,
        "trial_id": "AE001-T011",
        "stage": "SOURCE_ONLY_PRE_OUTCOME",
        "market_panel_sha256": market["panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "corporate_action_ledger_sha256": actions["ledger_sha256"],
        "corporate_action_artifact_sha256": sha256_bytes(action_bytes),
        "current27_feature_panel_sha256": current27["panel_sha256"],
        "current27_feature_artifact_sha256": sha256_bytes(current_bytes),
        "t005_same_session37_feature_panel_sha256": t005["panel_sha256"],
        "t005_same_session37_feature_artifact_sha256": sha256_bytes(t005_bytes),
        "lagged37_feature_panel_sha256": panel["panel_sha256"],
        "lagged37_feature_artifact_sha256": sha256_bytes(panel_bytes),
        "feature_set_sha256": panel["feature_set_sha256"],
        "feature_session_count": panel["session_count"],
        "feature_row_count": panel["feature_row_count"],
        "excluded_missing_lagged_futures_row_count": panel[
            "excluded_missing_lagged_futures_row_count"
        ],
        "max_copied_futures_abs_diff": panel["max_copied_futures_abs_diff"],
        "report_sha256": report["report_sha256"],
        "status": report["status"],
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    _write_json(args.output / "source-report.json", report)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
