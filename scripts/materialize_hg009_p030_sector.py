"""Rebuild source-first 300-company industry classification/provenance queue.

Source readiness is BLOCKED until an independently verified full-population
preentry mapping exists. Never attribute post-Oct15 industry mapping to H1.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p030_sector_queue import (
    materialize_sector_audit,
    validate_sector_audit,
)

DEFAULT = Path("research/hg009/hg009-p030-sector-proof-queue-v1.json")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, default=DEFAULT)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    packet = materialize_sector_audit(args.repo_root)
    validate_sector_audit(packet, args.repo_root)
    raw = json.dumps(
        packet, sort_keys=True, indent=2,
        ensure_ascii=False, allow_nan=False,
    ) + "\n"
    path = args.repo_root / args.output
    if args.check:
        if not path.is_file() or path.read_text(encoding="utf-8") != raw:
            raise SystemExit("P030 pinned 300-company source queue differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") != raw:
            raise SystemExit("P030 source queue must not silently be overwritten")
        path.write_text(raw, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED_SOURCE_BLOCKER",
        "original": packet["original_company_count"],
        "provisional_index_matches": packet[
            "original_postentry_index_subset_exact_match_count"
        ],
        "unclassified": packet["unclassified_in_index_subset_count"],
        "provenanced_before_original_entry": packet[
            "source_independently_verified_before_legacy_entry_count"
        ],
        "next_independent_cohort_is_live": packet[
            "new_independent_cohort_registered"
        ],
        "raw_signed_sha256": packet["report_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
