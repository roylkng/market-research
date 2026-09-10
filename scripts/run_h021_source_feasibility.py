from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ParsedConsensus:
    revenue_growth_forecast_pct: float | None
    profit_growth_estimate_pct: float | None
    analyst_count: int | None
    current_eps: float | None
    average_eps_estimate: float | None
    low_eps_estimate: float | None
    high_eps_estimate: float | None
    premium_marker: bool
    historical_point_in_time_eps_found: bool


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.replace(",", "").strip()
    try:
        return float(value)
    except ValueError:
        return None


def _search_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.I | re.S)
    return _number(match.group(1)) if match else None


def _search_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.I | re.S)
    return int(match.group(1)) if match else None


def parse_consensus_html(html: str) -> ParsedConsensus:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    revenue_growth = _search_float(r"revenue growth forecast of\s*([+-]?[0-9.,]+)%", text)
    profit_growth = _search_float(r"profit growth estimate of\s*([+-]?[0-9.,]+)%", text)
    analyst_count = _search_int(r"based on top\s*(\d+)\s*analyst calls", text)
    if analyst_count is None:
        analyst_count = _search_int(r"consensus recommendation from\s*(\d+)\s*analysts", text)
    if analyst_count is None:
        analyst_count = _search_int(r"(\d+)\s*ANALYST Recommendations", text)

    eps_block = re.search(
        r"EPS forecast(?P<body>.{0,900})",
        text,
        flags=re.I | re.S,
    )
    eps_text = eps_block.group("body") if eps_block else text
    current_eps = _search_float(r"Current EPS\s*([+-]?[0-9.,]+)", eps_text)
    average_eps = _search_float(r"Avg\.? Estimate\s*([+-]?[0-9.,]+)", eps_text)
    low_eps = _search_float(r"Low Estimate\s*([+-]?[0-9.,]+)", eps_text)
    high_eps = _search_float(r"High Estimate\s*([+-]?[0-9.,]+)", eps_text)

    premium_marker = bool(
        re.search(r"Forecaster is a Premium Feature|upgrade your subscription|premium feature", text, re.I)
    )

    # Historical point-in-time evidence requires a dated consensus value, not merely
    # a current statement that a metric changed over N days. This conservative probe
    # only marks true if a date and an EPS estimate are visibly paired in the page text.
    historical_point_in_time = bool(
        re.search(
            r"(?:20\d{2}[-/]\d{2}[-/]\d{2}|\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2}).{0,120}"
            r"(?:EPS|earnings per share).{0,80}(?:estimate|consensus).{0,40}[0-9]",
            text,
            re.I | re.S,
        )
    )

    return ParsedConsensus(
        revenue_growth_forecast_pct=revenue_growth,
        profit_growth_estimate_pct=profit_growth,
        analyst_count=analyst_count,
        current_eps=current_eps,
        average_eps_estimate=average_eps,
        low_eps_estimate=low_eps,
        high_eps_estimate=high_eps,
        premium_marker=premium_marker,
        historical_point_in_time_eps_found=historical_point_in_time,
    )


def _fetch(session: requests.Session, url: str, timeout: float) -> dict[str, Any]:
    captured_at = datetime.now(UTC).isoformat()
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        return {
            "url": url,
            "captured_at_utc": captured_at,
            "fetch_state": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
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
    }
    if response.ok and "text/html" in (response.headers.get("content-type") or ""):
        record["parsed"] = asdict(parse_consensus_html(response.text))
    return record


def _company_urls(row: dict[str, Any]) -> list[tuple[str, str]]:
    stock_id = row["trendlyne_id"]
    symbol = row.get("source_symbol", row["symbol"])
    slug = row["slug"]
    return [
        (
            "overview",
            f"https://trendlyne.com/equity/{stock_id}/{symbol}/{slug}/",
        ),
        (
            "consensus",
            f"https://trendlyne.com/equity/consensus-estimates/{stock_id}/{symbol}/{slug}/",
        ),
    ]


def _write_markdown(report: dict[str, Any], output: Path) -> None:
    lines = [
        "# H021 source feasibility probe v1",
        "",
        f"Captured: **{report['captured_at_utc']}**",
        "",
        "**SOURCE FEASIBILITY ONLY. NO RETURN OUTCOMES OPENED. LIVE CAPITAL DISABLED.**",
        "",
        f"Historical backtest allowed: **{str(report['decision']['historical_backtest_allowed']).upper()}**",
        f"Automated current-snapshot Stage A: **{report['decision']['automated_current_snapshot_status']}**",
        "",
        "| Symbol | Current consensus captured | Analyst count | EPS estimate | Premium marker | HTTP states |",
        "|---|---|---:|---:|---|---|",
    ]
    for company in report["companies"]:
        chosen = company.get("best_public_snapshot") or {}
        parsed = chosen.get("parsed") or {}
        states = ", ".join(
            f"{item['kind']}:{item.get('status_code', item.get('fetch_state'))}" for item in company["fetches"]
        )
        lines.append(
            "| {symbol} | {captured} | {analysts} | {eps} | {premium} | {states} |".format(
                symbol=company["symbol"],
                captured="yes" if company["current_consensus_captured"] else "no",
                analysts=parsed.get("analyst_count") if parsed.get("analyst_count") is not None else "",
                eps=parsed.get("average_eps_estimate") if parsed.get("average_eps_estimate") is not None else "",
                premium="yes" if parsed.get("premium_marker") else "no",
                states=states,
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            report["decision"]["reason"],
            "",
            "No historical H021 return test may be run from this probe unless actual dated consensus snapshots are independently verified.",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(cohort_path: Path, out_dir: Path, sleep_seconds: float, timeout: float) -> dict[str, Any]:
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "marketlab-h021-source-feasibility/1.0 (+research-only; low-rate)",
            "Accept": "text/html,application/xhtml+xml",
        }
    )

    companies: list[dict[str, Any]] = []
    historical_verified_count = 0
    current_captured_count = 0

    for row in cohort["companies"]:
        fetches: list[dict[str, Any]] = []
        best: dict[str, Any] | None = None
        for kind, url in _company_urls(row):
            result = _fetch(session, url, timeout)
            result["kind"] = kind
            fetches.append(result)
            raw_record = raw_dir / f"{row['symbol']}-{kind}.json"
            raw_record.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            parsed = result.get("parsed") or {}
            if result.get("fetch_state") == "OK" and (
                parsed.get("average_eps_estimate") is not None
                or parsed.get("revenue_growth_forecast_pct") is not None
                or parsed.get("profit_growth_estimate_pct") is not None
                or parsed.get("analyst_count") is not None
            ):
                if best is None or kind == "overview":
                    best = result
            if parsed.get("historical_point_in_time_eps_found"):
                historical_verified_count += 1
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        current_captured = best is not None
        current_captured_count += int(current_captured)
        companies.append(
            {
                "symbol": row["symbol"],
                "trendlyne_id": row["trendlyne_id"],
                "fetches": fetches,
                "best_public_snapshot": best,
                "current_consensus_captured": current_captured,
            }
        )

    cohort_size = len(companies)
    all_current = current_captured_count == cohort_size
    historical_allowed = historical_verified_count == cohort_size and cohort_size > 0

    if historical_allowed:
        historical_reason = (
            "All frozen probe companies exposed dated historical EPS-consensus evidence. "
            "A separate retention/timestamp audit is still required before outcomes are opened."
        )
    else:
        historical_reason = (
            "Historical H021 backtesting is BLOCKED. The public probe did not independently verify "
            "actual dated historical EPS-consensus snapshots for every frozen company. A current "
            "30/90-day change or vendor claim of historical availability is not treated as a past snapshot."
        )

    current_status = "PASS" if all_current else "FAIL"
    reason = (
        f"{historical_reason} Automated current consensus capture was {current_status.lower()} "
        f"for {current_captured_count}/{cohort_size} frozen companies. "
        "If automated current capture is incomplete or terms/access are unclear, use prospective "
        "browser-assisted/manual capture with immutable timestamps rather than bypassing access controls."
    )

    report = {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "cohort_path": str(cohort_path),
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "companies": companies,
        "summary": {
            "cohort_size": cohort_size,
            "current_consensus_captured_count": current_captured_count,
            "historical_point_in_time_eps_evidence_count": historical_verified_count,
        },
        "decision": {
            "historical_backtest_allowed": historical_allowed,
            "automated_current_snapshot_status": current_status,
            "reason": reason,
        },
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(report, out_dir / "report.md")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--sleep-seconds", type=float, default=1.5)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    report = run(args.cohort, args.out_dir, args.sleep_seconds, args.timeout)
    print(json.dumps(report["summary"], sort_keys=True))
    print(report["decision"]["reason"])


if __name__ == "__main__":
    main()
