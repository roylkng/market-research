"""Materialize or replay Mayur FY26 original NSE investing-cash reconciliation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p010_mayur_cash import (
    build_mayur_cash_use_bridge,
    validate_mayur_cash_use_bridge,
)

OUTPUT = Path("research/hg009/hg009-p010-mayur-investing-cash-bridge-v1.json")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, default=OUTPUT)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    report = build_mayur_cash_use_bridge(args.repo_root)
    validate_mayur_cash_use_bridge(report, args.repo_root)
    contents = json.dumps(
        report, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False,
    ) + "\n"
    dest = args.repo_root / args.output
    if args.check:
        if not dest.is_file() or dest.read_text("utf-8") != contents:
            raise SystemExit("P010 original NSE FY26 cash evidence changed")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.read_text("utf-8") != contents:
            raise SystemExit("P010 historical cash receipt must not be rewritten")
        dest.write_text(contents, encoding="utf-8")
    print(json.dumps({
        "status": "VERIFIED" if args.check else "ORIGINAL_SOURCE_MATERIALIZED",
        "original_nse_archive_sha256": report["pinned_original_byte_sha256"],
        "report_sha256": report["report_sha256"],
        "financial_rows_verified": report["number_of_source_row_values_matched"],
        "cfo_less_ppe_cr_not_fcf": report["fy26_cfo_less_ppe_cr_not_fcf"],
        "residual_cash_after_selected_asset_uses_cr_not_owner_fcf": report[
            "residual_cfo_less_ppe_less_net_asset_placement_cr_not_owner_fcf"
        ],
        "investor_valuation_ready": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
