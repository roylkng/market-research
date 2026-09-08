#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--signals", required=True)
    p.add_argument("--recalled", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args()


def main() -> None:
    ns = args()
    signals = json.loads(Path(ns.signals).read_text())
    recalled = json.loads(Path(ns.recalled).read_text())
    by_family = defaultdict(list)
    for row in signals:
        for family in row.get("retained_families") or []:
            by_family[family].append(row)
    recalled_by_family = defaultdict(set)
    for item in recalled:
        episode = item["episode"]
        signal = item["signal"]
        episode_id = (episode["symbol"], episode["start_date"], episode["hit_date"])
        for family in signal.get("retained_families") or []:
            recalled_by_family[family].add(episode_id)

    report = {
        "status": "POST_HOC_DIAGNOSTIC_NOT_FOR_H004_RETUNING",
        "family_metrics": {},
    }
    for family, rows in sorted(by_family.items()):
        hits = [row for row in rows if row["explosive_20d"]]
        lead = [row["lead_sessions_to_25pct"] for row in hits if row.get("lead_sessions_to_25pct") is not None]
        report["family_metrics"][family] = {
            "signal_count": len(rows),
            "hit_count": len(hits),
            "precision": len(hits) / len(rows) if rows else None,
            "recalled_episode_count": len(recalled_by_family.get(family, set())),
            "median_hit_lead_sessions": statistics.median(lead) if lead else None,
            "median_max_20d_return_pct": statistics.median(row["max_20d_return_pct"] for row in rows) if rows else None,
            "median_close_20d_return_pct": statistics.median(row["close_20d_return_pct"] for row in rows) if rows else None,
        }
    Path(ns.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
