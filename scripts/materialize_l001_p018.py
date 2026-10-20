"""Audit Zuari's five June holding marks on same-day Oct19 original NSE data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p018_zuari_fullmarket import (
    materialize_l001_p018,
    validate_l001_p018,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output", type=Path,
        default=Path("research/l001/l001-p018-oct19-five-stake-source-repricing-v1.json"),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    output = materialize_l001_p018(args.repo_root)
    validate_l001_p018(output, root=args.repo_root)
    data = json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path = args.repo_root / args.output
    if args.check:
        if not path.is_file() or path.read_text("utf-8") != data:
            raise SystemExit("P018 original source-repricing result does not match")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text("utf-8") != data:
            raise SystemExit("P018 immutable full-market NSE repricing cannot be overwritten")
        path.write_text(data, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "SEALED_LOCALLY",
        "id": output["research_id"],
        "sha256": output["report_sha256"],
        "source_historical_dates": ["2026-10-15", "2026-10-19"],
        "oct19_five_stake_mark_cr": output["stake_marks_by_date_cr"]["2026-10-19"],
        "oct19_hypothetical_additional_haircut": output[
            "Oct19_further_markdown_erasing_apparent_gap_fraction"
        ],
        "true_owner_equity_fair_value_verified": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
