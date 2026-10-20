"""Seal or verify H1/H5 growth-balance descriptive sensitivity.

H1 rules are post-hoc. The same H5 rule is declared Oct 21 before its Oct 22
exit, but H1 prices were already visible. Neither is confirmatory alpha.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p025_growth import (
    build_report,
    load_sources,
    validate_report,
)

OUTPUT = {
    1: Path("research/hg009/hg009-p025-h1-growth-balanced-20261021.json"),
    5: Path("research/hg009/hg009-p025-h5-growth-balanced-20261022.json"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--horizon", type=int, choices=(1, 5), default=1)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        baseline, price = load_sources(args.repo_root, args.horizon)
    except FileNotFoundError:
        if args.horizon != 5:
            raise
        print(json.dumps({
            "state": "WAITING_FOR_OCT22_ORIGINAL_H5_SOURCE",
            "horizon": 5, "changed": False,
            "proven_alpha": False, "live_capital_allowed": False,
        }, sort_keys=True))
        return 0
    output = build_report(baseline, price, horizon=args.horizon)
    validate_report(output, baseline=baseline, market=price)
    path = args.repo_root / OUTPUT[args.horizon]
    payload = json.dumps(
        output, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False,
    ) + "\n"
    if args.check:
        if not path.is_file():
            if args.horizon == 5:
                print(json.dumps({
                    "state": "ORIGINAL_H5_SOURCE_AVAILABLE_REPORT_NOT_YET_SEALED",
                    "horizon": 5, "changed": False,
                    "proven_alpha": False, "live_capital_allowed": False,
                }, sort_keys=True))
                return 0
            raise SystemExit("P025 source-ready H1 signed result not yet sealed")
        if path.read_text(encoding="utf-8") != payload:
            raise SystemExit("P025 signed original price/baseline report differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") != payload:
            raise SystemExit("P025 original signed price report cannot be overwritten")
        path.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "SIGNED_SOURCE_SENSITIVITY",
        "horizon": args.horizon,
        "report_sha256": output["report_sha256"],
        "source_h1_or_h5_sha256": output["original_price_report_sha256"],
        "gaps": output["gaps"],
        "proven_alpha": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
