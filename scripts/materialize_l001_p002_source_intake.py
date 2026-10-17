"""Reproduce the HG009 all-100 source-readiness manifest without touching source ledgers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p002_intake import build_source_intake

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "research/hg009/hg009-d001-100-experimental-companies-v1.json"
P014 = ROOT / "research/hg009/hg009-p014-economic-symmetry-and-cash-v1.json"
OUTPUT = ROOT / "research/l001/p002-hg009-100-source-readiness-20261017.json"
CUTOFF = "2026-10-17T12:00:00Z"


def materialize() -> str:
    cohort = json.loads(COHORT.read_text(encoding="utf-8"))
    prior = json.loads(P014.read_text(encoding="utf-8"))
    report = build_source_intake(cohort, prior, research_cutoff_utc=CUTOFF)
    # The generated JSON is compared byte-for-byte in CI. Its original-source
    # pins are sealed, while Git itself supplies the resulting file blob SHA.
    # Full reported hash is available from build_source_intake for callers.
    report.pop("report_sha256")
    return json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    body = materialize()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != body:
            raise SystemExit("L001 P002 source-readiness manifest drift")
        print("L001 P002 all-100 source-readiness manifest verified")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
