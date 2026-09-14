from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.h021_stockanalysis_full_probe import aggregate_shard_reports


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--shard-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = _load_json(args.config)
    shard_paths = sorted(args.shard_dir.glob("*.json"))
    if not shard_paths:
        raise SystemExit(f"no shard reports found in {args.shard_dir}")
    reports = [_load_json(path) for path in shard_paths]
    aggregate = aggregate_shard_reports(config, reports)
    aggregate["captured_at_utc"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    aggregate["config_path"] = str(args.config)
    aggregate["shard_report_files"] = [path.name for path in shard_paths]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = aggregate["summary"]
    print(
        f"total={summary['total']} parser={summary['parser_pass']} "
        f"semantic={summary['semantic_match_pass']} pass={summary['probe_pass']} out={args.out}"
    )


if __name__ == "__main__":
    main()
