"""Probe NSE corporate-action discovery for H5, retaining original bytes/failures.

This is only a *partial hazard screen*. An empty HTTP 200 does NOT certify
corporate-action coverage and cannot authorize economic shareholder returns.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.hg009_p007_probe import (
    build_p007_probe,
    commit_probe,
    replay_all_probes,
)
from marketlab.nse import NSEClient


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--attempt-id", help="Unique immutable run ID for this actual probe")
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()
    if args.verify:
        print(json.dumps(replay_all_probes(args.repo_root), sort_keys=True))
        return 0
    if not args.attempt_id:
        p.error("P007 P2 real observation requires a stable --attempt-id")
    client = NSEClient(timeout=20, attempts=3)
    result, raw = build_p007_probe(
        repo_root=args.repo_root,
        attempt_id=args.attempt_id,
        fetcher=lambda: client.corporate_actions_with_raw(
            None, from_date="15-10-2026", to_date="22-10-2026"
        ),
        clock=lambda: datetime.now(UTC),
    )
    path = commit_probe(
        repo_root=args.repo_root, envelope=result, source_raw=raw,
    )
    replay = replay_all_probes(args.repo_root)
    print(json.dumps({
        "state": result["screen"]["source_state"],
        "attempt_receipt": str(path),
        "raw_sha256": result["source_receipt"]["raw_sha256"],
        "source_original_bytes_archived": raw is not None,
        "original_three_arm_count": result["original_300_identity_count"],
        "partial_api_hazards": result["screen"]["observed_hazard_count"],
        "verified_archived_attempts": replay["verified_attempt_count"],
        "adjusted_stock_returns_certified": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
