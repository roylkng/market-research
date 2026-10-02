from __future__ import annotations

import argparse
import hashlib
import json
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

ARCHIVES = {
    "FY2023-24": (
        "https://nsearchives.nseindia.com/web/sites/default/files/"
        "inline-files/BRSR_Data_Dump.zip"
    ),
    "FY2024-25": (
        "https://nsearchives.nseindia.com/web/mediaattachment/2026-04/"
        "BRSR_DUMP_FY24-25_20260414130852.zip"
    ),
}
ALLOWED_HOSTS = {"nsearchives.nseindia.com"}
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
            if host not in ALLOWED_HOSTS:
                raise RuntimeError(
                    f"D010 C0 redirect escaped frozen host: {response.url}"
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
    raise RuntimeError(f"D010 C0 failed to fetch {url}: {last}")


def _inventory(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        rows = []
        suffix_counts: dict[str, int] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            raw = archive.read(info.filename)
            suffix = Path(info.filename).suffix.lower() or "<none>"
            suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
            rows.append(
                {
                    "path": info.filename,
                    "size_bytes": info.file_size,
                    "compressed_size_bytes": info.compress_size,
                    "suffix": suffix,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "zip_like": suffix
                    in {".zip", ".xlsx", ".xlsm", ".xltx", ".xltm"},
                }
            )
    return {
        "member_count": len(rows),
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "members": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory frozen RM001 D010 annual BRSR archives"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for year, url in ARCHIVES.items():
        raw, metadata = _fetch(
            url,
            attempts=args.attempts,
            timeout=args.timeout_seconds,
        )
        sha = hashlib.sha256(raw).hexdigest()
        raw_path = args.output / "raw" / f"{year}-{sha}.zip"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw)
        report = {
            "year": year,
            "url": url,
            "raw_sha256": sha,
            "size_bytes": len(raw),
            "fetch": metadata,
            **_inventory(raw_path),
        }
        reports[year] = report
        _write(args.output / f"{year}-inventory.json", report)

    summary = {
        "schema_version": 1,
        "diagnostic_id": "RM001-D010-C0-v1",
        "parent_phase_ab_run_id": 37007303564,
        "parent_result_sha256": (
            "64a0ec350f76ba3413d037fc8b3bd234dd9389be915032a5048f9526cd3e444b"
        ),
        "archives": {
            year: {
                "url": report["url"],
                "raw_sha256": report["raw_sha256"],
                "size_bytes": report["size_bytes"],
                "member_count": report["member_count"],
                "suffix_counts": report["suffix_counts"],
            }
            for year, report in reports.items()
        },
        "coverage_gates_changed": False,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "live_capital_allowed": False,
    }
    _write(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
