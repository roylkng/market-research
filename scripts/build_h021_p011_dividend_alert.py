"""Publish source-attributed October H021 dividend measurement hazard before entry.

No web query, market price, trading order or future return is performed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h021_p011_dividend_alert import replay_first_cohort


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    data = replay_first_cohort(Path("."))
    serialized = json.dumps(
        data, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
    ) + "\n"
    if args.verify_existing:
        if args.output.read_text(encoding="utf-8") != serialized:
            raise ValueError("H021 original pre-entry event warning changed")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as out:
            out.write(serialized)
    print(json.dumps({
        "risk_id": data["risk_id"],
        "frozen_symbol_count": len(data["frozen_selected_symbols"]),
        "flagged_dividend": data["publicly_identified_pre_entry_dividend_symbols"],
        "stock_total_return_basis_approved": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
