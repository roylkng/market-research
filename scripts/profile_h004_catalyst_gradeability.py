#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args()


def flags(text: str) -> dict[str, bool]:
    low = text.casefold()
    return {
        "has_digit": bool(re.search(r"\d", text)),
        "has_currency": any(x in low for x in ("₹", "rs.", "rs ", "inr", "crore", "lakh", "million", "billion", "usd", "eur", "$")),
        "has_capacity_unit": any(x in low for x in ("mw", "gw", "mtpa", "tpa", "tonne", "tons", "units per", "capacity")),
        "has_percent": "%" in text or "percent" in low,
        "has_control_language": any(x in low for x in ("100%", "controlling stake", "control", "entire share", "entire business", "wholly owned", "majority stake")),
        "has_first_commercial": any(x in low for x in ("first commercial", "commencement of commercial", "commercial production", "commercial operation")),
    }


def main() -> None:
    ns = args()
    rows = json.loads(Path(ns.input).read_text())
    by_family = defaultdict(Counter)
    desc = defaultdict(Counter)
    for row in rows:
        text = str(row.get("attachment_summary") or "")
        f = flags(text)
        for family in row.get("retained_families") or []:
            desc[family][str(row.get("description") or "")] += 1
            for key, value in f.items():
                by_family[family][key] += int(value)
            by_family[family]["total"] += 1
    report = {
        "candidate_count": len(rows),
        "materiality_evidence_flags": {family: dict(counter) for family, counter in sorted(by_family.items())},
        "top_descriptions": {family: counter.most_common(30) for family, counter in sorted(desc.items())},
    }
    Path(ns.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
