"""Run the post-close MarketLab v2 broad-market mover and discovery audit."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

import requests

from marketlab.intelligence_market_audit import build_market_audit
from marketlab.intelligence_store import ResearchStore
from marketlab.marketdata import udiff_url

USER_AGENT = "marketlab-research/0.2 (+https://github.com/roylkng/market-research)"


def download_udiff(session_date: date) -> bytes:
    url = udiff_url(session_date)
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/zip,*/*"},
        timeout=(10, 45),
    )
    response.raise_for_status()
    raw = response.content
    if not raw:
        raise RuntimeError("official NSE UDiFF response is empty")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--liquidity-floor-inr", type=float, default=20_000_000.0)
    parser.add_argument("--move-threshold-pct", type=float, default=5.0)
    parser.add_argument("--top-abs-movers", type=int, default=25)
    args = parser.parse_args()
    session_date = date.fromisoformat(args.session)
    raw = download_udiff(session_date)
    captured_at = datetime.now(UTC).isoformat()
    args.output.mkdir(parents=True, exist_ok=True)
    with ResearchStore(args.store) as store:
        raw_sha = store.save_object(raw)
        report = build_market_audit(
            raw,
            session_date=session_date,
            store=store,
            captured_at=captured_at,
            liquidity_floor_inr=args.liquidity_floor_inr,
            move_threshold_pct=args.move_threshold_pct,
            top_abs_movers=args.top_abs_movers,
        )
        store.append("market_audit", report["report_sha256"], report)
    path = args.output / f"market-audit-{session_date.isoformat()}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "session_date": report["session_date"],
        "market_raw_sha256": raw_sha,
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
        "live_capital_allowed": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
