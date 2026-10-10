"""Reproduce original management 2x *post-synergy* WWIL EBITDA hurdle.

The dated FY26 revenue and future anticipated EBITDA periods are not
equivalent. No audited EBITDA, company target return or trade.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_wwil_synergy_hurdle import (
    build_wwil_management_hurdle,
    load_original_press,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    raw, receipt, provenance = load_original_press(args.repo_root)
    output = build_wwil_management_hurdle(raw, receipt, provenance)
    data = json.dumps(
        output, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != data:
                raise ValueError("management original source-stress packet drifted")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as handle:
                handle.write(data)
    print(json.dumps({
        "id": output["analysis_id"],
        "original_pdf_sha256": output["source_provenance"]["original_pdf_sha256"],
        "original_page_count": output["original_pdf_page_count"],
        "source_multiple_claim_page": output["issuer_reported_claim_source_pages"][
            "management_2x_post_synergy_multiple"
        ]["page_number"],
        "future_ebitda_hurdle_crore_not_a_historical_observation": (
            output["reverse_implied_future_annual_ebitda_inr_crore_if_quote_basis_comparable"]
        ),
        "cross_period_ebitda_margin_proxy_pct": (
            output["reverse_implied_ebitda_margin_on_older_fy26_turnover_pct"]
        ),
        "historical_normalized_ebitda_verified": False,
        "capital_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
