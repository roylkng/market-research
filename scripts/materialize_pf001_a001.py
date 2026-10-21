"""Reconstruct PF001 cash-versus-stock skill from immutable October 19 sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.pf001_a001_skill_guard import (
    materialize_pf001_a001,
    validate_pf001_a001,
)

DEFAULT = Path(
    "research/paper-funds/PF001/audits/pf001-a001-stock-selection-skill-v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = materialize_pf001_a001(args.repo_root)
    validate_pf001_a001(report, args.repo_root)
    data = json.dumps(
        report, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False,
    ) + "\n"
    destination = args.repo_root / args.output
    if args.check:
        if (
            not destination.is_file()
            or destination.read_text(encoding="utf-8") != data
        ):
            raise SystemExit("PF001 A001 original-skill audit is not reproducible")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if (
            destination.exists()
            and destination.read_text(encoding="utf-8") != data
        ):
            raise SystemExit("PF001 A001 cannot overwrite original skill audit")
        destination.write_text(data, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "audit_sha256": report["audit_sha256"],
        "validation": report["validation"]["interpretation_state"],
        "development": report["development"]["interpretation_state"],
        "stock_selection_alpha_supported": report["positive_stock_selection_alpha_evidence"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
