"""Generate or independently verify frozen H1 source-missingness sharp bounds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p037_missingness import (
    materialize_hg009_h1_missingness,
    verify_hg009_h1_missingness,
)

DEFAULT = Path("research/hg009/hg009-p037-h1-missingness-bounds-v1.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = materialize_hg009_h1_missingness(args.repo_root)
    verify_hg009_h1_missingness(report, root=args.repo_root)
    data = (
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    )
    path = args.repo_root / args.output
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != data:
            raise SystemExit("P037 signed H1 sensitivity evidence differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") != data:
            raise SystemExit("P037 immutable posthoc evidence cannot be overwritten")
        path.write_text(data, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "review_id": report["review_id"],
        "sha256": report["report_sha256"],
        "selected_missing": report["arm_source_missingness_sensitivity"][
            "SELECTED"
        ]["missing_source_count"],
        "one_lane_missing": report["arm_source_missingness_sensitivity"][
            "ONE_LANE"
        ]["missing_source_count"],
        "zero_lane_missing": report["arm_source_missingness_sensitivity"][
            "ZERO_LANE"
        ]["missing_source_count"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
