"""Seal P016 exact 100-NSE original-source investing cash falsification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p016_owner_cash_gate import (
    build_owner_cash_falsification,
    load_original_p015,
    validate_owner_cash_falsification,
)

DEST = Path("research/l001/l001-p016-owner-cash-evidence-gates-100-v1.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=DEST)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = load_original_p015(args.repo_root)
    report = build_owner_cash_falsification(source)
    validate_owner_cash_falsification(report, original_p015=source)
    output = args.repo_root / args.output
    serial = json.dumps(
        report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != serial:
            raise SystemExit("L001 P016 original-source owner-cash audit changed")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and output.read_text(encoding="utf-8") != serial:
            raise SystemExit("L001 P016 signed audit cannot be overwritten")
        output.write_text(serial, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "report": report["report_id"],
        "source_sha256": report["source_P015_sha256"],
        "original_issuers": report["issuer_count"],
        "flags": report["source_review_gate_counts_overlap"],
        "sustainable_owner_cash_verified": (
            report["issuer_sustainable_owner_cash_estimated_count"]
        ),
        "signature": report["report_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
