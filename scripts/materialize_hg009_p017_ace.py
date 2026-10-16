"""Reproduce ACE FY25/FY26 cash timing effects only from original issuer bytes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p017_ace_cash import (
    FIRST_RECEIPT,
    build_ace_fy25_fy26_cash_audit,
    verify_ace_fy25_fy26_cash_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p017-ace-two-year-cash-bridge-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.repo_root
    if not (root / FIRST_RECEIPT).is_file():
        print(json.dumps({
            "state": "AWAITING_ORIGINAL_NSE_FY25_RAW_SOURCE",
            "changed": False,
            "investment_recommendation_generated": False,
        }, sort_keys=True))
        return 0
    result = build_ace_fy25_fy26_cash_audit(root)
    verify_ace_fy25_fy26_cash_audit(result, root)
    output = (
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
    dest = root / args.output
    if args.check:
        if not dest.is_file() or dest.read_text(encoding="utf-8") != output:
            raise SystemExit("P017 original ACE FY25/FY26 owner-cash diagnostics changed")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.read_text(encoding="utf-8") != output:
            raise SystemExit("P017 cannot overwrite a source-frozen cash bridge")
        dest.write_text(output, encoding="utf-8")
    print(json.dumps({
        "state": "REPLAY_VERIFIED" if args.check else "ORIGINAL_SOURCE_SEALED",
        "symbol": "ACE",
        "FY25_CFO_cr": result["fy25_CFO_cr"],
        "FY26_CFO_cr": result["fy26_CFO_cr"],
        "PPE_decline_component_cr": result["PPE_spend_reduction_component_cr"],
        "CFO_improvement_component_cr": result["CFO_change_component_cr"],
        "report_sha256": result["report_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
