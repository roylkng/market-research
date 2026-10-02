from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests

from marketlab.alpha import AlphaContractError
from marketlab.nse import NSEAcquisitionError, NSEClient, NSEEndpoint
from marketlab.rm001_d013 import (
    FY_ARCHIVES,
    deterministic_public_time_sample,
    parse_brsr_archive,
)
from marketlab.rm001_d013_r1 import (
    BRSR_PAGE_URL,
    build_r1_report,
    discover_brsr_api_candidates,
    evaluate_endpoint_correspondence,
    extract_first_party_script_urls,
    structurally_eligible_rows,
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


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _get_bytes(
    client: NSEClient,
    url: str,
    *,
    accept: str,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, client.attempts + 1):
        try:
            if not client._session_initialized:
                client._initialize_session()
            response = client.session.get(
                url,
                headers={
                    "Accept": accept,
                    "Referer": BRSR_PAGE_URL,
                },
                timeout=client.timeout,
            )
            if response.status_code in {401, 403}:
                client._session_initialized = False
                if attempt < client.attempts:
                    time.sleep(0.25 * attempt)
                    continue
            if (
                response.status_code == 429
                or response.status_code >= 500
            ) and attempt < client.attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            if not response.content:
                raise NSEAcquisitionError(
                    f"D013-R1 empty source bytes: {url}"
                )
            return response.content
        except (requests.RequestException, NSEAcquisitionError) as exc:
            last_error = exc
            if attempt < client.attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
                continue
            break
    raise NSEAcquisitionError(
        f"D013-R1 source fetch failed {url}: {last_error}"
    ) from last_error


def _sample(archives: dict[str, bytes]) -> list[dict]:
    filings = []
    for year in sorted(FY_ARCHIVES):
        expected = FY_ARCHIVES[year]["sha256"]
        observed = _sha256(archives[year])
        if observed != expected:
            raise AlphaContractError(
                f"D013-R1 {year} archive SHA mismatch: {observed}"
            )
        parsed = parse_brsr_archive(
            year=year,
            raw=archives[year],
        )
        filings.extend(parsed["filings"])
    return deterministic_public_time_sample(filings)


def _query_variants(
    *,
    symbol: str,
    from_date: str,
    to_date: str,
) -> list[dict[str, str]]:
    return [
        {
            "index": "equities",
            "symbol": symbol,
            "from_date": from_date,
            "to_date": to_date,
        },
        {
            "symbol": symbol,
            "from_date": from_date,
            "to_date": to_date,
        },
        {
            "index": "equities",
            "from_date": from_date,
            "to_date": to_date,
        },
        {
            "from_date": from_date,
            "to_date": to_date,
        },
    ]


def _query_endpoint_for_sample(
    *,
    client: NSEClient,
    endpoint_path: str,
    filing: dict,
    response_root: Path,
    pause_seconds: float,
) -> tuple[list[dict], dict]:
    parsed = datetime.fromisoformat(
        str(filing["submission_timestamp_parsed"])
    )
    day = parsed.date()
    from_date = (day - timedelta(days=1)).strftime("%d-%m-%Y")
    to_date = (day + timedelta(days=1)).strftime("%d-%m-%Y")
    endpoint = NSEEndpoint(
        name=f"d013_r1:{endpoint_path}",
        url=urljoin(client.BASE_URL, endpoint_path),
    )

    successes = []
    failures = []
    selected_rows: list[dict] = []
    selected_variant = None

    for index, params in enumerate(
        _query_variants(
            symbol=str(filing["symbol"]),
            from_date=from_date,
            to_date=to_date,
        ),
        start=1,
    ):
        try:
            payload, raw = client._json_get_with_raw(
                endpoint,
                params=params,
            )
        except NSEAcquisitionError as exc:
            failures.append(
                {
                    "variant": index,
                    "params": params,
                    "error": str(exc),
                }
            )
            if pause_seconds:
                time.sleep(pause_seconds)
            continue

        raw_sha = _sha256(raw)
        rows = structurally_eligible_rows(payload)
        target = (
            response_root
            / filing["sample_score"]
            / f"variant-{index}-{raw_sha}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        successes.append(
            {
                "variant": index,
                "params": params,
                "raw_sha256": raw_sha,
                "response_path": str(target),
                "recursive_structural_row_count": len(rows),
            }
        )
        if rows:
            selected_rows = rows
            selected_variant = index
            break
        if pause_seconds:
            time.sleep(pause_seconds)

    return selected_rows, {
        "selected_variant": selected_variant,
        "successful_responses": successes,
        "failed_variants": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen RM001 D013-R1 dedicated BRSR source correspondence"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    raw_root = args.output / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)

    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    client.session.headers["Referer"] = BRSR_PAGE_URL

    archives = {}
    archive_manifest = {}
    for year in sorted(FY_ARCHIVES):
        url = FY_ARCHIVES[year]["url"]
        raw = client.archive_bytes(url)
        archives[year] = raw
        sha = _sha256(raw)
        archive_path = raw_root / "archives" / f"{year}-{sha}.zip"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(raw)
        archive_manifest[year] = {
            "url": url,
            "raw_sha256": sha,
            "path": str(archive_path),
        }

    sample = _sample(archives)

    page_raw = _get_bytes(
        client,
        BRSR_PAGE_URL,
        accept="text/html,application/xhtml+xml,*/*;q=0.8",
    )
    page_sha = _sha256(page_raw)
    page_path = raw_root / "page" / f"brsr-page-{page_sha}.html"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_bytes(page_raw)

    script_urls = extract_first_party_script_urls(page_raw)
    script_bytes = {}
    script_manifest = []
    script_failures = []
    for script_url in script_urls:
        try:
            raw = _get_bytes(
                client,
                script_url,
                accept="application/javascript,text/javascript,*/*;q=0.8",
            )
        except NSEAcquisitionError as exc:
            script_failures.append(
                {
                    "url": script_url,
                    "error": str(exc),
                }
            )
            continue
        sha = _sha256(raw)
        script_path = raw_root / "scripts" / f"{sha}.js"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        if script_path.exists() and script_path.read_bytes() != raw:
            raise AlphaContractError(
                f"D013-R1 script hash path collision: {script_path}"
            )
        script_path.write_bytes(raw)
        script_bytes[script_url] = raw
        script_manifest.append(
            {
                "url": script_url,
                "raw_sha256": sha,
                "path": str(script_path),
                "byte_count": len(raw),
            }
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    candidates = discover_brsr_api_candidates(script_bytes)
    endpoint_reports = []
    query_source_manifest = []

    for candidate in candidates:
        endpoint_path = str(candidate["endpoint_path"])
        endpoint_hash = hashlib.sha256(
            endpoint_path.encode("utf-8")
        ).hexdigest()
        response_root = (
            raw_root / "responses" / endpoint_hash
        )
        rows_by_sample = {}
        metadata_by_sample = {}

        for filing in sample:
            rows, metadata = _query_endpoint_for_sample(
                client=client,
                endpoint_path=endpoint_path,
                filing=filing,
                response_root=response_root,
                pause_seconds=args.pause_seconds,
            )
            rows_by_sample[filing["sample_score"]] = rows
            metadata_by_sample[filing["sample_score"]] = metadata

        endpoint_report = evaluate_endpoint_correspondence(
            endpoint_path=endpoint_path,
            sample=sample,
            rows_by_sample=rows_by_sample,
            query_metadata_by_sample=metadata_by_sample,
        )
        endpoint_reports.append(endpoint_report)
        query_source_manifest.append(
            {
                "endpoint_path": endpoint_path,
                "endpoint_hash": endpoint_hash,
                "sample_queries": metadata_by_sample,
            }
        )

    report = build_r1_report(
        archives=archives,
        page_url=BRSR_PAGE_URL,
        page_sha256=page_sha,
        script_sources=script_manifest,
        candidates=candidates,
        endpoint_reports=endpoint_reports,
    )

    source_manifest = {
        "schema_version": 1,
        "diagnostic_id": report["diagnostic_id"],
        "page": {
            "url": BRSR_PAGE_URL,
            "raw_sha256": page_sha,
            "path": str(page_path),
        },
        "archives": archive_manifest,
        "script_url_count": len(script_urls),
        "script_ready_count": len(script_manifest),
        "script_failures": script_failures,
        "scripts": script_manifest,
        "candidate_endpoint_count": len(candidates),
        "candidate_endpoints": [
            row["endpoint_path"] for row in candidates
        ],
        "query_sources": query_source_manifest,
        "live_capital_allowed": False,
    }

    _write_json(args.output / "source-manifest.json", source_manifest)
    _write_json(args.output / "report.json", report)

    endpoint_summary = []
    for row in endpoint_reports:
        endpoint_summary.append(
            {
                key: value
                for key, value in row.items()
                if key != "rows"
            }
        )
    summary = {
        "schema_version": 1,
        "diagnostic_id": report["diagnostic_id"],
        "status": report["status"],
        "result_sha256": report["result_sha256"],
        "sample_count": report["sample_count"],
        "page_sha256": page_sha,
        "script_ready_count": len(script_manifest),
        "candidate_endpoint_count": len(candidates),
        "passing_endpoint_paths": report["passing_endpoint_paths"],
        "endpoint_reports": endpoint_summary,
        "d013_r2_authorized": report["d013_r2_authorized"],
        "d013_status_changed": False,
        "d013_multi_nic_failure_resolved": False,
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
