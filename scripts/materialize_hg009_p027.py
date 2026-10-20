"""Materialize honest HG009 falsification and next-independent-cohort gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p027_gate import materialize, verify_packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p027-h1-no-alpha-next-cohort-gate-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = materialize(args.repo_root)
    verify_packet(report, args.repo_root)
    output_path = args.repo_root / args.output
    serialized = json.dumps(
        report, indent=2, sort_keys=True, ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    if args.check:
        if (
            not output_path.is_file()
            or output_path.read_text(encoding="utf-8") != serialized
        ):
            raise SystemExit("P027 original immutable study report differs")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if (
            output_path.exists()
            and output_path.read_text(encoding="utf-8") != serialized
        ):
            raise SystemExit("P027 existing sealed review cannot be replaced")
        output_path.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "FROZEN",
        "audit_sha256": report["report_sha256"],
        "original_h1_date": report["H1_original_market_event"],
        "H1_lagged_both_controls": report["H1_selected_lags_both_source_controls"],
        "industry_coverage_fraction": (
            report["original_2026_10_16_index_subset_coverage_fraction"]
        ),
        "independently_investable_equity_valuations": (
            report["issuer_original_ten_three_scenario_attributable_valuations_complete"]
        ),
        "future_matched_cohort_activated": (
            report["next_experiment_protocol"]["next_experiment_active"]
        ),
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
