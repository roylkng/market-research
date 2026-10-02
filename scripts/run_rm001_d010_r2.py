from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.rm001_d010_r2 import build_r2_report

ARCHIVE_URL = (
    "https://nsearchives.nseindia.com/web/mediaattachment/2026-04/"
    "BRSR_DUMP_FY24-25_20260414130852.zip"
)
ARCHIVE_SHA256 = (
    "c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42"
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
        description="Run frozen RM001 D010-R2 cross-period semantics diagnostic"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    raw = fetch(ARCHIVE_URL)
    if raw is None:
        raise RuntimeError("R2 FY2024-25 archive unavailable")
    observed = hashlib.sha256(raw).hexdigest()
    if observed != ARCHIVE_SHA256:
        raise RuntimeError(
            f"R2 FY2024-25 archive SHA mismatch: {observed}"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    raw_path = args.output / "raw" / "FY2024-25.zip"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)

    report = build_r2_report(fy2024_25_raw=raw)
    report["source_manifest"] = {
        "FY2024-25": {
            "url": ARCHIVE_URL,
            "sha256": observed,
            "size_bytes": len(raw),
            "path": str(raw_path),
        }
    }
    _write_json(args.output / "report.json", report)

    summary = {
        key: value
        for key, value in report.items()
        if key
        not in {
            "candidates",
            "source_manifest",
        }
    }
    summary["candidate_summaries"] = [
        {
            "stable_identity": candidate["stable_identity"],
            "filing_count": candidate["filing_count"],
            "distinct_period_count": candidate["distinct_period_count"],
            "symbols": candidate["symbols"],
            "symbol_changed": candidate["symbol_changed"],
            "nic_changed_between_periods": candidate[
                "nic_changed_between_periods"
            ],
            "gates": candidate["gates"],
            "candidate_pass": candidate["candidate_pass"],
            "periods": candidate["periods"],
        }
        for candidate in report["candidates"]
    ]
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
