from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from marketlab.alpha_corporate_actions import (
    acquire_corporate_action_ledger,
    filter_feature_panel_for_corporate_actions,
)
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.nse import NSEClient


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
        description="Build AE001 corporate-action ledger and action-safe feature panel"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chunk-days", type=int, default=31)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    feature_bytes = args.feature_panel.read_bytes()
    market = load_canonical_gzip_json(market_bytes)
    features = load_canonical_gzip_json(feature_bytes)

    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )

    def fetcher(from_date: str, to_date: str):
        payload, raw = client.corporate_actions_with_raw(
            None,
            from_date=from_date,
            to_date=to_date,
        )
        query = urlencode(
            {
                "index": "equities",
                "from_date": from_date,
                "to_date": to_date,
            }
        )
        source_url = f"{client.CORPORATE_ACTION_ENDPOINT.url}?{query}"
        return payload, raw, source_url

    ledger = acquire_corporate_action_ledger(
        start_date=args.start_date,
        end_date=args.end_date,
        fetcher=fetcher,
        raw_dir=args.raw_dir,
        chunk_days=args.chunk_days,
    )
    safe = filter_feature_panel_for_corporate_actions(
        feature_panel=features,
        market_panel=market,
        action_ledger=ledger,
        lookback_sessions=60,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    ledger_bytes = canonical_gzip_json(ledger)
    safe_bytes = canonical_gzip_json(safe)
    (args.output / "corporate-action-ledger.json.gz").write_bytes(ledger_bytes)
    (args.output / "action-safe-feature-panel.json.gz").write_bytes(safe_bytes)

    manifest = {
        "schema_version": 1,
        "engine_id": "AE001-v1-DEVELOPMENT",
        "input_market_artifact_sha256": sha256_bytes(market_bytes),
        "input_feature_artifact_sha256": sha256_bytes(feature_bytes),
        "corporate_action_ledger_sha256": ledger["ledger_sha256"],
        "corporate_action_artifact_sha256": sha256_bytes(ledger_bytes),
        "action_safe_feature_panel_sha256": safe["panel_sha256"],
        "action_safe_feature_artifact_sha256": sha256_bytes(safe_bytes),
        "share_changing_symbol_count": ledger["record_count"],
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
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
