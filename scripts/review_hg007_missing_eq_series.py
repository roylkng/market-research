"""Audit absent NSE EQ rows for ORBTEXP and RETAIL across source series.

Does not infer suspensions, delistings, zero turnover, name changes, or
liquidity from unrelated cash-market series. All original source bytes
are already permanently retained in HG007-P036.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_eq_absence_review import (
    build_missing_eq_series_review,
    validate_missing_eq_series_review,
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path)
    p.add_argument("--verify-existing", action="store_true")
    args = p.parse_args()
    if args.verify_existing and args.out is None:
        p.error("--verify-existing requires --out")
    report = build_missing_eq_series_review(args.repo_root)
    validate_missing_eq_series_review(report)
    serialized = json.dumps(
        report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != serialized:
                raise ValueError("original source non-EQ series gap review changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as result:
                result.write(serialized)
    print(json.dumps({
        "audit_id": report["audit_id"],
        "original_hg002_company_count": report["original_hg002_company_count_preserved"],
        "original_missing_eq_session_count": report["original_eq_missing_observations"],
        "per_company_exchange_row_statuses": {
            case["symbol"]: case["source_classification_counts"]
            for case in report["findings"]
        },
        "missing_eq_days_treated_as_zero_turnover": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
