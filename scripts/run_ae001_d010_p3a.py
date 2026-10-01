from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_d010_p1 import short_archive_url
from marketlab.alpha_d010_p3a import inspect_short_raw, summarize_p3a
from marketlab.alpha_d010_sources import PROBE_DATES


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
        description="Run frozen D010 P3A short-selling parser diagnostic"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    diagnostics = []
    raw_root = args.output / "raw"
    for session_date in PROBE_DATES:
        raw = fetch(short_archive_url(session_date))
        if raw is None:
            raise RuntimeError(
                f"D010 P3A frozen short source unavailable: {session_date}"
            )
        diagnostic = inspect_short_raw(
            raw,
            session_date=session_date,
        )
        diagnostics.append(diagnostic)
        path = (
            raw_root
            / session_date.isoformat()
            / f"{diagnostic['raw_sha256']}.csv"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    report = summarize_p3a(diagnostics)
    args.output.mkdir(parents=True, exist_ok=True)
    _write_json(args.output / "report.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
