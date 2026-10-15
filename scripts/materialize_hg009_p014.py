"""Freeze or replay the original-source ten-company economic challenge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p014_economics import materialize, validate_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "research/hg009/hg009-p014-economic-symmetry-and-cash-v1.json"
        )
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = materialize(args.repo_root)
    validate_review(value, args.repo_root)
    payload = json.dumps(
        value, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False
    ) + "\n"
    path = args.repo_root / args.output
    if args.check:
        if not path.is_file() or path.read_text("utf-8") != payload:
            raise SystemExit("P014 signed original economic review differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text("utf-8") != payload:
            raise SystemExit("P014 cannot overwrite immutable prior review")
        path.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "case_count": value["case_count"],
        "source_lanes": value["diligence_source_lanes_not_expected_return_rankings"],
        "report_sha256": value["report_sha256"],
        "investable": value["investment_value_ready_count"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
