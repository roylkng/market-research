"""Reproduce exact original NSE share-capital versus cash reverse hurdles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p015_hurdles import materialize, validate_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p015-ace-acutaas-hurdles-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = materialize(args.repo_root)
    validate_result(report, args.repo_root)
    content = json.dumps(
        report, indent=2, sort_keys=True,
        allow_nan=False, ensure_ascii=False,
    ) + "\n"
    file = args.repo_root / args.output
    if args.check:
        if not file.is_file() or file.read_text("utf-8") != content:
            raise SystemExit("P015 original-source hurdle report differs")
    else:
        file.parent.mkdir(parents=True, exist_ok=True)
        if file.exists() and file.read_text("utf-8") != content:
            raise SystemExit("P015 original research report cannot be overwritten")
        file.write_text(content, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "companies": report["fixed_companies"],
        "sha256": report["packet_sha256"],
        "investable": report["realizable_equity_valuations_complete"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
