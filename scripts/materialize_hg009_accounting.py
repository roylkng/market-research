"""Seal deterministic October-14 HG009 accounting diligence, not stock returns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_100 import load_hg001_router
from marketlab.hg009_p003_accounting import (
    COHORT,
    SOURCE,
    build_hg009_accounting_review,
    validate_hg009_accounting_review,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p003-accounting-quality-redteam-v1.json"),
    )
    p.add_argument("--check", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    original = load_hg001_router(args.repo_root / SOURCE)
    selected = json.loads(
        (args.repo_root / COHORT).read_text(encoding="utf-8")
    )
    report = build_hg009_accounting_review(router=original, cohort=selected)
    validate_hg009_accounting_review(
        report, router=original, cohort=selected,
    )
    payload = (
        json.dumps(
            report, indent=2, sort_keys=True,
            ensure_ascii=False, allow_nan=False,
        ) + "\n"
    )
    destination = args.repo_root / args.output
    if args.check:
        if (
            not destination.is_file()
            or destination.read_text(encoding="utf-8") != payload
        ):
            raise SystemExit("HG009 P003 immutable accounting review differs")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if (
            destination.exists()
            and destination.read_text(encoding="utf-8") != payload
        ):
            raise SystemExit("HG009 P003 original research review cannot be overwritten")
        destination.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "review_id": report["review_id"],
        "selected": report["selected_case_count"],
        "flag_count": report["screen_flags_count"],
        "manual_filing_case_count": report["cashflow_primary_source_manual_pilot_case_count"],
        "packet_sha256": report["packet_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
