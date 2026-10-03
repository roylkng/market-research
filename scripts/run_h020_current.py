from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests
import yaml

from marketlab.timing import compute_snapshot

YAHOO_HOSTS = (
    "https://query1.finance.yahoo.com/v8/finance/chart",
    "https://query2.finance.yahoo.com/v8/finance/chart",
)
USER_AGENT = "marketlab-research/0.1 (+https://github.com/roylkng/market-research)"


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def fetch_yahoo_history(ticker: str, as_of: str, raw_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    errors: list[str] = []
    for host in YAHOO_HOSTS:
        url = f"{host}/{quote(ticker, safe='')}"
        try:
            response = requests.get(
                url,
                params={
                    "range": "2y",
                    "interval": "1d",
                    "events": "div,splits",
                    "includeAdjustedClose": "true",
                },
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            raw = response.content
            payload = response.json()
            result = (payload.get("chart") or {}).get("result") or []
            if not result:
                raise ValueError(str((payload.get("chart") or {}).get("error") or "empty chart result"))
            item = result[0]
            timestamps = item.get("timestamp") or []
            quote_values = ((item.get("indicators") or {}).get("quote") or [{}])[0]
            adjusted_values = ((item.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose")
            closes = adjusted_values or quote_values.get("close") or []
            volumes = quote_values.get("volume") or []
            if len(timestamps) != len(closes):
                raise ValueError("timestamp/close length mismatch")
            rows: list[dict[str, Any]] = []
            for index, timestamp in enumerate(timestamps):
                close = closes[index]
                if close is None:
                    continue
                session = datetime.fromtimestamp(timestamp, tz=UTC).date()
                if session.isoformat() > as_of:
                    continue
                rows.append(
                    {
                        "date": session.isoformat(),
                        "adj_close": float(close),
                        "volume": volumes[index] if index < len(volumes) else None,
                    }
                )
            frame = pd.DataFrame(rows)
            if frame.empty:
                raise ValueError("no completed sessions at or before as-of date")
            frame["date"] = pd.to_datetime(frame["date"], utc=True)
            frame = frame.set_index("date").sort_index()
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{ticker.replace('^', 'index-').replace('.', '-')}.json"
            raw_path.write_bytes(raw)
            return frame, {
                "provider": "Yahoo Finance chart endpoint",
                "ticker": ticker,
                "request_url": response.url,
                "raw_path": str(raw_path),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "first_session": str(frame.index[0].date()),
                "last_session": str(frame.index[-1].date()),
                "session_count": len(frame),
                "exchange_timezone": item.get("meta", {}).get("exchangeTimezoneName"),
            }
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{host}: {type(exc).__name__}: {exc}")
    raise RuntimeError("; ".join(errors))


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# H020 current timing screen",
        "",
        f"As-of cutoff: **{report['as_of']}**",
        "",
        f"Benchmark: **{report['benchmark']}**, regime **{report['market_regime']}**.",
        "",
        "**RESEARCH ONLY. LIVE CAPITAL DISABLED. Timing scores are not probabilities.**",
        "",
        "| Symbol | Business lens | Action | Score | 20d | Rel 20d | RSI | Notes |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in report["results"]:
        if row.get("action") == "BLOCKED_DATA":
            lines.append(
                f"| {row['symbol']} | {row.get('business_lens', '')} | BLOCKED_DATA | | | | | {row.get('reason', '')} |"
            )
            continue
        lines.append(
            "| {symbol} | {business_lens} | {action} | {score} | {ret20:.1f}% | "
            "{rel20:.1f}pp | {rsi:.1f} | {reason} |".format(
                symbol=row["symbol"],
                business_lens=row.get("business_lens", ""),
                action=row["action"],
                score=row["timing_score_0_100_not_probability"],
                ret20=row["return_20d_pct"],
                rel20=row["relative_20d_pp"],
                rsi=row["rsi14"],
                reason=row["reason"],
            )
        )
    lines.extend(
        [
            "",
            "Transrail Lighting and Genus Power influenced the design discussion and cannot validate H020.",
            "Yahoo Finance raw responses are retained and hashed for this exploratory run. They are not exchange-certified validation data.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    config = yaml.safe_load(args.candidates.read_text(encoding="utf-8"))
    benchmark_ticker = config["benchmark_ticker"]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.out_dir / "raw"
    benchmark, benchmark_provenance = fetch_yahoo_history(benchmark_ticker, args.as_of, raw_dir)
    results: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {"benchmark": benchmark_provenance, "stocks": {}}

    for item in config["candidates"]:
        symbol = item["symbol"]
        try:
            frame, source = fetch_yahoo_history(item["ticker"], args.as_of, raw_dir)
            row = compute_snapshot(
                frame,
                benchmark,
                symbol=symbol,
                design_influenced=bool(item.get("design_influenced", False)),
            )
            provenance["stocks"][symbol] = source
        except Exception as exc:  # noqa: BLE001
            row = {
                "symbol": symbol,
                "action": "BLOCKED_DATA",
                "reason": f"{type(exc).__name__}: {exc}",
                "design_influenced": bool(item.get("design_influenced", False)),
            }
        row["ticker"] = item["ticker"]
        row["business_lens"] = item["business_lens"]
        row["business_note"] = item["business_note"]
        results.append(row)

    results.sort(
        key=lambda row: (
            0 if row.get("action", "").startswith("PAPER_ENTRY_ELIGIBLE") else 1,
            -(row.get("timing_score_0_100_not_probability") or -1),
            row["symbol"],
        )
    )
    market_regime = next((row.get("market_regime") for row in results if row.get("market_regime")), "UNKNOWN")
    report = {
        "schema_version": 1,
        "hypothesis_id": "H020",
        "run_kind": "EXPLORATORY_CURRENT_SCREEN",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "as_of": args.as_of,
        "benchmark": benchmark_ticker,
        "market_regime": market_regime,
        "candidate_config_sha256": hashlib.sha256(args.candidates.read_bytes()).hexdigest(),
        "provider_note": "Yahoo Finance is used for this exploratory timing run. Raw responses are retained and hashed. This is not exchange-certified historical validation data.",
        "live_capital_allowed": False,
        "results": results,
        "provenance": provenance,
    }
    report["report_sha256"] = _canonical_hash({k: v for k, v in report.items() if k != "report_sha256"})
    (args.out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown = render_markdown(report)
    (args.out_dir / "report.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
