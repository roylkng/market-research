"""Freeze outcome-blind feasibility for a future index-industry matched NSE cohort."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p036_independent_pool import (
    build_feasibility,
    validate_feasibility,
)

DEFAULT = Path("research/hg009/hg009-p036-next-cohort-industry-feasibility-v1.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    artifact = build_feasibility(args.repo_root)
    validate_feasibility(args.repo_root, artifact)
    content = json.dumps(
        artifact, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False
    ) + "\n"
    path = args.repo_root / args.output
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit("P036 original sector-matched report changed")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise SystemExit("P036 original feasibility is immutable")
        path.write_text(content, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "SOURCE_POOL_SEALED",
        "original_index_EQ": artifact["original_index_valid_EQ_industry_count"],
        "development_excluded": artifact["original_development_identity_count"],
        "eligible_source_by_arm": artifact["new_eligible_source_rows_by_arm"],
        "max_industry_and_liquidity_matched_triplets": (
            artifact["maximum_industry_liquidity_matched_triplets"]
        ),
        "new_trial_activated": False,
        "sha256": artifact["report_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
