#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args()


def main() -> None:
    ns = parse_args()
    rows = json.loads(Path(ns.candidates).read_text())
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    summary_presence: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        desc = str(row.get("description") or "").strip() or "<EMPTY>"
        has_summary = bool(str(row.get("attachment_summary") or "").strip())
        for family in row.get("candidate_families") or []:
            by_family[family][desc] += 1
            summary_presence[family]["with_attachment_summary" if has_summary else "without_attachment_summary"] += 1
    report = {
        "candidate_count": len(rows),
        "by_family_top_descriptions": {
            family: counter.most_common(80) for family, counter in sorted(by_family.items())
        },
        "by_family_attachment_summary_presence": {
            family: dict(counter) for family, counter in sorted(summary_presence.items())
        },
    }
    Path(ns.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True)[:120000])


if __name__ == "__main__":
    main()
