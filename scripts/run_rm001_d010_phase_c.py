from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from marketlab.rm001_d010 import build_d010_phase_c_report

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
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
)


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


def _fetch(url: str, *, attempts: int, timeout: float) -> tuple[bytes, dict]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        }
    )
    last = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                url,
                timeout=timeout,
                allow_redirects=True,
            )
            response.raise_for_status()
            host = (urlparse(response.url).hostname or "").lower()
            if host != "nsearchives.nseindia.com":
                raise RuntimeError(
                    f"D010 Phase C redirect escaped frozen host: {response.url}"
                )
            return response.content, {
                "requested_url": url,
                "final_url": response.url,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "content_length_header": response.headers.get("content-length"),
                "redirect_history": [
                    {
                        "status_code": item.status_code,
                        "url": item.url,
                        "location": item.headers.get("location"),
                    }
                    for item in response.history
                ],
            }
        except (requests.RequestException, RuntimeError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(float(attempt))
    raise RuntimeError(f"D010 Phase C failed to fetch {url}: {last}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen RM001 D010 BRSR Phase C coverage diagnostic"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    raw_by_year = {}
    fetch_evidence = {}
    for year, spec in ARCHIVES.items():
        raw, metadata = _fetch(
            spec["url"],
            attempts=args.attempts,
            timeout=args.timeout_seconds,
        )
        observed = hashlib.sha256(raw).hexdigest()
        if observed != spec["sha256"]:
            raise RuntimeError(
                f"D010 {year} archive SHA changed: {observed} != {spec['sha256']}"
            )
        raw_by_year[year] = raw
        raw_path = args.output / "raw" / f"{year}-{observed}.zip"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw)
        fetch_evidence[year] = {
            **metadata,
            "sha256": observed,
            "size_bytes": len(raw),
            "retained_path": str(raw_path),
        }

    report = build_d010_phase_c_report(
        fy2023_24_raw=raw_by_year["FY2023-24"],
        fy2024_25_raw=raw_by_year["FY2024-25"],
    )
    report["fetch_evidence"] = fetch_evidence
    _write(args.output / "phase-c-report.json", report)

    summary = {
        "schema_version": 1,
        "diagnostic_id": report["diagnostic_id"],
        "status": report["status"],
        "result_sha256": report["result_sha256"],
        "coverage_gates_pass": report["coverage_gates_pass"],
        "nic_semantics_compatible": report["nic_semantics_compatible"],
        "equal_required_year_entity_counts": (
            report["equal_required_year_entity_counts"]
        ),
        "fixed_cap_gate_status": report["fixed_cap_gate_status"],
        "d011_authorized": report["d011_authorized"],
        "failure_reasons": report["failure_reasons"],
        "years": {
            year: {
                key: value
                for key, value in year_report.items()
                if key
                in {
                    "general_data_row_count",
                    "product_data_row_count",
                    "unique_entity_count",
                    "stable_identity_coverage",
                    "cin_coverage",
                    "nse_symbol_coverage",
                    "reporting_year_coverage",
                    "submission_timestamp_coverage",
                    "duplicate_identity_rate",
                    "explicit_nic_row_count",
                    "explicit_nic_entity_count",
                    "explicit_nic_coverage",
                    "multiple_nic_entity_count",
                    "turnover_weight_complete_multi_nic_entity_count",
                    "orphan_product_row_count",
                    "gates",
                    "year_gates_pass",
                    "annual_archive_sha256",
                    "general_workbook_path",
                    "product_workbook_path",
                }
            }
            for year, year_report in report["year_reports"].items()
        },
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "live_capital_allowed": False,
    }
    _write(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
