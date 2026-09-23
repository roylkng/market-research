"""Offline verification for the company-intelligence v2 prospective news ledger."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.intelligence_prospective_news import load_news_ledger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    ledger = load_news_ledger(args.ledger)
    print(json.dumps({
        "capture_count": len(ledger["captures"]),
        "observation_count": len(ledger["observations"]),
        "ledger_sha256": ledger["ledger_sha256"],
        "live_capital_allowed": ledger["live_capital_allowed"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
