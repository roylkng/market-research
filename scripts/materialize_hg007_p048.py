"""Materialize an immutable-source seven-catalyst research triage, not a pick list."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_p048_direct_catalyst import (
    materialize_direct_catalyst_triage,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg007/hg007-p048-direct-catalyst-triage-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    packet = materialize_direct_catalyst_triage(args.repo_root)
    raw = (
        json.dumps(packet, sort_keys=True, indent=2, allow_nan=False, ensure_ascii=False)
        + "\n"
    )
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != raw:
            raise SystemExit("P048 reviewed original source packet differs from frozen output")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(json.dumps({
        "audit_id": packet["audit_id"],
        "source_session": packet["latest_official_price_session_ist"],
        "reviewed_direct_catalysts": packet["active_direct_catalyst_count"],
        "review_lanes": packet["review_lanes"],
        "packet_sha256": packet["packet_sha256"],
        "live_capital_allowed": False,
        "state": "VALIDATED" if args.check else "MATERIALIZED",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
