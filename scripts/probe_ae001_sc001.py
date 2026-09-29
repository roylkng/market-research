from __future__ import annotations

import argparse
import gzip
import json
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_delivery import delivery_url
from marketlab.alpha_prospective_sources import (
    append_source_probe,
    session_already_eligible,
    validate_source_ledger,
)
from marketlab.marketdata import udiff_url


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("SC001 ledger must be a JSON object")
    validate_source_ledger(payload)
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
        description="Probe same-session NSE sources for AE001 SC001"
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

    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    market_url = udiff_url(args.session_date)
    delivery_source_url = delivery_url(args.session_date)
    market_raw = fetch(market_url)
    delivery_raw = fetch(delivery_source_url)

    # The authoritative observation time is after both source requests finish.
    captured = datetime.now(UTC)
    updated, attempt = append_source_probe(
        ledger,
        session_date=session_text,
        captured_at_utc=captured.isoformat(),
        market_source_url=market_url,
        market_raw=market_raw,
        delivery_source_url=delivery_source_url,
        delivery_raw=delivery_raw,
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

    if market_raw is not None:
        market_path = Path(str(attempt["market"]["raw_repo_path"]))
        market_path.parent.mkdir(parents=True, exist_ok=True)
        if market_path.exists() and market_path.read_bytes() != market_raw:
            raise RuntimeError(f"SC001 market raw path collision: {market_path}")
        market_path.write_bytes(market_raw)

    if delivery_raw is not None:
        delivery_path = Path(str(attempt["delivery"]["raw_repo_path"]))
        delivery_path.parent.mkdir(parents=True, exist_ok=True)
        compressed = gzip.compress(delivery_raw, compresslevel=9, mtime=0)
        if delivery_path.exists() and delivery_path.read_bytes() != compressed:
            raise RuntimeError(
                f"SC001 delivery raw path collision: {delivery_path}"
            )
        delivery_path.write_bytes(compressed)

    _write_json(args.ledger, updated)
    validate_source_ledger(updated)
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
                "market_status": attempt["market"]["status"],
                "delivery_status": attempt["delivery"]["status"],
                "ledger_sha256": updated["ledger_sha256"],
                "attempt_sha256": attempt["attempt_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
