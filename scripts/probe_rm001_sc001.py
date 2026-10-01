from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_sc003_preopen import latest_completed_sc001_target
from marketlab.events import sha256_bytes
from marketlab.rm001_size_source import security_master_url
from marketlab.rm001_size_timing import (
    append_size_source_probe,
    size_timing_summary,
    target_ready_observed,
    validate_size_source_ledger,
)


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


def _market_raw(target: dict) -> bytes:
    market = target.get("market")
    if not isinstance(market, dict):
        raise RuntimeError("RM001-SC001 target lacks SC001 market metadata")
    path = Path(str(market.get("raw_repo_path") or ""))
    if not path.exists():
        raise RuntimeError(f"SC001 market raw file missing: {path}")
    raw = path.read_bytes()
    if sha256_bytes(raw) != market.get("raw_sha256"):
        raise RuntimeError("SC001 market raw file hash mismatch")
    return raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe previous-session NSE Security File for RM001-SC001"
    )
    parser.add_argument(
        "--observation-date",
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--size-ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sc001 = _load(args.sc001_ledger)
    size_ledger = _load(args.size_ledger)
    validate_size_source_ledger(size_ledger)
    observation_date = args.observation_date.isoformat()
    target = latest_completed_sc001_target(
        sc001,
        observation_date=observation_date,
    )
    target_session = str(target["session_date"])

    if target_ready_observed(size_ledger, target_session):
        summary = size_timing_summary(size_ledger)
        _write(args.summary, summary)
        print(
            json.dumps(
                {
                    "state": "TARGET_READY_ALREADY_OBSERVED",
                    "target_session_date": target_session,
                    "observation_date": observation_date,
                    "changed": False,
                    "summary_sha256": summary["summary_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0

    source_url = security_master_url(date.fromisoformat(target_session))
    security_raw = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )(source_url)
    captured = datetime.now(UTC)

    updated, attempt = append_size_source_probe(
        size_ledger,
        sc001_attempt=target,
        observation_date=observation_date,
        captured_at_utc=captured.isoformat(),
        market_raw=_market_raw(target),
        security_raw=security_raw,
        source_url=source_url,
    )
    if attempt is None:
        raise RuntimeError("RM001-SC001 unexpectedly returned no attempt")

    if security_raw is not None:
        raw_path = Path(str(attempt["raw_repo_path"]))
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if raw_path.exists() and raw_path.read_bytes() != security_raw:
            raise RuntimeError(f"RM001-SC001 raw path collision: {raw_path}")
        raw_path.write_bytes(security_raw)

    _write(args.size_ledger, updated)
    validate_size_source_ledger(updated)
    summary = size_timing_summary(updated)
    _write(args.summary, summary)

    print(
        json.dumps(
            {
                "state": "CAPTURED",
                "changed": True,
                "target_session_date": target_session,
                "observation_date": observation_date,
                "captured_at_utc": attempt["captured_at_utc"],
                "source_status": attempt["source_status"],
                "ready_before_preopen_cutoff": attempt[
                    "ready_before_preopen_cutoff"
                ],
                "attempt_sha256": attempt["attempt_sha256"],
                "ledger_sha256": updated["ledger_sha256"],
                "summary_sha256": summary["summary_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
