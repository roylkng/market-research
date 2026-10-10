"""Inspect signed EPS revision arithmetic from the exact first H021 captures.

No prices, benchmark or future return labels are accessed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h021_eps_sign_audit import audit_sealed_first_cohort


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit_sealed_first_cohort()
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "audit_id": result["audit_id"],
        "eligible_eps_observations": result["eligible_eps_observations"],
        "negative_prior_eps": result["prior_eps_negative_count"],
        "sign_inversions": result["direction_inversion_count"],
        "inversions_in_original_top_decile": result["direction_inversion_top_decile_count"],
        "top_decile_inverted_symbols": result["top_decile_inverted_symbols"],
        "selection_unchanged": not result["h021_primary_selection_revised"],
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
