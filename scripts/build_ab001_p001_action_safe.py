from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_corporate_actions import (
    filter_feature_panel_for_corporate_actions,
    validate_action_ledger,
)
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes

EXPECTED_ACTION_LEDGER_SHA = (
    "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
)
EXPECTED_ACTION_GZIP_SHA = (
    "6ee878d48eadae0b76c7b4db3a02b3f1fb6cada61c2d3c39b40fb872b1622e2d"
)
EXPECTED_SAFE_PANEL_SHA = (
    "300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8"
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
        description="Build P001 action-safe features from the exact pinned T003 ledger"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--action-ledger-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    feature_bytes = args.feature_panel.read_bytes()
    ledger_bytes = args.action_ledger.read_bytes()
    manifest = json.loads(
        args.action_ledger_manifest.read_text(encoding="utf-8")
    )
    if not isinstance(manifest, dict):
        raise TypeError("P001 pinned action manifest must be a JSON object")
    if manifest.get("internal_ledger_sha256") != EXPECTED_ACTION_LEDGER_SHA:
        raise ValueError("P001 pinned action manifest internal SHA mismatch")
    if manifest.get("gzip_file_sha256") != EXPECTED_ACTION_GZIP_SHA:
        raise ValueError("P001 pinned action manifest gzip SHA mismatch")
    if sha256_bytes(ledger_bytes) != EXPECTED_ACTION_GZIP_SHA:
        raise ValueError("P001 pinned action gzip bytes do not match frozen SHA")

    market = load_canonical_gzip_json(market_bytes)
    features = load_canonical_gzip_json(feature_bytes)
    ledger = load_canonical_gzip_json(ledger_bytes)
    validate_action_ledger(ledger)
    if ledger["ledger_sha256"] != EXPECTED_ACTION_LEDGER_SHA:
        raise ValueError("P001 pinned action ledger internal SHA mismatch")

    safe = filter_feature_panel_for_corporate_actions(
        feature_panel=features,
        market_panel=market,
        action_ledger=ledger,
        lookback_sessions=60,
    )
    if safe["panel_sha256"] != EXPECTED_SAFE_PANEL_SHA:
        raise ValueError(
            "P001 pinned action ledger did not reproduce sealed T003 safe panel: "
            f"{safe['panel_sha256']}"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    safe_bytes = canonical_gzip_json(safe)
    (args.output / "corporate-action-ledger.json.gz").write_bytes(
        ledger_bytes
    )
    (args.output / "action-safe-feature-panel.json.gz").write_bytes(
        safe_bytes
    )

    output_manifest = {
        "schema_version": 1,
        "artifact_id": "AB001-P001-ACTION-SAFE-FROM-PINNED-T003-v1",
        "input_market_artifact_sha256": sha256_bytes(market_bytes),
        "input_feature_artifact_sha256": sha256_bytes(feature_bytes),
        "pinned_action_manifest": manifest,
        "corporate_action_ledger_sha256": ledger["ledger_sha256"],
        "corporate_action_artifact_sha256": sha256_bytes(ledger_bytes),
        "action_safe_feature_panel_sha256": safe["panel_sha256"],
        "action_safe_feature_artifact_sha256": sha256_bytes(safe_bytes),
        "input_feature_row_count": features["feature_row_count"],
        "action_safe_feature_row_count": safe["feature_row_count"],
        "action_blocked_feature_row_count": safe[
            "corporate_action_blocked_feature_row_count"
        ],
        "action_unresolved_feature_row_count": safe[
            "corporate_action_unresolved_feature_row_count"
        ],
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", output_manifest)
    print(json.dumps(output_manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
