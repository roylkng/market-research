"""Seal a source-pinned Sun TV FY26 franchise-rights cash bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p019_suntv_rights import (
    build_suntv_2026_cash_reconciliation,
    load_prior_evidence,
    validate_suntv_reconciliation,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output", type=Path,
        default=Path(
            "research/l001/l001-p019-suntv-franchise-rights-cash-bridge-v1.json"
        )
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    original, receipts = load_prior_evidence(args.repo_root)
    report = build_suntv_2026_cash_reconciliation(original, receipts)
    validate_suntv_reconciliation(report, root=args.repo_root)
    serialized = json.dumps(
        report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    target = args.repo_root / args.output
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != serialized:
            raise SystemExit("P019 frozen source cash accounting report drifted")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.read_text(encoding="utf-8") != serialized:
            raise SystemExit("P019 original accounting audit cannot be overwritten")
        target.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "original_date": report["original_report_period_end"],
        "source_symbol": report["symbol"],
        "bridge_sha256": report["report_sha256"],
        "conditional_owner_cash_not_verified": (
            report["conditional_2026_cash_proxy_not_proven_sustainable"]
        ),
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
