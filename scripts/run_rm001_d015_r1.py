from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.events import sha256_bytes
from marketlab.rm001_d015_r1 import (
    PARENT_RAW_SHA256,
    SECURITY_URL,
    build_d015_r1_report,
)


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
        description="Run frozen RM001 D015-R1 series-semantics diagnostic"
    )
    parser.add_argument("--parent-raw", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    parent_raw = args.parent_raw.read_bytes()
    if sha256_bytes(parent_raw) != PARENT_RAW_SHA256:
        raise RuntimeError("D015-R1 parent raw SHA mismatch")

    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    security_raw = fetch(SECURITY_URL)
    if security_raw is None:
        raise RuntimeError("D015-R1 official Security File returned 404")

    report = build_d015_r1_report(
        parent_raw=parent_raw,
        security_raw=security_raw,
    )

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    security_path = (
        args.raw_dir
        / f"security-2026-10-01-{report['security_source']['raw_sha256']}.csv.gz"
    )
    if security_path.exists() and security_path.read_bytes() != security_raw:
        raise RuntimeError(
            f"D015-R1 Security File path collision: {security_path}"
        )
    security_path.write_bytes(security_raw)
    report["security_source"]["raw_path"] = str(security_path)
    report.pop("report_sha256", None)
    from marketlab.alpha import digest

    report["report_sha256"] = digest(report)
    _write_json(args.output, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
