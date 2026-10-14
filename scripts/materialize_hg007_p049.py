"""Materialize FY26 source-referenced DATAMATICS cashflow sensitivity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_p049_datamatics_cash import materialize_datamatics_cash_hurdle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = materialize_datamatics_cash_hurdle(args.repo_root)
    payload = (
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False, ensure_ascii=False)
        + "\n"
    )
    if args.check:
        # Compare the signed canonical JSON payload, not irrelevant indentation
        # or whether an exact INR amount is spelled 295531945 or 295531945.0.
        if not args.output.exists():
            raise SystemExit("P049 materialized source report is missing")
        observed = json.loads(args.output.read_text(encoding="utf-8"))
        if observed != result or observed.get("packet_sha256") != result["packet_sha256"]:
            raise SystemExit("P049 frozen report no longer matches original source math")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "analysis_id": result["audit_id"],
        "packet_sha256": result["packet_sha256"],
        "observed_oct13_price_inr": result["market_source"][
            "official_EQ_close_inr_not_current_quote"
        ],
        "observed_fy26_cfo_less_cash_capex_cr": result[
            "fy26_cfo_less_fixed_asset_cash_spending_inr_crore_not_normalized_fcf"
        ],
        "live_capital_allowed": False,
        "status": "VERIFIED" if args.check else "MATERIALIZED",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
