"""Reproduce all 28 hidden-gem NSE Oct13 market-source rows from original ZIP.

Fully offline, source SHA pinned, and keeps no-cash, no-alpha, no-portfolio
restrictions. A market-session price is not a real fill or value target.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_oct13_28_snapshot import materialize_oct13_28


def _serialized(report: dict) -> str:
    return json.dumps(
        report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    report = materialize_oct13_28(args.repo_root)
    encoded = _serialized(report)
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("original NSE 28-company Oct13 observation was modified")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
    print(json.dumps({
        "audit_id": report["audit_id"],
        "session_date": report["market_session_ist"],
        "frozen_symbol_count": report["total_original_cases"],
        "source_observed_EQ": report["official_valid_EQ_company_count"],
        "source_observed_non_EQ": report["non_EQ_series_company_count"],
        "non_EQ_names": report["non_EQ_series_company_symbols"],
        "missing_or_identity_blocked": report["absent_or_identity_blocked_company_count"],
        "one_day_large_value_vs_prior_median": (
            report["one_day_to_past_median_value_multiple_at_least_5x_symbols"]
        ),
        "return_alpha_or_position_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
