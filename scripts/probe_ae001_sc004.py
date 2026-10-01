from __future__ import annotations

import argparse
import gzip
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_d010_p1 import short_archive_url
from marketlab.alpha_d010_p2 import slb_archive_url
from marketlab.alpha_prospective_d010_sources import (
    MAX_PREVIOUS_SESSION_LOOKBACK_DAYS,
    append_sc004_source_probe,
    session_already_eligible,
    validate_sc004_source_ledger,
)
from marketlab.marketdata import udiff_url


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("SC004 ledger must be a JSON object")
    validate_sc004_source_ledger(payload)
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


def _retain(path_text: object, raw: bytes | None) -> None:
    if raw is None or path_text is None:
        return
    path = Path(str(path_text))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        gzip.compress(raw, compresslevel=9, mtime=0)
        if path.suffix == ".gz"
        else raw
    )
    if path.exists() and path.read_bytes() != payload:
        raise RuntimeError(f"SC004 raw path collision: {path}")
    path.write_bytes(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe live NSE short-selling and SLB sources for SC004"
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
                    "publication_session": session_text,
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

    current_market_url = udiff_url(args.session_date)
    current_market_raw = fetch(current_market_url)

    previous_day = None
    previous_market_url = None
    previous_market_raw = None
    for offset in range(1, MAX_PREVIOUS_SESSION_LOOKBACK_DAYS + 1):
        candidate = args.session_date - timedelta(days=offset)
        candidate_url = udiff_url(candidate)
        candidate_raw = fetch(candidate_url)
        if candidate_raw is not None:
            previous_day = candidate
            previous_market_url = candidate_url
            previous_market_raw = candidate_raw
            break

    short_url = short_archive_url(args.session_date)
    slb_url = slb_archive_url(args.session_date)
    short_raw = fetch(short_url)
    slb_raw = fetch(slb_url)

    # The authoritative source-observation timestamp is after every required
    # request, including the previous-session support request, has completed.
    captured = datetime.now(UTC)
    updated, attempt = append_sc004_source_probe(
        ledger,
        publication_session=session_text,
        previous_completed_session=(
            None if previous_day is None else previous_day.isoformat()
        ),
        captured_at_utc=captured.isoformat(),
        current_market_source_url=current_market_url,
        current_market_raw=current_market_raw,
        previous_market_source_url=previous_market_url,
        previous_market_raw=previous_market_raw,
        short_source_url=short_url,
        short_raw=short_raw,
        slb_source_url=slb_url,
        slb_raw=slb_raw,
    )
    if attempt is None:
        print(
            json.dumps(
                {
                    "state": "ALREADY_ELIGIBLE",
                    "publication_session": session_text,
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    _retain(
        attempt["current_market"].get("raw_repo_path"),
        current_market_raw,
    )
    _retain(
        attempt["previous_market"].get("raw_repo_path"),
        previous_market_raw,
    )
    _retain(
        attempt["short_selling"].get("raw_repo_path"),
        short_raw,
    )
    _retain(
        attempt["slb_open_positions"].get("raw_repo_path"),
        slb_raw,
    )

    _write_json(args.ledger, updated)
    validate_sc004_source_ledger(updated)
    print(
        json.dumps(
            {
                "state": "CAPTURED",
                "publication_session": session_text,
                "previous_completed_session": attempt[
                    "previous_completed_session"
                ],
                "captured_at_utc": attempt["captured_at_utc"],
                "captured_before_or_at_cutoff": attempt[
                    "captured_before_or_at_cutoff"
                ],
                "current_market_status": attempt["current_market"]["status"],
                "previous_market_status": attempt["previous_market"]["status"],
                "short_status": attempt["short_selling"]["status"],
                "slb_status": attempt["slb_open_positions"]["status"],
                "eligible_before_cutoff": attempt[
                    "eligible_before_cutoff"
                ],
                "attempt_sha256": attempt["attempt_sha256"],
                "ledger_sha256": updated["ledger_sha256"],
                "changed": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
