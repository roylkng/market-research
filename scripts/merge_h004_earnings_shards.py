#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import run_h004_earnings_replay_v2 as replay


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--shards-root", required=True)
    p.add_argument("--out-dir", required=True)
    return p.parse_args()


def read_json(path: Path):
    return json.loads(path.read_text())


def main() -> None:
    ns = args()
    root = Path(ns.shards_root)
    out = Path(ns.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    shard_dirs = sorted(path.parent for path in root.rglob("summary.json"))
    if len(shard_dirs) != 4:
        raise SystemExit(f"expected 4 shard summaries, found {len(shard_dirs)}: {shard_dirs}")

    primary = []
    discovery = []
    coverage = Counter()
    shard_summaries = []
    for shard in shard_dirs:
        summary = read_json(shard / "summary.json")
        shard_summaries.append(summary)
        primary.extend(read_json(shard / "events.json"))
        discovery.extend(read_json(shard / "discovery-events.json"))
        coverage.update(summary.get("coverage") or {})

    identities = set()
    for row in primary + discovery:
        key = (row.get("symbol"), row.get("quarter_end"), row.get("basis"), row.get("broadcast"))
        if key in identities:
            raise SystemExit(f"duplicate event across shards: {key}")
        identities.add(key)

    primary.sort(key=lambda row: (row["decision_date"], row["symbol"], row.get("broadcast") or ""))
    discovery.sort(key=lambda row: (row["decision_date"], row["symbol"], row.get("broadcast") or ""))
    summary = replay.summarize_v2(primary, dict(sorted(coverage.items())))
    summary["event_window"] = {"start": "2025-10-01", "end": "2026-07-31"}
    summary["price_window_union"] = {"start": "2025-06-01", "end": "2026-08-31"}
    summary["sharded_execution"] = {
        "shard_count": 4,
        "shard_event_windows": [s.get("event_window") for s in shard_summaries],
        "primary_rows_merged": len(primary),
        "discovery_rows_merged": len(discovery),
        "model_thresholds_changed": False,
    }
    summary["data_contract"] = {
        "current_financials": "original NSE Integrated Filing Financials XBRL",
        "prior_financials": "same-basis same-quarter original NSE legacy/integrated XBRL",
        "market_data": "official NSE UDiFF daily bhavcopy",
        "xbrl_units": "actual INR",
        "operating_ebitda_proxy": "PBT before exceptional/tax - other income + finance cost + depreciation",
    }

    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "events.json").write_text(json.dumps(primary, indent=2, sort_keys=True) + "\n")
    (out / "discovery-events.json").write_text(json.dumps(discovery, indent=2, sort_keys=True) + "\n")
    (out / "shard-summaries.json").write_text(json.dumps(shard_summaries, indent=2, sort_keys=True) + "\n")
    (out / "RESULTS.md").write_text(
        "# H004-HR002 sharded earnings replay\n\n"
        "Status: **historical reconstruction, not out-of-sample validation**\n\n"
        "Four calendar shards ran the same frozen H004 earnings implementation independently and were merged by immutable event identity. No thresholds were changed between shards.\n\n"
        "```json\n" + json.dumps(summary, indent=2, sort_keys=True) + "\n```\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
