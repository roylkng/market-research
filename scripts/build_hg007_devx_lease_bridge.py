"""Reproduce original FY26 DEVX cash lease reconciliation and October credit risk.

Uses only already anchored exact NSE/Acuite originals and frozen HG005.
No network, current share price, portfolio target, future returns or trade.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_devx_lease_economics import (
    build_devx_lease_cash_bridge,
    load_original_devx_evidence,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("must supply --out when verifying prior output")

    original, market, provenance = load_original_devx_evidence(args.repo_root)
    packet = build_devx_lease_cash_bridge(original, market, provenance)
    serialized = json.dumps(
        packet, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    )+"\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != serialized:
                raise ValueError("DEVX cash/lease report changed from exact original source")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(serialized)

    print(json.dumps({
        "analysis_id": packet["analysis_id"],
        "symbol": packet["symbol"],
        "source_lease_ebitda_reconciled": abs(
            packet["fy26_standalone_issuer_reported"][
                "indas_ebitda_less_cash_rent_less_cash_ebit_rounding_cr"
            ]
        ) <= 0.02,
        "cash_ebit_pct_of_indas_ebitda": packet["fy26_standalone_issuer_reported"][
            "cash_ebit_as_ratio_of_indas_ebitda_pct"
        ],
        "actual_winston_earnings_verified": False,
        "verified_current_ev": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
