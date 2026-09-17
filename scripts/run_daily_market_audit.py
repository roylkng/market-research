"""Run the post-close MarketLab v2 broad-market mover and discovery audit."""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests

from marketlab.intelligence_market_audit import build_market_audit
from marketlab.intelligence_market_audit_context import (
    apply_prospective_capture_context,
    inject_news_ledger,
)
from marketlab.intelligence_prospective_news import load_news_ledger
from marketlab.intelligence_store import ResearchStore, digest
from marketlab.marketdata import udiff_url

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/152.0 Safari/537.36"
)


class UDiffArchiveMissing(RuntimeError):
    """The official archive does not exist for this calendar date."""


def download_udiff(
    session_date: date,
    *,
    attempts: int = 4,
    timeout_seconds: float = 45.0,
    session: requests.Session | None = None,
) -> bytes:
    """Fetch the official NSE UDiFF archive with bounded transient retries."""
    if attempts < 1 or timeout_seconds <= 0:
        raise ValueError("invalid UDiFF fetch bounds")
    url = udiff_url(session_date)
    http = session if session is not None else requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "application/zip,*/*"})
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = http.get(url, timeout=(10, timeout_seconds))
            if response.status_code == 404:
                raise UDiffArchiveMissing(f"official NSE UDiFF archive is missing: {url}")
            if (
                response.status_code in {403, 429} or response.status_code >= 500
            ) and attempt < attempts:
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            raw = response.content
            if not raw:
                raise RuntimeError("official NSE UDiFF response is empty")
            return raw
        except UDiffArchiveMissing:
            raise
        except RuntimeError:
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            break
    raise RuntimeError(
        f"official NSE UDiFF fetch failed after {attempts} attempts: {last_error}"
    ) from last_error


def find_previous_udiff(
    session_date: date,
    *,
    attempts: int,
    timeout_seconds: float,
    max_calendar_lookback: int = 7,
) -> tuple[date, bytes]:
    """Find the immediately previous published UDiFF session without predicting holidays."""
    if max_calendar_lookback < 1:
        raise ValueError("invalid previous-session lookback")
    http = requests.Session()
    for days_back in range(1, max_calendar_lookback + 1):
        candidate = session_date - timedelta(days=days_back)
        try:
            return candidate, download_udiff(
                candidate,
                attempts=attempts,
                timeout_seconds=timeout_seconds,
                session=http,
            )
        except UDiffArchiveMissing:
            continue
    raise RuntimeError(
        f"no prior official NSE UDiFF archive within {max_calendar_lookback} calendar days"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--news-ledger", type=Path)
    parser.add_argument("--liquidity-floor-inr", type=float, default=20_000_000.0)
    parser.add_argument("--move-threshold-pct", type=float, default=5.0)
    parser.add_argument("--top-abs-movers", type=int, default=25)
    parser.add_argument("--archive-attempts", type=int, default=4)
    parser.add_argument("--archive-timeout-seconds", type=float, default=45.0)
    args = parser.parse_args()
    session_date = date.fromisoformat(args.session)
    raw = download_udiff(
        session_date,
        attempts=args.archive_attempts,
        timeout_seconds=args.archive_timeout_seconds,
    )
    prior_session_date, prior_raw = find_previous_udiff(
        session_date,
        attempts=args.archive_attempts,
        timeout_seconds=args.archive_timeout_seconds,
    )
    captured_at = datetime.now(UTC).isoformat()
    ledger = load_news_ledger(args.news_ledger) if args.news_ledger else None
    args.output.mkdir(parents=True, exist_ok=True)
    with ResearchStore(args.store) as store:
        raw_sha = store.save_object(raw)
        prior_raw_sha = store.save_object(prior_raw)
        injected = inject_news_ledger(store, ledger, as_of=captured_at) if ledger else 0
        report = build_market_audit(
            raw,
            session_date=session_date,
            prior_udiff=prior_raw,
            prior_session_date=prior_session_date,
            store=store,
            captured_at=captured_at,
            liquidity_floor_inr=args.liquidity_floor_inr,
            move_threshold_pct=args.move_threshold_pct,
            top_abs_movers=args.top_abs_movers,
        )
        if ledger:
            report = apply_prospective_capture_context(report, ledger)
        else:
            report["prospective_capture_context"] = {
                "state": "NO_CANONICAL_NEWS_LEDGER_SUPPLIED",
                "diagnostic_replay_only": True,
            }
            report.pop("report_sha256", None)
            report["report_sha256"] = digest(report)
        store.append("market_audit", report["report_sha256"], report)
    path = args.output / f"market-audit-{session_date.isoformat()}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "session_date": report["session_date"],
        "prior_session_date": report["prior_session_date"],
        "market_raw_sha256": raw_sha,
        "prior_market_raw_sha256": prior_raw_sha,
        "prospective_news_observations_injected": injected,
        "prospective_capture_context": report["prospective_capture_context"],
        "report_sha256": report["report_sha256"],
        "universe": report["universe"],
        "coverage_class_counts": report["coverage_class_counts"],
        "top_movers": [
            {
                "symbol": row["symbol"],
                "return_pct": round(row["close_return_pct"], 4),
                "turnover_inr": row["turnover_inr"],
                "coverage": row["news_audit"]["coverage_class"],
                "in_deep_panel": row["in_deep_panel"],
            }
            for row in report["movers"][:15]
        ],
        "noncomparable_liquid_top": [
            {
                "symbol": row["symbol"],
                "return_pct_vs_udiff_reference": round(
                    row["close_return_pct_vs_udiff_reference"], 4
                ),
                "reason": row["reason"],
            }
            for row in report["noncomparable_liquid"][:10]
        ],
        "live_capital_allowed": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
