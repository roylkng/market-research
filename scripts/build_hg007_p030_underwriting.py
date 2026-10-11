"""Rebuild five HG005 company evidence gates from 11 original SHA-pinned sources.

No remote data fetch, return re-ranking, equity target or capital permission.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_p030_underwriting_readiness import (
    build_p030_case_readiness,
    load_pinned_underwriting_sources,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    sources, receipts = load_pinned_underwriting_sources(args.repo_root)
    packet = build_p030_case_readiness(sources, receipts)
    encoded = json.dumps(
        packet, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("original-source five-company readiness drifted")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
    print(json.dumps({
        "readiness_id": packet["readiness_id"],
        "original_five": [case["symbol"] for case in packet["casework"]],
        "source_family_count": len(packet["evidence_source_git_blob_receipts"]),
        "approved_equity_upside_cases": packet["economically_validated_50pct_upside_cases"],
        "valuation_ready_count": packet["separate_valuation_or_return_ready_company_count"],
        "current_fully_diluted_asof_oct11_verified_count": (
            5 - packet["unverified_current_oct11_fully_diluted_company_count"]
        ),
        "investment_recommendations_authorized": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
