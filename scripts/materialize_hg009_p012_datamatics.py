"""Materialize or verify an archived FY26 Datamatics original-NSE cash bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p012_datamatics_cash import (
    build_datamatics_original_cash_bridge,
    validate_datamatics_original_cash_bridge,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p012-datamatics-fy26-cash-bridge-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build_datamatics_original_cash_bridge(args.repo_root)
    validate_datamatics_original_cash_bridge(result, root=args.repo_root)
    content = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False,
    ) + "\n"
    output = args.repo_root / args.output
    if args.check:
        if not output.is_file() or output.read_text("utf-8") != content:
            raise SystemExit("P012 audited original cashflow output differs")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and output.read_text("utf-8") != content:
            raise SystemExit("P012 previously sealed original audit cannot change")
        output.write_text(content, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "SOURCE_REPLAYED_AND_SEALED",
        "issuer": result["symbol"],
        "original_pdf_sha256": result["original_raw_sha256"],
        "original_pdf_cash_rows": len(
            result["exact_original_pdf_cashflow_row_labels_and_values_replayed"]
        ),
        "fy26_cfo_after_all_investing_cr": result[
            "fy26_cfo_after_all_investing_cr_not_owner_fcf"
        ],
        "fy26_annual_cash_change_cr": result["fy26_annual_cash_change_cr"],
        "report_sha256": result["report_sha256"],
        "portfolio_eligibility_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
