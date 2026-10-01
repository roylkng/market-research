from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from marketlab.alpha_d010_sources import (
    PROBE_DATES,
    SOURCE_FAMILIES,
    ProbeResponse,
    inspect_csv_response,
    render_url,
    summarize_discovery,
)

USER_AGENT = "Mozilla/5.0 MarketLab-AE001-D010/1.0"


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
        description="Run frozen AE001 D010 source discovery"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    attempts = []
    raw_root = args.output / "raw"

    with requests.Session() as session:
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/csv,text/plain,*/*",
            }
        )
        for family, patterns in SOURCE_FAMILIES.items():
            for pattern_index, pattern in enumerate(patterns):
                for probe_date in PROBE_DATES:
                    url = render_url(pattern, probe_date)
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
                    except requests.RequestException as exc:
                        attempts.append(
                            {
                                "family": family,
                                "pattern_index": pattern_index,
                                "session_date": probe_date.isoformat(),
                                "response": {
                                    "url": url,
                                    "status_code": None,
                                    "content_type": "",
                                    "byte_length": 0,
                                    "raw_sha256": None,
                                    "header": None,
                                    "data_row_count": None,
                                    "status": "REQUEST_ERROR",
                                    "error": type(exc).__name__,
                                },
                            }
                        )
                        continue

                    inspected = inspect_csv_response(probe, url=url)
                    attempts.append(
                        {
                            "family": family,
                            "pattern_index": pattern_index,
                            "session_date": probe_date.isoformat(),
                            "response": inspected,
                        }
                    )
                    if inspected["status"] == "READY":
                        raw_sha = inspected["raw_sha256"]
                        raw_path = (
                            raw_root
                            / family.lower()
                            / probe_date.isoformat()
                            / f"{raw_sha}.csv"
                        )
                        raw_path.parent.mkdir(parents=True, exist_ok=True)
                        if (
                            raw_path.exists()
                            and raw_path.read_bytes() != probe.body
                        ):
                            raise RuntimeError(
                                f"D010 raw path collision: {raw_path}"
                            )
                        raw_path.write_bytes(probe.body)

    report = summarize_discovery(attempts)
    args.output.mkdir(parents=True, exist_ok=True)
    _write_json(args.output / "attempts.json", attempts)
    _write_json(args.output / "report.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
