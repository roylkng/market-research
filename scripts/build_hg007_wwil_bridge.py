"""Materialize the October 7 WWIL reported funding bridge, source review pending.

No live NSE data, equity returns, forecast EBITDA, capital recommendation,
or assertion of legally completed transfer is produced.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_wwil_bridge import (
    PROVISIONAL_TERMS,
    build_conditional_funding_bridge,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    case = build_conditional_funding_bridge(
        PROVISIONAL_TERMS,
        evidence_state="SECONDARY_TRANSCRIPTION_AWAITING_ORIGINAL_PDF",
        transfer_conditions_precedent_satisfied=False,
        original_pdf_reviewed=False,
    )
    serialized = json.dumps(
        case, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is None:
        print(serialized, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
        print(json.dumps({
            "id": case["bridge_id"],
            "gross_purchase_crore": case["gross_purchase_consideration_inr_crore"],
            "inox_reported_funding_crore": case["inox_green_total_reported_funding_inr_crore"],
            "outside_reported_funding_crore": case["authum_external_reported_funding_inr_crore"],
            "original_source_reviewed": case["original_bse_pdf_audited_verified"],
            "expected_return_calculated": case["acquisition_expected_return_calculated"],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
