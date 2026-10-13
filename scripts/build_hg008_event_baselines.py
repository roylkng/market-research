"""Reproduce five official-source historical event-forecast baseline cards.

These are historical stage-specific competing-risk incidence estimates, NOT
forecasts for surviving SAMBHV/INOXGREEN today and NOT share-price alpha.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg008_event_forecast import build_first_seen_baselines, load_baseline_sources


def build(root: Path) -> dict:
    original, survivor, receipts = load_baseline_sources(root)
    return build_first_seen_baselines(original, survivor, receipts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    packet = build(args.repo_root)
    serialized = json.dumps(
        packet, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != serialized:
                raise ValueError("original HG006 stage baseline packet changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as out:
                out.write(serialized)
    print(json.dumps({
        "baseline_id": packet["baseline_id"],
        "stage_baseline_count": packet["stage_baseline_count"],
        "existing_current_company_probability_count": packet["existing_case_current_probability_count"],
        "existing_survivor_abstention_count": len(packet["existing_company_survivor_abstentions"]),
        "historical_model_out_of_sample_validated": False,
        "stock_price_return_prediction": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
