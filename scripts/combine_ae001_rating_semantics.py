from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_rating_semantics import (
    augment_feature_panel_with_rating_semantics,
    build_rating_semantic_panel,
    validate_rating_source_list,
)
from marketlab.events import sha256_bytes


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AlphaContractError(f"T008 expected JSON object: {path}")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine T008 semantic shards and build CORE44 feature panel"
    )
    parser.add_argument("--source-list", type=Path, required=True)
    parser.add_argument("--shard-dir", type=Path, required=True)
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_list = _load_json(args.source_list)
    validate_rating_source_list(source_list)

    shard_paths = sorted(args.shard_dir.rglob("*.json.gz"))
    if not shard_paths:
        raise AlphaContractError("T008 semantic shard directory is empty")
    all_records = []
    shard_indexes = set()
    expected_shard_count = None
    shard_hashes = []
    for path in shard_paths:
        raw = path.read_bytes()
        shard = load_canonical_gzip_json(raw)
        if shard.get("artifact_id") != "AE001-T008-RATING-SEMANTIC-SHARD-v1":
            continue
        if shard.get("source_list_sha256") != source_list["source_list_sha256"]:
            raise AlphaContractError("T008 shard source-list binding mismatch")
        if shard.get("market_return_outcomes_attached") is not False:
            raise AlphaContractError("T008 shard unexpectedly contains outcomes")
        shard_count = int(shard["shard_count"])
        shard_index = int(shard["shard_index"])
        if expected_shard_count is None:
            expected_shard_count = shard_count
        elif expected_shard_count != shard_count:
            raise AlphaContractError("T008 shard-count mismatch")
        if shard_index in shard_indexes:
            raise AlphaContractError("T008 duplicate shard index")
        shard_indexes.add(shard_index)
        shard_hashes.append(
            {
                "shard_index": shard_index,
                "artifact_sha256": shard["artifact_sha256"],
                "file_sha256": sha256_bytes(raw),
            }
        )
        all_records.extend(shard["records"])

    if expected_shard_count is None:
        raise AlphaContractError("T008 found no semantic shard artifacts")
    if shard_indexes != set(range(expected_shard_count)):
        raise AlphaContractError(
            f"T008 semantic shards incomplete: {sorted(shard_indexes)}"
        )

    semantic = build_rating_semantic_panel(
        source_list=source_list,
        records=all_records,
    )
    market_bytes = args.market_panel.read_bytes()
    feature_bytes = args.feature_panel.read_bytes()
    market = load_canonical_gzip_json(market_bytes)
    features = load_canonical_gzip_json(feature_bytes)
    augmented = augment_feature_panel_with_rating_semantics(
        feature_panel=features,
        market_panel=market,
        semantic_panel=semantic,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    semantic_bytes = canonical_gzip_json(semantic)
    augmented_bytes = canonical_gzip_json(augmented)
    (args.output / "rating-semantic-panel.json.gz").write_bytes(
        semantic_bytes
    )
    (args.output / "rating-feature-panel.json.gz").write_bytes(
        augmented_bytes
    )

    status_counts = Counter(
        str(record["status"])
        for record in semantic["records"]
    )
    manifest = {
        "schema_version": 1,
        "artifact_id": "AE001-T008-RATING-FEATURES-v1",
        "source_list_sha256": source_list["source_list_sha256"],
        "semantic_shards": sorted(
            shard_hashes,
            key=lambda row: row["shard_index"],
        ),
        "semantic_panel_sha256": semantic["panel_sha256"],
        "semantic_artifact_sha256": sha256_bytes(semantic_bytes),
        "semantic_status_counts": dict(sorted(status_counts.items())),
        "market_panel_sha256": market["panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "base_feature_panel_sha256": features["panel_sha256"],
        "base_feature_artifact_sha256": sha256_bytes(feature_bytes),
        "augmented_feature_panel_sha256": augmented["panel_sha256"],
        "augmented_feature_artifact_sha256": sha256_bytes(augmented_bytes),
        "feature_row_count": augmented["feature_row_count"],
        "mapped_event_count": augmented["rating_mapped_event_count"],
        "excluded_no_same_session_eq_identity": augmented[
            "rating_excluded_no_same_session_eq_identity"
        ],
        "excluded_after_last_decision_cutoff": augmented[
            "rating_excluded_after_last_decision_cutoff"
        ],
        "market_return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
