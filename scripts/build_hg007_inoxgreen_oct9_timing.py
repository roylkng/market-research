"""Materialize original NSE INOXGREEN Oct9 turnover versus timed pledge disclosure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_inoxgreen_oct9_timing import (
    build_oct9_volatility_custody,
    load_immutable_inputs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    p034, acquisition, p012, raw, provenance = load_immutable_inputs(
        args.repo_root
    )
    report = build_oct9_volatility_custody(
        p034, acquisition, p012, raw, provenance
    )
    serial = json.dumps(
        report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != serial:
                raise ValueError("P035 source and timing audit differs from frozen original")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as f:
                f.write(serial)
    data = report["source_ino_green_9oct"]
    print(json.dumps({
        "audit_id": report["audit_id"],
        "official_previous_session_close_inr": data[
            "previous_nse_session_official_close_inr"
        ],
        "official_oct9_close_inr": data["9oct_official_close_inr"],
        "oct9_day_change_pct": data["9oct_change_vs_previous_session_close_pct"],
        "oct9_traded_shares": data["9oct_official_traded_shares"],
        "oct9_traded_value_crore": data["9oct_official_traded_value_inr_crore"],
        "official_pledge_broadcast_after_oct8_session_close": report[
            "disclosure_timing_control"
        ]["first_original_nse_pledge_broadcast_after_oct8_close"],
        "causation_proved": False,
        "investment_recommendation_authorized": False,
        "live_capital_allowed": False,
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
