from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.alpha_acquisition import (
    acquire_historical_market_panel,
    http_fetcher,
)
from marketlab.alpha_history import (
    build_historical_feature_panel,
    canonical_gzip_json,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build official-NSE AE001 historical market and feature panels"
    )
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    captured = datetime.now(UTC)
    fetcher = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    market = acquire_historical_market_panel(
        start_date=args.start_date,
        end_date=args.end_date,
        fetcher=fetcher,
        store_root=args.store,
        captured_at_utc=captured,
        pause_seconds=args.pause_seconds,
    )
    features = build_historical_feature_panel(sessions=market["sessions"])

    args.output.mkdir(parents=True, exist_ok=True)
    market_bytes = canonical_gzip_json(market)
    feature_bytes = canonical_gzip_json(features)
    market_path = args.output / "market-panel.json.gz"
    feature_path = args.output / "feature-panel.json.gz"
    market_path.write_bytes(market_bytes)
    feature_path.write_bytes(feature_bytes)

    manifest = {
        "schema_version": 1,
        "engine_id": "AE001-v1-DEVELOPMENT",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "market_panel_sha256": market["panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "feature_panel_sha256": features["panel_sha256"],
        "feature_artifact_sha256": sha256_bytes(feature_bytes),
        "session_count": market["session_count"],
        "feature_row_count": features["feature_row_count"],
        "historical_archives_captured_prospectively": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
