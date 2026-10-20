"""Freeze four issuer-specific falsification hurdles from signed original sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p023_frontier import (
    materialize_falsification_frontier,
    validate_falsification_frontier,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output",
        type=Path,
        default=Path("research/l001/l001-p023-value-falsification-frontier-v1.json"),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    report = materialize_falsification_frontier(args.repo_root)
    validate_falsification_frontier(report, args.repo_root)
    source = (
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    path = args.repo_root / args.output
    if args.check:
        if not path.is_file() or path.read_text(encoding="utf-8") != source:
            raise SystemExit("L001 P023 signed original report differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") != source:
            raise SystemExit("L001 P023 original review is immutable")
        path.write_text(source, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "review_id": report["review_id"],
        "four_competing_theses": report["issuer_hypotheses_reviewed"],
        "source_sha256": report["report_sha256"],
        "investable_cases_approved": report[
            "investable_portfolio_candidates_approved"
        ],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
