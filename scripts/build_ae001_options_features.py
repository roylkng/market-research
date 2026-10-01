from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_options import (
    acquire_historical_options_panel,
    augment_feature_panel_with_options,
)
from marketlab.events import sha256_bytes

EXPECTED_MARKET_PANEL_SHA256 = (
    "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
)
EXPECTED_T005_FULL37_PANEL_SHA256 = (
    "62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f"
)
EXPECTED_D006_SOURCE_HASHES_SHA256 = (
    "edf21ed30ea4021a82118c8699f1a7470442bcee29155810772a09c4b24bc6dc"
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
        description="Materialize T009 options source and 47-feature panel only"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    feature_bytes = args.feature_panel.read_bytes()
    market = load_canonical_gzip_json(market_bytes)
    features = load_canonical_gzip_json(feature_bytes)

    if market.get("panel_sha256") != EXPECTED_MARKET_PANEL_SHA256:
        raise ValueError("T009 market panel differs from frozen upstream")
    if features.get("panel_sha256") != EXPECTED_T005_FULL37_PANEL_SHA256:
        raise ValueError("T009 base 37-feature panel differs from frozen T005")

    sessions = market.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("T009 market panel sessions are required")
    session_dates = [str(row["session_date"]) for row in sessions]

    captured = datetime.now(UTC)
    options = acquire_historical_options_panel(
        session_dates=session_dates,
        fetcher=http_fetcher(
            attempts=args.attempts,
            timeout=args.timeout_seconds,
        ),
        store_root=args.store,
        captured_at_utc=captured,
    )
    if (
        options["source_hashes_sha256"]
        != EXPECTED_D006_SOURCE_HASHES_SHA256
    ):
        raise ValueError("T009 options source hash chain differs from D006")
    if options["unavailable_session_count"] != 0:
        raise ValueError("T009 options source has unavailable sessions")
    if options["parser_rejected_session_count"] != 0:
        raise ValueError("T009 options source has parser-rejected sessions")

    augmented = augment_feature_panel_with_options(
        feature_panel=features,
        market_panel=market,
        options_panel=options,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    options_bytes = canonical_gzip_json(options)
    feature_bytes_out = canonical_gzip_json(augmented)
    (args.output / "options-panel.json.gz").write_bytes(options_bytes)
    (args.output / "options-feature-panel.json.gz").write_bytes(
        feature_bytes_out
    )

    manifest = {
        "schema_version": 1,
        "artifact_id": "AE001-T009-SOURCE-MATERIALIZATION-v1",
        "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "market_panel_sha256": market["panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "base_37_feature_panel_sha256": features["panel_sha256"],
        "base_37_feature_artifact_sha256": sha256_bytes(feature_bytes),
        "options_panel_sha256": options["panel_sha256"],
        "options_artifact_sha256": sha256_bytes(options_bytes),
        "options_source_hashes_sha256": options[
            "source_hashes_sha256"
        ],
        "options_ready_session_count": options["ready_session_count"],
        "options_unavailable_session_count": options[
            "unavailable_session_count"
        ],
        "options_parser_rejected_session_count": options[
            "parser_rejected_session_count"
        ],
        "augmented_47_feature_panel_sha256": augmented["panel_sha256"],
        "augmented_47_feature_artifact_sha256": sha256_bytes(
            feature_bytes_out
        ),
        "option_complete_feature_row_count": augmented[
            "feature_row_count"
        ],
        "option_complete_session_count": augmented["session_count"],
        "exclusion_counts": augmented["exclusion_counts"],
        "outcomes_opened": False,
        "model_fit_started": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
