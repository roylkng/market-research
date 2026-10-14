"""Freeze original HG009 300-arm accounting/earning source confounder baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_controls import load_hg009_inputs
from marketlab.hg009_p005_baseline import (
    SOURCE_CONTROL,
    build_hg009_source_baseline,
    validate_hg009_source_baseline,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p005-source-baseline-300-v1.json"),
    )
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    source, selected = load_hg009_inputs(args.repo_root)
    controls = json.loads(
        (args.repo_root / SOURCE_CONTROL).read_text(encoding="utf-8")
    )
    report = build_hg009_source_baseline(
        source=source, selected=selected, controls=controls
    )
    validate_hg009_source_baseline(
        report, source=source, selected=selected, controls=controls
    )
    payload = (
        json.dumps(
            report, sort_keys=True, indent=2,
            ensure_ascii=False, allow_nan=False,
        ) + "\n"
    )
    file = args.repo_root / args.output
    if args.check:
        if not file.is_file() or file.read_text(encoding="utf-8") != payload:
            raise SystemExit("HG009 P005 pre-entry original-source baseline mismatch")
    else:
        file.parent.mkdir(parents=True, exist_ok=True)
        if file.exists() and file.read_text(encoding="utf-8") != payload:
            raise SystemExit("HG009 P005 original-source baseline cannot be overwritten")
        file.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "FROZEN",
        "selected_count": report["arms"]["SELECTED"]["original_source_count"],
        "one_lane_count": report["arms"]["ONE_LANE"]["original_source_count"],
        "zero_lane_count": report["arms"]["ZERO_LANE"]["original_source_count"],
        "packet_sha256": report["packet_sha256"],
        "date_source": report["data_source_snapshot_date"],
        "return_labels_opened": report["future_market_returns_observed"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
