from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha_acquisition import acquire_historical_market_panel, http_fetcher
from marketlab.h021_capture import verify_capture_bundle
from marketlab.research_radar import (
    build_research_priority_radar,
    render_radar_markdown,
)


def _json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _count_records(payload: dict) -> int:
    for key in ("records", "events"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return len(rows)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build frozen RR001 100-name research-priority radar"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--batch-spec", type=Path, required=True)
    parser.add_argument("--consensus-payload", type=Path, required=True)
    parser.add_argument("--consensus-manifest", type=Path, required=True)
    parser.add_argument("--h022", type=Path, required=True)
    parser.add_argument("--h023", type=Path, required=True)
    parser.add_argument("--h024-summary", type=Path, required=True)
    parser.add_argument("--market-start", type=date.fromisoformat, required=True)
    parser.add_argument("--market-end", type=date.fromisoformat, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    universe = _json(args.universe)
    batch_spec = _json(args.batch_spec)
    manifest = _json(args.consensus_manifest)
    payload_bytes = args.consensus_payload.read_bytes()
    snapshot = verify_capture_bundle(
        payload_bytes,
        manifest,
        universe,
        batch_spec,
    )
    h022 = _json(args.h022)
    h023 = _json(args.h023)
    h024 = _json(args.h024_summary)

    market = acquire_historical_market_panel(
        start_date=args.market_start,
        end_date=args.market_end,
        fetcher=http_fetcher(
            attempts=args.attempts,
            timeout=args.timeout_seconds,
        ),
        store_root=args.store,
        captured_at_utc=datetime.now(UTC),
        pause_seconds=0.02,
    )
    if market["sessions"][-1]["session_date"] != args.market_end.isoformat():
        raise RuntimeError(
            "RR001 frozen market-end date is not the latest acquired NSE session"
        )

    radar = build_research_priority_radar(
        universe=universe,
        consensus_snapshot=snapshot,
        market_panel=market,
        consensus_payload_sha256=manifest["payload_uncompressed_sha256"],
        h022_signal_ledger=h022,
        h023_event_count=_count_records(h023),
        h024_primary_event_count=int(
            h024.get("current_primary_event_count") or 0
        ),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(
            radar,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    args.output_md.write_text(
        render_radar_markdown(radar),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "radar_sha256": radar["radar_sha256"],
                "as_of_market_session": radar["as_of_market_session"],
                "short": [row["symbol"] for row in radar["shortlists"]["short"]],
                "mid": [row["symbol"] for row in radar["shortlists"]["mid"]],
                "long": [row["symbol"] for row in radar["shortlists"]["long"]],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
