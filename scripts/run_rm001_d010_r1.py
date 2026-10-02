from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.rm001_d010_r1 import build_r1_report

ARCHIVES = {
    "FY2023-24": {
        "url": (
            "https://nsearchives.nseindia.com/web/sites/default/files/"
            "inline-files/BRSR_Data_Dump.zip"
        ),
        "sha256": (
            "f287b4137b662a2f1cdba54f8d3858f84f09f43e1f0702ad5b2299cde5fb16ef"
        ),
    },
    "FY2024-25": {
        "url": (
            "https://nsearchives.nseindia.com/web/mediaattachment/2026-04/"
            "BRSR_DUMP_FY24-25_20260414130852.zip"
        ),
        "sha256": (
            "c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42"
        ),
    },
}


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
        description="Run frozen RM001 D010-R1 duplicate filing semantics diagnostic"
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
    raw_by_year = {}
    source_manifest = {}

    args.output.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for year, spec in ARCHIVES.items():
        raw = fetch(spec["url"])
        if raw is None:
            raise RuntimeError(f"R1 {year} archive unavailable")
        observed = hashlib.sha256(raw).hexdigest()
        if observed != spec["sha256"]:
            raise RuntimeError(
                f"R1 {year} archive SHA mismatch: {observed}"
            )
        raw_by_year[year] = raw
        path = raw_dir / f"{year}.zip"
        path.write_bytes(raw)
        source_manifest[year] = {
            "url": spec["url"],
            "sha256": observed,
            "size_bytes": len(raw),
            "path": str(path),
        }

    report = build_r1_report(
        fy2023_24_raw=raw_by_year["FY2023-24"],
        fy2024_25_raw=raw_by_year["FY2024-25"],
    )
    report["source_manifest"] = source_manifest
    _write_json(args.output / "report.json", report)

    summary = {
        "schema_version": 1,
        "diagnostic_id": report["diagnostic_id"],
        "status": report["status"],
        "result_sha256": report["result_sha256"],
        "d010_status_changed": report["d010_status_changed"],
        "d011_authorized": report["d011_authorized"],
        "d012_authorized": report["d012_authorized"],
        "failure_reasons": report["failure_reasons"],
        "years": {
            year: {
                key: value
                for key, value in year_report.items()
                if key
                in {
                    "duplicate_group_count",
                    "duplicate_filing_record_count",
                    "excess_duplicate_record_count",
                    "deterministic_amendment_group_count",
                    "deterministic_amendment_group_fraction",
                    "duplicate_filing_parseable_timestamp_fraction",
                    "duplicate_filing_explicit_nic_fraction",
                    "timestamp_collision_group_count",
                    "reporting_period_conflict_group_count",
                    "symbol_change_group_count",
                    "nic_change_group_count",
                    "app_id_identity_conflict_count",
                    "orphan_product_row_count",
                    "gates",
                    "year_pass",
                }
            }
            for year, year_report in report["years"].items()
        },
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
