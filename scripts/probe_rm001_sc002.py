from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_history import canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_d015 import SOURCE_URL
from marketlab.rm001_industry_timing import (
    append_industry_source_probe,
    industry_readiness_summary,
    session_ready_observed,
    validate_industry_source_ledger,
)
from marketlab.rm001_size_source import security_master_url


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
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


def _write_exact(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"RM001-SC002 raw path collision: {path}")
    path.write_bytes(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe same-session Nifty Total Market industry sources"
    )
    parser.add_argument("--session-date", type=date.fromisoformat, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger = _load(args.ledger)
    validate_industry_source_ledger(ledger)
    session_text = args.session_date.isoformat()

    if session_ready_observed(ledger, session_text):
        summary = industry_readiness_summary(ledger)
        _write_json(args.summary, summary)
        print(
            json.dumps(
                {
                    "state": "SESSION_READY_ALREADY_OBSERVED",
                    "session_date": session_text,
                    "changed": False,
                    "summary_sha256": summary["summary_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0

    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    constituent_raw = fetch(SOURCE_URL)
    security_url = security_master_url(args.session_date)
    security_raw = fetch(security_url)
    captured = datetime.now(UTC)

    updated, attempt, snapshot = append_industry_source_probe(
        ledger,
        session_date=session_text,
        captured_at_utc=captured.isoformat(),
        constituent_raw=constituent_raw,
        security_raw=security_raw,
        security_source_url=security_url,
    )
    if attempt is None:
        raise RuntimeError("RM001-SC002 unexpectedly returned no attempt")

    if constituent_raw is not None:
        path = Path(str(attempt["constituent_raw_repo_path"]))
        if sha256_bytes(constituent_raw) != attempt["constituent_raw_sha256"]:
            raise RuntimeError("RM001-SC002 constituent raw SHA mismatch")
        _write_exact(path, constituent_raw)

    if security_raw is not None:
        path = Path(str(attempt["security_raw_repo_path"]))
        if sha256_bytes(security_raw) != attempt["security_raw_sha256"]:
            raise RuntimeError("RM001-SC002 security raw SHA mismatch")
        _write_exact(path, security_raw)

    if snapshot is not None:
        snapshot_path = Path(str(attempt["industry_snapshot_repo_path"]))
        snapshot_bytes = canonical_gzip_json(snapshot)
        _write_exact(snapshot_path, snapshot_bytes)

    _write_json(args.ledger, updated)
    validate_industry_source_ledger(updated)
    summary = industry_readiness_summary(updated)
    _write_json(args.summary, summary)

    print(
        json.dumps(
            {
                "state": "CAPTURED",
                "changed": True,
                "session_date": session_text,
                "captured_at_utc": attempt["captured_at_utc"],
                "source_status": attempt["source_status"],
                "ready_before_cutoff": attempt["ready_before_cutoff"],
                "projected_eq_row_count": attempt["projected_eq_row_count"],
                "industry_label_count": attempt["industry_label_count"],
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
