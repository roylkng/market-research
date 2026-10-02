from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from marketlab.rm001_d010 import (
    ALLOWED_HOSTS,
    COMPLIANCE_PAGE,
    FILINGS_PAGE,
    TAXONOMY_ARCHIVE_URL,
    TAXONOMY_URL,
    UTILITY_URL,
    SourceBytes,
    build_d010_phase_ab_report,
    html_link_inventory,
)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
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


class Fetcher:
    def __init__(self, *, attempts: int, timeout: float) -> None:
        self.attempts = attempts
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.nseindia.com/",
            }
        )
        try:
            self.session.get(
                "https://www.nseindia.com/",
                timeout=self.timeout,
            )
        except requests.RequestException:
            pass

    def get(self, url: str) -> tuple[bytes, dict[str, object]]:
        host = (urlparse(url).hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            raise ValueError(f"D010 source host is not frozen/allowed: {host}")
        last: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                final_host = (
                    urlparse(response.url).hostname or ""
                ).lower()
                if final_host not in ALLOWED_HOSTS:
                    raise ValueError(
                        f"D010 redirect escaped allowed hosts: {response.url}"
                    )
                metadata = {
                    "requested_url": url,
                    "final_url": response.url,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "content_length_header": response.headers.get(
                        "content-length"
                    ),
                    "redirect_history": [
                        {
                            "status_code": item.status_code,
                            "url": item.url,
                            "location": item.headers.get("location"),
                        }
                        for item in response.history
                    ],
                }
                return response.content, metadata
            except (requests.RequestException, ValueError) as exc:
                last = exc
                if attempt < self.attempts:
                    time.sleep(float(attempt))
        raise RuntimeError(f"D010 failed to fetch {url}: {last}")


def _retain(
    *,
    output: Path,
    label: str,
    url: str,
    raw: bytes,
    metadata: dict[str, object],
) -> SourceBytes:
    sha = hashlib.sha256(raw).hexdigest()
    suffix = Path(urlparse(str(metadata["final_url"])).path).suffix or ".bin"
    path = output / "raw" / f"{label}-{sha}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    _write_json(
        output / "raw" / f"{label}-{sha}.metadata.json",
        {
            **metadata,
            "label": label,
            "sha256": sha,
            "size_bytes": len(raw),
            "retained_path": str(path),
        },
    )
    return SourceBytes(label=label, url=url, raw=raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen RM001 D010 BRSR/NIC source feasibility phases A/B"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fetch = Fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )

    fixed = {}
    for label, url in (
        ("brsr-utility", UTILITY_URL),
        ("brsr-taxonomy", TAXONOMY_URL),
        ("taxonomy-archives", TAXONOMY_ARCHIVE_URL),
        ("compliance-page", COMPLIANCE_PAGE),
        ("brsr-filings-page", FILINGS_PAGE),
    ):
        raw, metadata = fetch.get(url)
        fixed[label] = _retain(
            output=args.output,
            label=label,
            url=url,
            raw=raw,
            metadata=metadata,
        )

    page_inventories = [
        html_link_inventory(
            page_url=COMPLIANCE_PAGE,
            html_bytes=fixed["compliance-page"].raw,
        ),
        html_link_inventory(
            page_url=FILINGS_PAGE,
            html_bytes=fixed["brsr-filings-page"].raw,
        ),
    ]
    script_urls = sorted(
        {
            url
            for inventory in page_inventories
            for url in inventory["script_urls"]
        }
    )
    script_sources = []
    script_failures = []
    for index, url in enumerate(script_urls, start=1):
        try:
            raw, metadata = fetch.get(url)
        except RuntimeError as exc:
            script_failures.append(
                {
                    "url": url,
                    "error": str(exc),
                }
            )
            continue
        script_sources.append(
            _retain(
                output=args.output,
                label=f"page-script-{index:03d}",
                url=url,
                raw=raw,
                metadata=metadata,
            )
        )

    report = build_d010_phase_ab_report(
        utility=fixed["brsr-utility"],
        taxonomy=fixed["brsr-taxonomy"],
        taxonomy_archive=fixed["taxonomy-archives"],
        compliance_html=fixed["compliance-page"],
        filings_html=fixed["brsr-filings-page"],
        script_sources=script_sources,
    )
    report["script_fetch"] = {
        "referenced_script_count": len(script_urls),
        "successful_script_count": len(script_sources),
        "failure_count": len(script_failures),
        "failures": script_failures,
    }
    unsigned = dict(report)
    unsigned.pop("result_sha256", None)
    from marketlab.alpha import digest

    report["result_sha256"] = digest(unsigned)
    _write_json(args.output / "phase-ab-report.json", report)

    compact = {
        "diagnostic_id": report["diagnostic_id"],
        "phase_a_status": report["phase_a"]["status"],
        "phase_a_nic": report["phase_a"]["explicit_nic_concept_found"],
        "phase_a_identity": report["phase_a"][
            "identity_families_found"
        ],
        "phase_a_reporting_year": report["phase_a"][
            "reporting_year_concept_found"
        ],
        "phase_a_turnover_share": report["phase_a"][
            "turnover_share_concept_found"
        ],
        "phase_b_status": report["phase_b"]["status"],
        "fy2023_24_candidate_count": report["phase_b"][
            "fy2023_24_candidate_count"
        ],
        "fy2024_25_candidate_count": report["phase_b"][
            "fy2024_25_candidate_count"
        ],
        "api_candidate_count": len(
            report["discovery"]["api_candidates"]
        ),
        "direct_brsr_link_count": len(
            report["discovery"]["direct_brsr_links"]
        ),
        "script_brsr_link_count": len(
            report["discovery"]["script_brsr_links"]
        ),
        "script_fetch": report["script_fetch"],
        "phase_c_authorized": report["phase_c_authorized"],
        "result_sha256": report["result_sha256"],
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", compact)
    print(json.dumps(compact, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
