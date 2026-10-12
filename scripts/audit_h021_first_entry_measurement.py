"""Reconcile frozen H021 signal, first official stock OHLC and measurement hazards.

This runs without network and never substitutes a missing Nifty 500 index,
trading fill, stock dividend credit or prospectively unknowable earnings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h021_first_measurement import source_pinned_first_measurement


def _json(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    packet = source_pinned_first_measurement(args.repo_root)
    encoded = _json(packet)
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("frozen first H021 measurement report source drifted")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as out:
                out.write(encoded)

    print(json.dumps({
        "audit_id": packet["audit_id"],
        "first_stock_opens": packet["first_source_stock_open_count"],
        "index_state_first_attempt": packet["first_source_attempt_nifty500_index_state"],
        "negative_eps_inversion_symbols": packet[
            "original_selected_negative_eps_inversion_symbols"
        ],
        "preentry_dividend_notice_symbols": packet[
            "original_selected_preentry_dividend_notice_symbols"
        ],
        "benchmark_excess_calculated": packet["benchmark_excess_calculated"],
        "return_outcomes_opened": packet["return_outcomes_opened"],
        "live_capital_allowed": packet["live_capital_allowed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
