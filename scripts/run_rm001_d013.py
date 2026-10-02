from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from marketlab.alpha_acquisition import http_fetcher
from marketlab.nse import NSEClient
from marketlab.rm001_d013 import (
    FY_ARCHIVES,
    IST,
    build_d013_report,
    deterministic_public_time_sample,
    parse_brsr_archive,
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


def _retain(root: Path, label: str, raw: bytes, suffix: str) -> str:
    sha = hashlib.sha256(raw).hexdigest()
    destination = root / "raw" / f"{label}-{sha}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != raw:
            raise RuntimeError(f"D013 content-addressed collision: {destination}")
    else:
        destination.write_bytes(raw)
    return sha


def _submission_calendar_date(filing: dict) -> date:
    parsed = datetime.fromisoformat(filing["submission_timestamp_parsed"])
    if parsed.tzinfo is None:
        return parsed.date()
    return parsed.astimezone(IST).date()


def _safe_label(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value
    )[:120]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen RM001 D013 BRSR as-of timeline diagnostic"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )

    archives: dict[str, bytes] = {}
    parsed_filings = []
    archive_manifest = {}
    for year in sorted(FY_ARCHIVES):
        spec = FY_ARCHIVES[year]
        raw = client.archive_bytes(spec["url"])
        observed = hashlib.sha256(raw).hexdigest()
        if observed != spec["sha256"]:
            raise RuntimeError(
                f"D013 {year} frozen archive SHA mismatch: {observed}"
            )
        _retain(
            args.output,
            f"archive-{_safe_label(year)}",
            raw,
            ".zip",
        )
        archives[year] = raw
        parsed = parse_brsr_archive(year=year, raw=raw)
        parsed_filings.extend(parsed["filings"])
        archive_manifest[year] = {
            "url": spec["url"],
            "sha256": observed,
            "size_bytes": len(raw),
            "general_record_count": parsed["general_record_count"],
            "product_record_count": parsed["product_record_count"],
            "general_workbook_path": parsed["general_workbook_path"],
            "product_workbook_path": parsed["product_workbook_path"],
        }

    sample = deterministic_public_time_sample(parsed_filings)
    announcement_payloads = {}
    announcement_hashes = {}
    announcement_query_manifest = {}
    query_cache = {}

    for filing in sample:
        day = _submission_calendar_date(filing)
        start = day - timedelta(days=1)
        end = day + timedelta(days=1)
        cache_key = (
            filing["symbol"],
            start.isoformat(),
            end.isoformat(),
        )
        cached = query_cache.get(cache_key)
        if cached is None:
            payload, raw = client.corporate_announcements_with_raw(
                filing["symbol"],
                from_date=start.strftime("%d-%m-%Y"),
                to_date=end.strftime("%d-%m-%Y"),
            )
            raw_sha = hashlib.sha256(raw).hexdigest()
            _retain(
                args.output,
                (
                    f"announcement-{_safe_label(filing['symbol'])}-"
                    f"{start.isoformat()}-{end.isoformat()}"
                ),
                raw,
                ".json",
            )
            cached = {
                "payload": payload,
                "raw_sha256": raw_sha,
                "query": {
                    "symbol": filing["symbol"],
                    "from_date": start.isoformat(),
                    "to_date": end.isoformat(),
                },
            }
            query_cache[cache_key] = cached
            if args.pause_seconds > 0:
                time.sleep(args.pause_seconds)

        score = filing["sample_score"]
        announcement_payloads[score] = cached["payload"]
        announcement_hashes[score] = cached["raw_sha256"]
        announcement_query_manifest[score] = cached["query"]

    base_fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    security_url_hashes = {}

    def security_fetcher(url: str) -> bytes | None:
        raw = base_fetch(url)
        if raw is None:
            return None
        sha = hashlib.sha256(raw).hexdigest()
        parsed = urlparse(url)
        basename = Path(parsed.path).name or "security.csv.gz"
        _retain(
            args.output,
            f"security-{_safe_label(basename)}",
            raw,
            ".bin",
        )
        security_url_hashes[url] = sha
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)
        return raw

    report = build_d013_report(
        archives=archives,
        announcement_payloads=announcement_payloads,
        announcement_raw_sha256=announcement_hashes,
        security_fetcher=security_fetcher,
    )
    report["source_manifest"] = {
        "archives": archive_manifest,
        "announcement_queries": announcement_query_manifest,
        "security_url_sha256": dict(sorted(security_url_hashes.items())),
    }
    _write_json(args.output / "report.json", report)

    timing = report["public_time"]
    summary = {
        "schema_version": 1,
        "diagnostic_id": report["diagnostic_id"],
        "status": report["status"],
        "result_sha256": report["result_sha256"],
        "d014_authorized": report["d014_authorized"],
        "filing_count": report["filing_count"],
        "public_time_sample_count": timing["sample_count"],
        "public_time_matched_count": timing["matched_count"],
        "public_time_match_fraction_by_year": timing[
            "match_fraction_by_year"
        ],
        "ist_median_abs_delta_seconds": timing[
            "ist_median_abs_delta_seconds"
        ],
        "ist_p95_abs_delta_seconds": timing[
            "ist_p95_abs_delta_seconds"
        ],
        "utc_median_abs_delta_seconds": timing[
            "utc_median_abs_delta_seconds"
        ],
        "identity_exact_join_coverage": report["identity"][
            "exact_join_coverage"
        ],
        "identity_ambiguous_join_count": report["identity"][
            "ambiguous_join_count"
        ],
        "explicit_nic_filing_coverage": report["nic"][
            "explicit_nic_filing_coverage"
        ],
        "multi_nic_transformable_fraction": report["nic"][
            "multi_nic_transformable_fraction"
        ],
        "reporting_period_parseable_fraction": report["nic"][
            "reporting_period_parseable_fraction"
        ],
        "timeline": {
            key: value
            for key, value in report["timeline"].items()
            if key != "gates"
        },
        "gates": report["gates"],
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
