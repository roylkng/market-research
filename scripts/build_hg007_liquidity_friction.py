"""Report liquidity friction from original, exactly sourced NSE Oct 9 UDiFF."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_liquidity_friction import (
    build_one_session_liquidity,
    load_official_oct9,
    validate_one_session_liquidity,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    packet, raw, sources = load_official_oct9(args.repo_root)
    screen = build_one_session_liquidity(packet, raw, sources)
    validate_one_session_liquidity(screen)
    encoded = json.dumps(screen, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("official single-session friction packet was modified")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as f:
                f.write(encoded)
    print(json.dumps({
        "study_id": screen["audit_id"],
        "source_date": screen["source_session"],
        "case_count": len(screen["cases"]),
        "traded_value_crore": {
            row["symbol"]: round(row["single_session_traded_value_inr_crore"], 5)
            for row in screen["cases"]
        },
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
