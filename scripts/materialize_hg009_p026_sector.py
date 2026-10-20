"""Freeze/replay original Oct16 sector coverage of all 300 HG009 identities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p026_sector_coverage import materialize, validate_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "research/hg009/hg009-p026-postentry-sector-coverage-v1.json"
        ),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = materialize(args.repo_root)
    validate_report(result, args.repo_root)
    output = args.repo_root / args.output
    canonical = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False,
    ) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != canonical:
            raise SystemExit("HG009 P026 original 300-issuer sector packet changed")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and output.read_text(encoding="utf-8") != canonical:
            raise SystemExit("HG009 P026 post-entry industry source cannot be overwritten")
        output.write_text(canonical, encoding="utf-8")
    print(json.dumps({
        "state": "REPRODUCED" if args.check else "MATERIALIZED",
        "source_exact_match_count": result["source_exact_match_count"],
        "source_total": 300,
        "max_complete_industry_triplets": (
            result["sector_triplet_upper_bound_complete_count"]
        ),
        "industry_coverage_gate_passed": (
            result["source_95pct_total_coverage_gate"]
        ),
        "source_is_post_original_entry": (
            result["source_report_session_is_after_original_entry"]
        ),
        "report_sha256": result["report_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
