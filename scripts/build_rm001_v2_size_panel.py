from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_size_panel import build_rm001_v2_size_panel


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
        description="Build RM001-v2 historical total-market-cap size panel"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    market = load_canonical_gzip_json(market_bytes)
    captured = datetime.now(UTC)
    panel = build_rm001_v2_size_panel(
        market_panel=market,
        fetcher=http_fetcher(
            attempts=args.attempts,
            timeout=args.timeout_seconds,
        ),
        store_root=args.store,
        captured_at_utc=captured,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    panel_bytes = canonical_gzip_json(panel)
    (args.output / "size-panel.json.gz").write_bytes(panel_bytes)
    manifest = {
        "schema_version": 1,
        "artifact_id": "RM001-v2-SIZE-PANEL-v1",
        "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
        "market_panel_sha256": market["panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "d007_result_sha256": panel["d007_result_sha256"],
        "size_panel_sha256": panel["panel_sha256"],
        "size_panel_artifact_sha256": sha256_bytes(panel_bytes),
        "session_count": panel["session_count"],
        "row_count": panel["row_count"],
        "minimum_exact_join_coverage": panel[
            "minimum_exact_join_coverage"
        ],
        "prospective_source_timing_verified": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
