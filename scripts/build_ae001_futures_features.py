from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_futures import (
    acquire_historical_futures_panel,
    augment_feature_panel_with_futures,
)
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
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
        description="Build reusable historical AE001 stock-futures feature panel"
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

    sessions = market.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("market panel sessions are required")
    session_dates = [str(row["session_date"]) for row in sessions]

    captured = datetime.now(UTC)
    futures = acquire_historical_futures_panel(
        session_dates=session_dates,
        fetcher=http_fetcher(
            attempts=args.attempts,
            timeout=args.timeout_seconds,
        ),
        store_root=args.store,
        captured_at_utc=captured,
    )
    augmented = augment_feature_panel_with_futures(
        feature_panel=features,
        market_panel=market,
        futures_panel=futures,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    futures_bytes = canonical_gzip_json(futures)
    augmented_bytes = canonical_gzip_json(augmented)
    (args.output / "futures-panel.json.gz").write_bytes(futures_bytes)
    (args.output / "futures-feature-panel.json.gz").write_bytes(
        augmented_bytes
    )

    manifest = {
        "schema_version": 1,
        "artifact_id": "AE001-HISTORICAL-STOCK-FUTURES-FEATURES-v1",
        "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
        "market_panel_sha256": market["panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "base_feature_panel_sha256": features["panel_sha256"],
        "base_feature_artifact_sha256": sha256_bytes(feature_bytes),
        "futures_panel_sha256": futures["panel_sha256"],
        "futures_artifact_sha256": sha256_bytes(futures_bytes),
        "futures_ready_session_count": futures["ready_session_count"],
        "futures_unavailable_session_count": futures[
            "unavailable_session_count"
        ],
        "futures_parser_rejected_session_count": futures[
            "parser_rejected_session_count"
        ],
        "augmented_feature_panel_sha256": augmented["panel_sha256"],
        "augmented_feature_artifact_sha256": sha256_bytes(
            augmented_bytes
        ),
        "futures_feature_row_count": augmented["feature_row_count"],
        "exclusion_counts": augmented["exclusion_counts"],
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
