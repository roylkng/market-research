"""Verify exact archived original NSE no-data response for INOXGREEN Oct 10.

This report explicitly does not equate one empty API request with the
absence of a filed September Regulation 31 document on other venues.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_ownership_gap import build_original_empty_api_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    report = build_original_empty_api_evidence(args.repo_root)
    raw = json.dumps(
        report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != raw:
                raise ValueError("original NSE no-data evidence was altered")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as f:
                f.write(raw)
    print(json.dumps({
        "evidence_id": report["evidence_id"],
        "source_status": report["classification"],
        "record_count_for_this_api_request": report["source"]["original_data_array_length"],
        "september_original_shareholding_confirmed": False,
        "pledged_shares_confirmed": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
