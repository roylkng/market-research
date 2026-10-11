"""Reconcile 5-company research with original Sambhv conditional cash and Q2 tonnes.

All source Git blobs fixed. Output is evidence *readiness*, no investment
ranking or probability-weighted expected returns.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_sambhv_update import build_latest_underwriting, load_pinned_latest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    originals, receipts = load_pinned_latest(args.repo_root)
    report = build_latest_underwriting(originals, receipts)
    encoded = json.dumps(
        report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("Sambhv five-case evidence overlay altered")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as dst:
                dst.write(encoded)
    print(json.dumps({
        "overlay_id": report["overlay_id"],
        "original_case_count": report["original_five_case_count"],
        "new_source_case_count": report["source_case_count_with_new_sambhv_data"],
        "warrant_cash_received_proven": report[
            "latest_sambhv_warrant_cash_received_independently_verified"
        ],
        "new_plant_ebitda_proven": report[
            "latest_sambhv_q2_incremental_ebitda_verified"
        ],
        "case_expected_returns_published": report[
            "source_probabilities_or_expected_returns_published"
        ],
        "live_capital_allowed": report["live_capital_allowed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
