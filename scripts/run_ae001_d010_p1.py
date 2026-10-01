from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from marketlab.alpha_d010_p1 import (
    DAILY_REPORT_KEYS,
    PROBE_DATES,
    extract_daily_report_metadata,
    metadata_probe_from_raw,
    short_archive_url,
    summarize_p1,
)
from marketlab.alpha_d010_sources import (
    ProbeResponse,
    inspect_csv_response,
)
from marketlab.nse import NSEAcquisitionError, NSEClient

USER_AGENT = "Mozilla/5.0 MarketLab-AE001-D010-P1/1.0"


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
        description="Run frozen AE001 D010 P1 archive resolution"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_root = args.output / "raw"

    short_attempts = []
    with requests.Session() as session:
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/csv,text/plain,*/*",
            }
        )
        for probe_date in PROBE_DATES:
            url = short_archive_url(probe_date)
            try:
                response = session.get(
                    url,
                    timeout=args.timeout_seconds,
                    allow_redirects=False,
                )
                probe = ProbeResponse(
                    status_code=response.status_code,
                    content_type=response.headers.get(
                        "Content-Type",
                        "",
                    ),
                    body=response.content,
                )
                inspected = inspect_csv_response(probe, url=url)
            except requests.RequestException as exc:
                inspected = {
                    "url": url,
                    "status_code": None,
                    "content_type": "",
                    "byte_length": 0,
                    "raw_sha256": None,
                    "header": None,
                    "data_row_count": None,
                    "status": "REQUEST_ERROR",
                    "error": type(exc).__name__,
                }
                response = None

            short_attempts.append(
                {
                    "session_date": probe_date.isoformat(),
                    "response": inspected,
                }
            )
            if inspected["status"] == "READY" and response is not None:
                path = (
                    raw_root
                    / "cm_short_selling"
                    / probe_date.isoformat()
                    / f"{inspected['raw_sha256']}.csv"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                if (
                    path.exists()
                    and path.read_bytes() != response.content
                ):
                    raise RuntimeError(
                        f"D010 P1 short raw path collision: {path}"
                    )
                path.write_bytes(response.content)

    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=3,
    )
    metadata_results = []
    for key in DAILY_REPORT_KEYS:
        try:
            payload, raw = client.daily_reports_with_raw(key)
        except NSEAcquisitionError as exc:
            metadata_results.append(
                {
                    "key": key,
                    "raw_sha256": None,
                    "matched_object_count": 0,
                    "matches": [],
                    "status": "REQUEST_ERROR",
                    "error": str(exc),
                }
            )
            continue
        probe = metadata_probe_from_raw(
            key=key,
            raw=raw,
            payload=payload,
        )
        result = extract_daily_report_metadata(probe)
        result["status"] = "READY"
        metadata_results.append(result)
        path = raw_root / "daily_reports_metadata" / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    report = summarize_p1(
        short_attempts=short_attempts,
        metadata_results=metadata_results,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    _write_json(args.output / "report.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
