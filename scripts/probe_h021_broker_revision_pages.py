from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


REVISION_PATTERNS = [
    re.compile(r"revis(?:e|ed)\s+our\s+[^.]{0,180}?EPS\s+estimates?[^.]{0,180}", re.I),
    re.compile(r"EPS\s+estimates?\s+(?:upward|downward)\s+by\s+[^.]{0,120}", re.I),
    re.compile(r"(?:raise|raised|cut|lower|lowered)\s+[^.]{0,100}?EPS\s+estimates?[^.]{0,120}", re.I),
]

DATE_PATTERN = re.compile(
    r"\b(?:0?[1-9]|[12][0-9]|3[01])\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2}\b",
    re.I,
)


def extract_revision_snippets(html: str) -> list[dict[str, str | None]]:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    snippets: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for pattern in REVISION_PATTERNS:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 220)
            end = min(len(text), match.end() + 220)
            context = text[start:end].strip()
            normalized = re.sub(r"\s+", " ", match.group(0)).strip()
            if normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            date_match = DATE_PATTERN.search(context)
            snippets.append(
                {
                    "revision_text": normalized,
                    "nearby_date_text": date_match.group(0) if date_match else None,
                    "context": context,
                }
            )
    return snippets


def fetch_page(session: requests.Session, url: str, timeout: float) -> dict[str, Any]:
    captured_at = datetime.now(UTC).isoformat()
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        return {
            "url": url,
            "captured_at_utc": captured_at,
            "fetch_state": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "revision_snippets": [],
        }
    raw = response.content
    record: dict[str, Any] = {
        "url": url,
        "final_url": response.url,
        "captured_at_utc": captured_at,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "content_length": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "fetch_state": "OK" if response.ok else "HTTP_ERROR",
        "revision_snippets": [],
    }
    if response.ok and "text/html" in (response.headers.get("content-type") or ""):
        record["revision_snippets"] = extract_revision_snippets(response.text)
    return record


def run(config_path: Path, out_dir: Path, timeout: float) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "marketlab-h021-broker-source-probe/1.0 (+research-only; low-rate)",
            "Accept": "text/html,application/xhtml+xml",
        }
    )

    page_results: list[dict[str, Any]] = []
    explicit_pages = 0
    dated_snippets = 0
    total_snippets = 0
    for page in config["pages"]:
        result = fetch_page(session, page["url"], timeout)
        result["id"] = page["id"]
        result["design_evidence"] = page["design_evidence"]
        snippets = result.get("revision_snippets") or []
        total_snippets += len(snippets)
        explicit_pages += int(bool(snippets))
        dated_snippets += sum(int(bool(s.get("nearby_date_text"))) for s in snippets)
        page_results.append(result)

    # A positive source probe means only that explicit, dated revision text is retrievable.
    # It does NOT establish complete historical coverage, so no return backtest is authorized.
    retrievable = explicit_pages > 0 and dated_snippets > 0
    report = {
        "schema_version": 1,
        "hypothesis_id": "H021-B",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "pages": page_results,
        "summary": {
            "page_count": len(page_results),
            "pages_with_explicit_revision_text": explicit_pages,
            "revision_snippet_count": total_snippets,
            "dated_revision_snippet_count": dated_snippets,
        },
        "decision": {
            "explicit_broker_revision_source_retrievable": retrievable,
            "historical_backtest_allowed": False,
            "reason": (
                "Explicit dated broker EPS-revision text is retrievable from at least one frozen page, "
                "but complete report-universe coverage has not been proven. This supports building a "
                "separate source-completeness audit, not opening security-return outcomes."
                if retrievable
                else "The frozen public pages did not yield explicit dated EPS-revision text in the automated probe."
            ),
        },
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# H021-B broker revision source probe",
        "",
        f"Captured: **{report['captured_at_utc']}**",
        "",
        "**SOURCE FEASIBILITY ONLY. NO RETURN OUTCOMES OPENED. LIVE CAPITAL DISABLED.**",
        "",
        f"Pages probed: {len(page_results)}",
        f"Pages with explicit EPS revision text: {explicit_pages}",
        f"Dated revision snippets: {dated_snippets}",
        f"Historical backtest allowed: **FALSE**",
        "",
        report["decision"]["reason"],
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    report = run(args.config, args.out_dir, args.timeout)
    print(json.dumps(report["summary"], sort_keys=True))
    print(report["decision"]["reason"])


if __name__ == "__main__":
    main()
