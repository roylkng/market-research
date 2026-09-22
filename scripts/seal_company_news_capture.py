"""Seal one bounded news-discovery run into the prospective metadata ledger."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.intelligence_prospective_news import (
    capture_from_store,
    load_news_ledger,
    merge_news_ledger,
    write_news_ledger,
)
from marketlab.intelligence_store import ResearchStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--identity-session", required=True)
    parser.add_argument("--identity-raw-sha256", required=True)
    args = parser.parse_args()
    with ResearchStore(args.store) as store:
        capture, observations = capture_from_store(
            store,
            identity_session=args.identity_session,
            identity_raw_sha256=args.identity_raw_sha256,
        )
    ledger = merge_news_ledger(load_news_ledger(args.ledger), capture, observations)
    write_news_ledger(args.ledger, ledger)
    print(json.dumps({
        "capture_id": capture["capture_id"],
        "captured_at": capture["captured_at"],
        "run_status": capture["run_status"],
        "observation_count": len(observations),
        "ledger_capture_count": len(ledger["captures"]),
        "ledger_observation_count": len(ledger["observations"]),
        "ledger_sha256": ledger["ledger_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
