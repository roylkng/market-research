from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from marketlab.h024_prospective_summary import build_prospective_summary


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the deterministic H024 prospective evidence summary"
    )
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary = build_prospective_summary(
        source_ledger=_load(args.state_dir / "source-ledger.json"),
        evidence_ledger=_load(args.state_dir / "evidence-ledger.json"),
        event_ledger=_load(args.state_dir / "event-ledger.json"),
        session_ledger=_load(args.state_dir / "session-ledger.json"),
        outcome_ledger=_load(args.state_dir / "outcome-ledger.json"),
    )
    _write(args.output, summary)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
