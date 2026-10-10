"""Recompute Sambhv steel-only versus conditional captive-power CAPEX boundary.

No external data, outcome labels, issuer model forecasting or portfolio orders.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_sambhv_phase1_sensitivity import (
    build_steel_power_sensitivity,
    load_sambhv_pinned_sources,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    receipt, market, hurdle, provenance = load_sambhv_pinned_sources(args.repo_root)
    packet = build_steel_power_sensitivity(
        receipt, market, hurdle, provenance=provenance
    )
    raw = json.dumps(
        packet, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != raw:
                raise ValueError("HG007 original-Sambhv sensitivity changed after source review")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as output:
                output.write(raw)

    rows = packet["two_alternative_assumptions_not_additive_payoff_estimates"]
    print(json.dumps({
        "sensitivity_id": packet["sensitivity_id"],
        "original_pdf_sha256": packet["source_provenance"]["original_issuer_pdf"]["sha256"],
        "issuer_steel_capex_cr": packet["source_verified_steel_only_capex_inr_crore"],
        "additional_captive_power_capex_cr": packet[
            "source_verified_additional_power_capex_inr_crore"
        ],
        "strong_steel_only_pct": 100 * rows[0][
            "original_steel_only_net_increment_to_frozen_cap"
        ],
        "strong_conditional_steel_power_pct": 100 * rows[0][
            "conditional_steel_plus_power_net_increment_to_frozen_cap"
        ],
        "actual_required_power_inclusion_proven": False,
        "stock_target_or_future_return_computed": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
