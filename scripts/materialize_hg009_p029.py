"""Materialize source-original NSE pre-entry futures exposure, not CAS eligibility."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p029_fo_exposure import materialize, validate


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p029-preentry-fo-microstructure-v1.json"),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    packet = materialize(args.repo_root)
    validate(packet, args.repo_root)
    serialized = json.dumps(
        packet, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False,
    ) + "\n"
    path = args.repo_root / args.output
    if args.check:
        if not path.is_file() or path.read_text(encoding="utf-8") != serialized:
            raise SystemExit("P029 original source F&O evidence differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") != serialized:
            raise SystemExit("P029 original-signed source packet cannot be overwritten")
        path.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "FROZEN",
        "report_sha256": packet["report_sha256"],
        "underlyings_in_original_oct14_FO": packet[
            "original_FO_stock_underlying_ticker_count"
        ],
        "arm_ticker_presence": {
            k: v["oct14_futures_ticker_seen_count"]
            for k, v in packet["original_group_exposure"].items()
        },
        "actual_CAS_eligible_count_verified": 0,
        "no_stock_returns_used": True,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
