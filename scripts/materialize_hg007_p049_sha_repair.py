"""Materialize an immutable P049 Datamatics signature discrepancy, not v1 repair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_p049_sha_repair import (
    build_p049_sha_repair,
    verify_repair_artifact,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg007/hg007-p049-canonical-sha-repair-v2.json")
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build_p049_sha_repair(args.repo_root)
    verify_repair_artifact(result, root=args.repo_root)
    output = args.repo_root / args.output
    raw = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != raw:
            raise SystemExit("P049 v2 immutable checksum mismatch report differs")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and output.read_text(encoding="utf-8") != raw:
            raise SystemExit("P049 v2 cannot overwrite existing original repair")
        output.write_text(raw, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "repair_id": result["repair_id"],
        "legacy_claimed": result["legacy_original_claimed_packet_sha256"],
        "recomputed_canonical": result["recomputed_original_canonical_body_sha256"],
        "repair_sha256": result["repair_packet_sha256"],
        "legacy_v1_modified": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
