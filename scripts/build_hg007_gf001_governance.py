"""Replay GF001 October 4 official ownership for all 28 HG002 hidden gems.

Requires *existing* full-market GF001-D002 and SS001-D002 artifact files;
no NSE fetch, no H023-U001 misattribution and no investment score.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_gf001_governance import (
    GF001_RESULT_PATH,
    _read_json,
    build_outside_u001_governance,
    frozen_outside_u001,
    validate_original_full_market,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--gf001-artifact", type=Path, required=True)
    parser.add_argument("--ss001-artifact", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    symbols, membership = frozen_outside_u001(args.repo_root)
    gf001 = _read_json(args.gf001_artifact / "gf001-d002-panel.json")
    ss001 = _read_json(args.ss001_artifact / "ss001-d002-shareholding-sources.json")
    gf001_result = _read_json(args.repo_root / GF001_RESULT_PATH)
    captured = validate_original_full_market(ss001, gf001, gf001_result)

    raw_store = args.out_dir / "raw" / "sha256"
    report = build_outside_u001_governance(
        symbols=symbols,
        census=ss001,
        panel=gf001,
        artifact_raw_root=args.gf001_artifact / "raw",
        extracted_original_dir=raw_store,
        captured=captured,
    )
    report["frozen_membership_evidence"] = membership
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "full-market-governance-28-v1.json").write_text(
        json.dumps(
            report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
        ) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "audit_id": report["audit_id"],
        "selected_outside_u001_company_count": 28,
        "oct04_core_ready_count": report["original_oct04_core_ready_count"],
        "unready_count": report["original_oct04_source_unavailable_or_unready_count"],
        "oct04_pledge_boolean_true_symbols": report["original_oct04_pledge_boolean_true_symbols"],
        "original_xbrl_bytes_retained_unique_count": report["original_xbrl_bytes_retained_unique_count"],
        "as_of_utc": report["original_snapshot_cutoff_utc"],
        "current_oct11_governance_verified": False,
        "company_expected_returns_calculated": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
