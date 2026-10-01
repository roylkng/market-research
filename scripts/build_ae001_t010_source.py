from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_t010 import (
    EXPECTED_ACTION_LEDGER_SHA256,
    EXPECTED_MARKET_PANEL_SHA256,
    build_t010_feature_panel,
    summarize_t010_source,
)
from marketlab.events import sha256_bytes


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
        description="Build source-only AE001 T010 44-feature common panel"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--t005-panel", type=Path, required=True)
    parser.add_argument("--d010-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    action_bytes = args.action_ledger.read_bytes()
    t005_bytes = args.t005_panel.read_bytes()
    d010_bytes = args.d010_panel.read_bytes()

    market = load_canonical_gzip_json(market_bytes)
    actions = load_canonical_gzip_json(action_bytes)
    t005 = load_canonical_gzip_json(t005_bytes)
    d010 = load_canonical_gzip_json(d010_bytes)

    if market.get("panel_sha256") != EXPECTED_MARKET_PANEL_SHA256:
        raise AlphaContractError("T010 source market panel differs from T005")
    if actions.get("ledger_sha256") != EXPECTED_ACTION_LEDGER_SHA256:
        raise AlphaContractError("T010 source action ledger differs from T005")

    combined = build_t010_feature_panel(
        t005_feature_panel=t005,
        d010_feature_panel=d010,
    )
    report = summarize_t010_source(combined)

    args.output.mkdir(parents=True, exist_ok=True)
    combined_bytes = canonical_gzip_json(combined)
    (args.output / "t010-feature-panel.json.gz").write_bytes(combined_bytes)
    (args.output / "market-panel.json.gz").write_bytes(market_bytes)
    (args.output / "corporate-action-ledger.json.gz").write_bytes(action_bytes)

    manifest = {
        "schema_version": 1,
        "trial_id": "AE001-T010",
        "stage": "SOURCE_ONLY_PRE_OUTCOME",
        "market_panel_sha256": market["panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "corporate_action_ledger_sha256": actions["ledger_sha256"],
        "corporate_action_artifact_sha256": sha256_bytes(action_bytes),
        "base37_feature_panel_sha256": t005["panel_sha256"],
        "base37_feature_artifact_sha256": sha256_bytes(t005_bytes),
        "d010_p4a_feature_panel_sha256": d010["panel_sha256"],
        "d010_p4a_feature_artifact_sha256": sha256_bytes(d010_bytes),
        "combined44_feature_panel_sha256": combined["panel_sha256"],
        "combined44_feature_artifact_sha256": sha256_bytes(combined_bytes),
        "feature_set_sha256": combined["feature_set_sha256"],
        "feature_session_count": combined["session_count"],
        "feature_row_count": combined["feature_row_count"],
        "excluded_no_d010_row_count": combined["excluded_no_d010_row_count"],
        "max_overlapping_base_feature_abs_diff": combined[
            "max_overlapping_base_feature_abs_diff"
        ],
        "report_sha256": report["report_sha256"],
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
