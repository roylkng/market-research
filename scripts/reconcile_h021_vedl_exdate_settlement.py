"""Reproduce source-pinned H021 VEDL pre-ex-date settlement assumptions.

No stock returns, dividend credit, verified buy/sell order or portfolio.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h021_vedl_settlement import (
    build_pre_ex_date_settlement_review,
    load_exact_source_records,
    validate_pre_ex_date_settlement_review,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    originals, receipts = load_exact_source_records(args.repo_root)
    packet = build_pre_ex_date_settlement_review(
        originals, receipts, repo_root=args.repo_root
    )
    validate_pre_ex_date_settlement_review(packet)
    encoded = json.dumps(
        packet, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("original H021 pre-ex date risk packet was changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
    print(json.dumps({
        "review_id": packet["review_id"],
        "symbol": packet["security"]["symbol"],
        "dividend_per_share_inr": packet["original_issuer_dividend_per_share_inr"],
        "last_cum_dividend_market_session": packet[
            "last_cum_dividend_regular_market_session_ist"
        ],
        "official_ex_date": packet["official_nse_exchange_ex_date_ist"],
        "hypothetical_earliest_normal_t1_settlement": packet[
            "ordinary_t1_candidate_settlement_session_ist"
        ],
        "actual_buy_execution_verified": packet[
            "actual_buy_execution_and_slippage_verified"
        ],
        "cash_entitlement_verified": packet["cash_entitlement_independently_verified"],
        "return_outcomes_opened": packet["future_h021_20_or_60_session_outcomes_opened"],
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
