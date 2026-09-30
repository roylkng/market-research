from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_futures import fo_udiff_url
from marketlab.alpha_prospective_futures_sources import (
    append_futures_source_probe,
    session_already_eligible,
    session_source_ready_observed,
    validate_futures_source_ledger,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("SC002 ledger must be a JSON object")
    validate_futures_source_ledger(payload)
    return payload


def _write_json(path: Path, payload: object) -> None:
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
        description="Probe same-session NSE FO UDiFF source for AE001 SC002"
    )
    parser.add_argument("--session-date", type=date.fromisoformat, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger = _load(args.ledger)
    session_text = args.session_date.isoformat()
    if session_already_eligible(ledger, session_text):
        print(
            json.dumps(
                {
                    "state": "ALREADY_ELIGIBLE",
                    "session_date": session_text,
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if session_source_ready_observed(ledger, session_text):
        print(
            json.dumps(
                {
                    "state": "SOURCE_READY_ALREADY_OBSERVED",
                    "session_date": session_text,
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    source_url = fo_udiff_url(args.session_date)
    raw = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )(source_url)

    captured = datetime.now(UTC)
    updated, attempt = append_futures_source_probe(
        ledger,
        session_date=session_text,
        captured_at_utc=captured.isoformat(),
        source_url=source_url,
        raw=raw,
    )
    if attempt is None:
        print(
            json.dumps(
                {
                    "state": "ALREADY_ELIGIBLE",
                    "session_date": session_text,
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    if raw is not None:
        raw_path = Path(str(attempt["futures"]["raw_repo_path"]))
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if raw_path.exists() and raw_path.read_bytes() != raw:
            raise RuntimeError(f"SC002 raw path collision: {raw_path}")
        raw_path.write_bytes(raw)

    _write_json(args.ledger, updated)
    validate_futures_source_ledger(updated)
    print(
        json.dumps(
            {
                "state": "CAPTURED",
                "session_date": session_text,
                "changed": True,
                "eligible_before_cutoff": attempt[
                    "eligible_before_cutoff"
                ],
                "captured_at_utc": attempt["captured_at_utc"],
                "futures_status": attempt["futures"]["status"],
                "diagnostics": attempt["futures"]["diagnostics"],
                "ledger_sha256": updated["ledger_sha256"],
                "attempt_sha256": attempt["attempt_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
