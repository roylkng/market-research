from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.nifty200_history import file_sha256, load_registry, reconstruct_freezes


def run(args: argparse.Namespace) -> list[dict]:
    registry_path = Path(args.registry)
    registry = load_registry(registry_path)
    snapshots = reconstruct_freezes(registry, repo_root=args.repo_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    for snapshot in snapshots:
        path = output_dir / f"{snapshot['quarter_id']}-{snapshot['freeze_date']}.json"
        path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_rows.append(
            {
                "quarter_id": snapshot["quarter_id"],
                "freeze_date": snapshot["freeze_date"],
                "snapshot_path": str(path),
                "snapshot_sha256": snapshot["sha256"],
                "regular_member_count": snapshot["regular_member_count"],
                "dummy_symbols": snapshot["dummy_symbols"],
                "non_financial_member_count": snapshot["non_financial_member_count"],
            }
        )

    manifest = {
        "schema_version": 1,
        "registry_id": registry["id"],
        "registry_path": str(registry_path),
        "registry_file_sha256": file_sha256(registry_path),
        "anchor_raw_sha256": registry["anchor"]["raw_sha256"],
        "snapshot_count": len(snapshots),
        "snapshots": manifest_rows,
        "live_capital_allowed": False,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description="Build point-in-time Nifty 200 historical snapshots")
    parser.add_argument(
        "--registry",
        default="registry/nifty200_historical_membership_v1.yaml",
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--output-dir",
        default="research/historical/nifty200/snapshots-v1",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
