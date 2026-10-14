"""Materialize frozen HG009 300-identity corporate-action hazard screen.

Absent original NSE action bytes is an explicitly blocked status, never an
all-clear or evidence that there were no cash distributions/stock splits.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p007_actions import (
    build_action_hazard_audit,
    load_original_hg009_sources,
    validate_action_hazard_audit,
)

BASE_START = "2026-10-15"
BASE_END = "2026-10-22"
ORIGINAL_PREENTRY_REVIEW = "2026-10-14T14:00:00+00:00"


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text("utf-8"))
    if not isinstance(payload, dict):
        raise AlphaContractError("P007 action evidence receipt not JSON object")
    return payload


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--source-raw", type=Path)
    p.add_argument("--source-receipt", type=Path)
    p.add_argument("--start", default=BASE_START)
    p.add_argument("--end", default=BASE_END)
    p.add_argument("--prepared-at-utc", default=ORIGINAL_PREENTRY_REVIEW)
    p.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p007-action-hazard-p1-v1.json"),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if bool(args.source_raw) != bool(args.source_receipt):
        raise AlphaContractError("P007 raw NSE action evidence requires receipt")
    raw = args.source_raw.read_bytes() if args.source_raw else None
    receipt = _read_json(args.source_receipt) if args.source_receipt else None
    original, selected, controls = load_original_hg009_sources(
        args.repo_root
    )
    report = build_action_hazard_audit(
        original=original,
        selected=selected,
        controls=controls,
        start_session=args.start,
        end_session=args.end,
        original_action_raw=raw,
        action_receipt=receipt,
        prepared_at_utc=args.prepared_at_utc,
    )
    validate_action_hazard_audit(report)
    saved = (
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )
    path = args.repo_root / args.output
    if args.check:
        if not path.is_file() or path.read_text("utf-8") != saved:
            raise SystemExit("P007 immutable source-screen packet differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text("utf-8") != saved:
            raise SystemExit("P007 original source packet cannot be overwritten")
        path.write_text(saved, encoding="utf-8")
    print(json.dumps({
        "status": "VERIFIED" if args.check else "SOURCE_SCREEN_SEALED",
        "source_state": report["source_state"],
        "audit_id": report["audit_id"],
        "company_count": report["original_declared_identity_count"],
        "action_source_sha": report["source_sha256"],
        "packet_sha256": report["packet_sha256"],
        "action_adjusted_returns_calculated": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
