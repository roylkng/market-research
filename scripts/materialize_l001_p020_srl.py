"""Verify source-retained SunRisers Leeds period earnings and cash hurdle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.l001_p020_srl_hurdles import materialize, validate


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output", type=Path,
        default=Path("research/l001/l001-p020-srl-franchise-profit-and-impairment-hurdle-v1.json"),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    result = materialize(args.repo_root)
    validate(result, root=args.repo_root)
    payload = json.dumps(
        result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    target = args.repo_root / args.output
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != payload:
            raise SystemExit("P020 original source-hurdle report changed")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.read_text(encoding="utf-8") != payload:
            raise SystemExit("P020 original report cannot be overwritten")
        target.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "source_symbol": result["symbol"],
        "source_document_sha256": result["source_document"][
            "full_original_pdf_sha256"
        ],
        "source_profit_ratio_is_ROIC": result[
            "AOC_PAT_ratio_is_annualized_invested_capital_ROIC"
        ],
        "report_sha256": result["report_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
