"""Materialize PIX two-quarter independently replayed income-quality bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p011_pix_income import (
    build_pix_symmetric_income_bridge,
    verify_pix_symmetric_income_bridge,
)

OUTPUT = Path("research/hg009/hg009-p011-pix-symmetric-quarter-profit-v1.json")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, default=OUTPUT)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    report = build_pix_symmetric_income_bridge(args.repo_root)
    verify_pix_symmetric_income_bridge(report, args.repo_root)
    blob = json.dumps(
        report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False,
    ) + "\n"
    target = args.repo_root / args.output
    if args.check:
        if not target.is_file() or target.read_text("utf-8") != blob:
            raise SystemExit("P011 original PIX source bridge changed")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text("utf-8") != blob:
            raise SystemExit("P011 cannot overwrite existing source-traced research")
        target.write_text(blob, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "ORIGINAL_NSE_STATEMENTS_SEALED",
        "source_periods": list(report["original_source_receipts"]),
        "packet_sha256": report["packet_sha256"],
        "symmetric_ex_other_income_growth_pct": report[
            "symmetric_pbt_excluding_all_other_income_yoy_pct"
        ],
        "expected_stock_return": None,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
