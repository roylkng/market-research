"""Recompute source-locked SunRisers Leeds 14-month GBP cash accounting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p021_srl_uk import materialize, verify


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output", type=Path,
        default=Path("research/l001/l001-p021-srl-uk-14month-cash-analysis-v1.json"),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    report = materialize(args.repo_root)
    verify(report, args.repo_root)
    out = json.dumps(
        report, sort_keys=True, indent=2,
        ensure_ascii=False, allow_nan=False,
    ) + "\n"
    path = args.repo_root / args.output
    if args.check:
        if not path.is_file() or path.read_text("utf-8") != out:
            raise SystemExit("P021 retained UK subsidiary original table report drifted")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.read_text("utf-8") != out:
            raise SystemExit("P021 may not retroactively overwrite original review")
        path.write_text(out, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "report_sha256": report["report_sha256"],
        "14month_operating_cash_gbp": report["reported_14month_operating_cfo_gbp"],
        "cash_to_purchase_percent_not_roic": report[
            "reported_mixed_period_cfo_to_deal_price_pct_not_roic"
        ],
        "fully_audited_parent_owner_cash": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
