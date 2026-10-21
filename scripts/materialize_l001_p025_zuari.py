"""Freeze and verify Zuari's mixed-date debt/stake falsification, no trading."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p025_zuari_falsification import (
    materialize_zuari_falsification,
    validate_zuari_falsification,
)

REPORT = Path("research/l001/l001-p025-zuari-q1-debt-stake-falsification-v1.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = materialize_zuari_falsification(args.repo_root)
    validate_zuari_falsification(report, root=args.repo_root)
    target = args.repo_root / args.output
    body = json.dumps(
        report, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False
    ) + "\n"
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != body:
            raise SystemExit("L001 P025 original Zuari research packet differs")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text(encoding="utf-8") != body:
            raise SystemExit("L001 P025 signed source report cannot be overwritten")
        target.write_text(body, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "SIGNED_SOURCE_RESEARCH_ONLY",
        "symbol": "ZUARIIND",
        "historical_gap_cr": report[
            "hypothetical_stale_balance_sheet_stake_gap_cr_not_attributable"
        ],
        "markdown_hurdle_pct": report[
            "additional_stake_markdown_erasing_stale_gap_percent_not_probability"
        ],
        "segment_to_finance_coverage": report[
            "Q1_segment_ebitda_divided_by_finance_cost"
        ],
        "original_packet_sha256": report["report_sha256"],
        "capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
