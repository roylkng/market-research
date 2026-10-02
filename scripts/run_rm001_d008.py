from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

from marketlab.rm001_d008 import analyze_monthly_workbook, summarize_d008

SOURCES = (
    (
        "2025-09",
        "https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Exchange_Data_CM_Segment_Sept%2725.xlsx",
    ),
    (
        "2025-12",
        "https://nsearchives.nseindia.com/web/mediaattachment/2026-01/Exchange_Data_CM_Segment_20260112185218.xlsx",
    ),
    (
        "2026-01",
        "https://nsearchives.nseindia.com/web/mediaattachment/2026-02/Exchange_Data_CM_Segment_Jan2026_20260217133015.xlsx",
    ),
    (
        "2026-08",
        "https://nsearchives.nseindia.com/web/mediaattachment/2026-09/Exchange_Data_CM_Segment_Aug26_20260911134110.xlsx",
    ),
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


def _fetch(url: str, *, attempts: int, timeout_seconds: float) -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 MarketLab-RM001-D008/1.0",
        "Referer": "https://www.nseindia.com/",
    }
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            raw = response.content
            if len(raw) < 4 or raw[:2] != b"PK":
                raise RuntimeError(
                    f"source is not XLSX ZIP: status={response.status_code} "
                    f"bytes={len(raw)}"
                )
            return raw
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(float(attempt))
    raise RuntimeError(f"D008 source fetch failed: {url}: {last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen RM001 D008 monthly sector-source feasibility scan"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.raw_dir.mkdir(parents=True, exist_ok=True)

    reports = []
    for month, url in SOURCES:
        raw = _fetch(
            url,
            attempts=args.attempts,
            timeout_seconds=args.timeout_seconds,
        )
        raw_path = args.raw_dir / f"exchange-monthly-{month}.xlsx"
        if raw_path.exists() and raw_path.read_bytes() != raw:
            raise RuntimeError(f"D008 raw path collision: {raw_path}")
        raw_path.write_bytes(raw)

        report = analyze_monthly_workbook(
            raw,
            month=month,
            source_url=url,
        )
        reports.append(report)
        _write_json(args.output / f"workbook-{month}.json", report)
        print(
            json.dumps(
                {
                    "month": month,
                    "source_sha256": report["source_sha256"],
                    "sheet_count": report["sheet_count"],
                    "candidate_count": report["candidate_count"],
                    "passing_candidate_count": report["passing_candidate_count"],
                    "source_candidate_pass": report["source_candidate_pass"],
                },
                sort_keys=True,
            )
        )

    summary = summarize_d008(reports)
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
