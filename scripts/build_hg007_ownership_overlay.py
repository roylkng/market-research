"""Generate 28-company source-verified dilution and pledge diligence view.

No network calls, no changed 28-company selection and no stock targets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_ownership_overlay import (
    build_ownership_case_overlay,
    load_exact_case_sources,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    previous, reg31, receipts = load_exact_case_sources(args.repo_root)
    result = build_ownership_case_overlay(previous, reg31, receipts)
    encoded = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("original NSE 28-company governance diligence view changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as fp:
                fp.write(encoded)

    print(json.dumps({
        "casebook_id": result["casebook_id"],
        "original_28_preserved": result["original_hg007_28_member_count"],
        "official_original_sep29_reg31_reviewed": result["source_verified_new_dilution_pledge_cases"],
        "other_cases_not_reassessed": result["unreviewed_company_count"],
        "new_stock_predictions": result["stock_level_alpha_trials_claimed"],
        "live_capital_allowed": result["live_capital_allowed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
