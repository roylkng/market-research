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
        raise RuntimeError("R2 frozen FY2024-25 archive unavailable")
    observed = hashlib.sha256(raw).hexdigest()
    if observed != ARCHIVE_SHA256:
        raise RuntimeError(f"R2 archive SHA mismatch: {observed}")

    args.output.mkdir(parents=True, exist_ok=True)
    raw_path = args.output / "raw" / "FY2024-25.zip"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)

    report = build_r2_report(fy2024_25_raw=raw)
    report["source_manifest"] = {
        "url": ARCHIVE_URL,
        "sha256": observed,
        "size_bytes": len(raw),
        "path": str(raw_path),
    }
    _write_json(args.output / "report.json", report)

    year = report["year_report"]
    summary = {
        "schema_version": 1,
        "diagnostic_id": report["diagnostic_id"],
        "status": report["status"],
        "result_sha256": report["result_sha256"],
        "d010_status_changed": report["d010_status_changed"],
        "r1_status_changed": report["r1_status_changed"],
        "d013_authorized": report["d013_authorized"],
        "failure_reasons": report["failure_reasons"],
        "cross_period_conflict_group_count": year[
            "cross_period_conflict_group_count"
        ],
        "cross_period_filing_record_count": year[
            "cross_period_filing_record_count"
        ],
        "parseable_period_record_fraction": year[
            "parseable_period_record_fraction"
        ],
        "explicit_nic_record_fraction": year[
            "explicit_nic_record_fraction"
        ],
        "overlapping_period_pair_count": year[
            "overlapping_period_pair_count"
        ],
        "deterministic_period_partition_group_count": year[
            "deterministic_period_partition_group_count"
        ],
        "deterministic_period_partition_group_fraction": year[
            "deterministic_period_partition_group_fraction"
        ],
        "target_period_group_count": year["target_period_group_count"],
        "target_period_record_count": year["target_period_record_count"],
        "app_id_identity_conflict_count": year[
            "app_id_identity_conflict_count"
        ],
        "gates": year["gates"],
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
