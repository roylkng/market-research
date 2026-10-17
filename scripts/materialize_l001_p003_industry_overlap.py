"""Reproduce the official-source HG009 classification overlap diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p003_industry_overlap import build_provisional_industry_crosswalk

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "research/hg009/hg009-d001-100-experimental-companies-v1.json"
CSV = ROOT / (
    "research/prospective/rm001-sc002/raw/2026-10-16/"
    "nifty-total-market-692caee1b8e4fd11912c71e1c2519c4070e9675f9a0a9e6d40294cdf032890fc.csv"
)
READINESS = ROOT / "research/l001/p003-rm001-sc002-readiness-pinned-20261017.json"
OUTPUT = ROOT / "research/l001/p003-hg009-100-nse-industry-overlap-20261017.json"


def materialize() -> str:
    report = build_provisional_industry_crosswalk(
        json.loads(COHORT.read_text(encoding="utf-8")),
        CSV.read_bytes(),
        json.loads(READINESS.read_text(encoding="utf-8")),
    )
    report.pop("report_sha256")
    return json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = materialize()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != result:
            raise SystemExit("L001 P003 official-source overlap manifest drift")
        print("L001 P003 exact-source 100-company overlap verified")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
