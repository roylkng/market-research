"""Materialize source-locked HG009 300-company observational comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_controls import (
    build_hg009_control_manifest,
    load_hg009_inputs,
    verify_hg009_controls,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
        ),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source, selected = load_hg009_inputs(args.repo_root)
    manifest = build_hg009_control_manifest(source, selected)
    verify_hg009_controls(manifest, source=source, selected=selected)
    content = (
        json.dumps(
            manifest, sort_keys=True, indent=2,
            ensure_ascii=False, allow_nan=False,
        )
        + "\n"
    )
    if args.check:
        if not args.output.is_file():
            raise SystemExit("HG009 P001 original control manifest missing")
        if args.output.read_text(encoding="utf-8") != content:
            raise SystemExit("HG009 P001 source-bound control manifest drift")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if (
            args.output.exists()
            and args.output.read_text(encoding="utf-8") != content
        ):
            raise SystemExit("HG009 P001 original manifest cannot be replaced")
        args.output.write_text(content, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "control_id": manifest["control_id"],
        "observation_identities": manifest["total_unique_observation_identities"],
        "selected": manifest["selected_company_count"],
        "one_lane_controls": manifest["one_lane_control_company_count"],
        "zero_lane_controls": manifest["zero_lane_control_company_count"],
        "manifest_sha256": manifest["manifest_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
