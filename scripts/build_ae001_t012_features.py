from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_announcement_semantics import (
    augment_feature_panel_with_hashed_semantics,
)
from marketlab.alpha_history import (
    canonical_gzip_json,
    load_canonical_gzip_json,
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
        description="Build frozen AE001 T012 hashed announcement semantic features"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--announcement-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    feature_bytes = args.feature_panel.read_bytes()
    announcement_bytes = args.announcement_panel.read_bytes()
    market = load_canonical_gzip_json(market_bytes)
    features = load_canonical_gzip_json(feature_bytes)
    announcements = load_canonical_gzip_json(announcement_bytes)

    augmented = augment_feature_panel_with_hashed_semantics(
        feature_panel=features,
        market_panel=market,
        announcement_panel=announcements,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    output_bytes = canonical_gzip_json(augmented)
    output_path = args.output / "semantic-feature-panel.json.gz"
    output_path.write_bytes(output_bytes)

    manifest = {
        "schema_version": 1,
        "artifact_id": "AE001-T012-HISTORICAL-SEMANTIC-FEATURES-v1",
        "trial_id": "AE001-T012",
        "market_panel_sha256": market["panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "base_feature_panel_sha256": features["panel_sha256"],
        "base_feature_artifact_sha256": sha256_bytes(feature_bytes),
        "announcement_panel_sha256": announcements["panel_sha256"],
        "announcement_artifact_sha256": sha256_bytes(announcement_bytes),
        "semantic_feature_panel_sha256": augmented["panel_sha256"],
        "semantic_feature_artifact_sha256": sha256_bytes(output_bytes),
        "semantic_feature_definition_sha256": augmented[
            "semantic_feature_definition_sha256"
        ],
        "semantic_hash_dimensions": augmented["semantic_hash_dimensions"],
        "semantic_eligible_event_count": augmented[
            "semantic_eligible_event_count"
        ],
        "semantic_nonzero_feature_row_count": augmented[
            "semantic_nonzero_feature_row_count"
        ],
        "feature_row_count": augmented["feature_row_count"],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
