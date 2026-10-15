"""Seal the P013 original FY26 cash-investing-financing flow bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p013_cash_bridge import (
    build_original_fy26_cash_use,
    verify_original_fy26_cash_use,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p013-fy26-cash-use-bridge-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build_original_fy26_cash_use(args.repo_root)
    verify_original_fy26_cash_use(data, root=args.repo_root)
    output = args.repo_root / args.output
    serialized = (
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != serialized:
            raise SystemExit("P013 original signed cash-source report missing or changed")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and output.read_text(encoding="utf-8") != serialized:
            raise SystemExit("P013 immutable original source report collision")
        output.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "research_id": data["research_id"],
        "state": "REPLAY_VERIFIED" if args.check else "ORIGINAL_CASH_SOURCES_SEALED",
        "issuers": data["archived_full_original_fy26_cashflow_source_count"],
        "source_cells": data["individually_row_replayed_source_cash_fields"],
        "cash_reconciled": data["all_three_cashflow_open_close_arithmetics_reconcile"],
        "valuation_complete": data["owner_cashflow_models_validated_count"],
        "sha256": data["report_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
