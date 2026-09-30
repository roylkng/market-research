from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_prospective_futures_sources import (
    validate_futures_source_ledger,
)
from marketlab.alpha_sc002_timing import publication_timing_summary


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("SC002 ledger must be a JSON object")
    validate_futures_source_ledger(payload)
    return payload


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize SC002 first-READY publication timing"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = publication_timing_summary(_load(args.ledger))
    unsigned = dict(summary)
    stored = unsigned.pop("summary_sha256")
    if stored != digest(unsigned):
        raise RuntimeError("SC002 timing summary hash mismatch")
    _write(args.output, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
