"""Materialize or verify HG009 H5 posthoc missingness sharp bounds.

The original P006 result is source-hash pinned and is never overwritten.
This report cannot estimate economic total returns or investable alpha.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p038_h5_missingness import (
    materialize_hg009_h5_missingness,
    verify_hg009_h5_missingness,
)

OUTPUT = Path("research/hg009/hg009-p038-h5-missingness-bounds-v1.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = materialize_hg009_h5_missingness(args.repo_root)
    verify_hg009_h5_missingness(payload, repo_root=args.repo_root)
    encoded = json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    target = args.repo_root / args.out
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != encoded:
            raise SystemExit("P038 H5 immutable source study does not match")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text(encoding="utf-8") != encoded:
            raise SystemExit("P038 H5 original outcome audit cannot overwrite prior evidence")
        target.write_text(encoded, encoding="utf-8")

    print(json.dumps({
        "audit_id": payload["audit_id"],
        "sha256": payload["report_sha256"],
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "selected_observed": payload["arm_data"]["SELECTED"]["source_priced_company_count"],
        "one_lane_observed": payload["arm_data"]["ONE_LANE"]["source_priced_company_count"],
        "zero_lane_observed": payload["arm_data"]["ZERO_LANE"]["source_priced_company_count"],
        "selected_minus_zero_upper_under_arbitrary_20pct_stress": payload[
            "comparison_bounds"
        ]["SELECTED_MINUS_ZERO_LANE"][
            "upper_gap_if_each_unknown_between_minus20_plus20_pp"
        ],
        "expected_equity_returns_calculated": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
