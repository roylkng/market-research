from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_trials import append_trial_event


def _load(path: Path) -> dict:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append one canonical AE001 trial-ledger event"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--recorded-at-utc", required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger = _load(args.ledger)
    payload = _load(args.payload)
    updated = append_trial_event(
        ledger,
        event_type=args.event_type,
        trial_id=args.trial_id,
        recorded_at_utc=args.recorded_at_utc,
        payload=payload,
    )
    output = args.output or args.ledger
    _write(output, updated)
    event = updated["events"][-1]
    print(
        json.dumps(
            {
                "trial_id": event["trial_id"],
                "event_type": event["event_type"],
                "event_sha256": event["event_sha256"],
                "ledger_sha256": updated["ledger_sha256"],
                "event_count": updated["event_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
