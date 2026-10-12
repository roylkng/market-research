"""Verify and preserve complete H021 first-session source without backdating.

Original Oct12 P004 first index attempt was HTTP404; P018 later verified
the 12 Oct Nifty500 CSV from two NSE archive hosts. A later successful
P004 packet is allowed only if every original equity bar and index value
matches the preserved independent sources.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h021_first_source_reconciliation import (
    load_pinned_reconciliation_sources,
    reconcile_source_packet,
    validate_reconciliation,
)

DEFAULT_COMPLETE = Path(
    "research/prospective/h021/entry-observations/"
    "2026-10-12-first-entry-v1.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--full-path", type=Path, default=DEFAULT_COMPLETE)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    root = args.repo_root
    original, supplement = load_pinned_reconciliation_sources(root)
    path = args.full_path if args.full_path.is_absolute() else root / args.full_path
    complete = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(complete, dict):
        raise TypeError("first later-complete market source must be JSON object")
    payload = reconcile_source_packet(
        first_attempt=original,
        source_supplement=supplement,
        later_complete=complete,
    )
    validate_reconciliation(payload)
    encoded = json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.verify_existing:
        if args.out.read_text(encoding="utf-8") != encoded:
            raise ValueError("later complete source reconciliation has drifted")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(json.dumps({
        "review_id": payload["review_id"],
        "source_original_404_preserved": payload["original_index_404_receipt_retained"],
        "verified_selected_stock_source_count": len(payload["selected_symbols_unchanged"]),
        "nifty500_official_open": payload["nifty500_open_from_agreed_official_sources"],
        "nifty500_official_close": payload["nifty500_close_from_agreed_official_sources"],
        "stock_and_benchmark_source_complete": payload["stock_and_benchmark_source_complete"],
        "returns_calculated": payload["benchmark_excess_calculated"],
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
