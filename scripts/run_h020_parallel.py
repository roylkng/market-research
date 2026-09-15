from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests
import yaml

from marketlab.h020_timing_v2 import compute_snapshot_v2

YAHOO_HOSTS = (
    "https://query1.finance.yahoo.com/v8/finance/chart",
    "https://query2.finance.yahoo.com/v8/finance/chart",
)
USER_AGENT = "marketlab-research/0.1 (+https://github.com/roylkng/market-research)"
V2_PROSPECTIVE_START_SESSION = date(2026, 9, 16)
LEDGER_SCHEMA_VERSION = 1


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def fetch_yahoo_history(
    ticker: str, as_of: str, raw_dir: Path
) -> tuple[pd.DataFrame, dict[str, Any]]:
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
                raise ValueError(
                    str((payload.get("chart") or {}).get("error") or "empty chart result")
                )
            item = result[0]
            timestamps = item.get("timestamp") or []
            quote_values = ((item.get("indicators") or {}).get("quote") or [{}])[0]
            adjusted_values = (
                ((item.get("indicators") or {}).get("adjclose") or [{}])[0].get(
                    "adjclose"
                )
            )
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
                "exchange_timezone": item.get("meta", {}).get(
                    "exchangeTimezoneName"
                ),
            }
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{host}: {type(exc).__name__}: {exc}")
    raise RuntimeError("; ".join(errors))


def new_ledger() -> dict[str, Any]:
    payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "hypothesis_id": "H020",
        "stream_id": "H020-V1-V2-PARALLEL-20260916",
        "v1_rule_id": "H020-V1-20260910",
        "v2_rule_id": "H020-V2-DOWNSIDE-GUARD-20260915",
        "prospective_start_session": "2026-09-16",
        "provider_class": "EXPLORATORY_YAHOO_NOT_EXCHANGE_CERTIFIED",
        "record_count": 0,
        "records": [],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    payload["ledger_sha256"] = canonical_hash(payload)
    return payload


def validate_ledger(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise ValueError("H020 parallel ledger schema mismatch")
    if payload.get("hypothesis_id") != "H020":
        raise ValueError("H020 parallel ledger hypothesis mismatch")
    if payload.get("stream_id") != "H020-V1-V2-PARALLEL-20260916":
        raise ValueError("H020 parallel ledger stream mismatch")
    records = payload.get("records")
    if not isinstance(records, list):
        raise TypeError("H020 parallel ledger records must be a list")
    if payload.get("record_count") != len(records):
        raise ValueError("H020 parallel ledger record_count mismatch")
    expected = canonical_hash({k: v for k, v in payload.items() if k != "ledger_sha256"})
    if payload.get("ledger_sha256") != expected:
        raise ValueError("H020 parallel ledger hash mismatch")
    seen: set[str] = set()
    for record in records:
        session = str(record.get("as_of_session"))
        if session in seen:
            raise ValueError(f"duplicate H020 parallel session: {session}")
        seen.add(session)
        expected_record = canonical_hash(
            {k: v for k, v in record.items() if k != "record_sha256"}
        )
        if record.get("record_sha256") != expected_record:
            raise ValueError(f"H020 parallel record hash mismatch: {session}")
    if payload.get("outcome_data_attached") is not False:
        raise ValueError("H020 parallel decision ledger cannot attach outcomes")
    if payload.get("live_capital_allowed") is not False:
        raise ValueError("H020 parallel decision ledger cannot authorize live capital")


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return new_ledger()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("H020 parallel ledger must be a JSON object")
    validate_ledger(payload)
    return payload


def seal_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    result = {k: v for k, v in payload.items() if k != "ledger_sha256"}
    result["record_count"] = len(result["records"])
    result["ledger_sha256"] = canonical_hash(result)
    validate_ledger(result)
    return result


def compact_result(row: dict[str, Any], *, ticker: str) -> dict[str, Any]:
    if row.get("action") == "BLOCKED_DATA":
        return {
            "symbol": row["symbol"],
            "ticker": ticker,
            "status": "BLOCKED_DATA",
            "reason": row.get("reason"),
            "v1_action": row.get("v1_action", "BLOCKED_DATA"),
            "v2_action": row.get("v2_action", "BLOCKED_DATA"),
            "v2_override": False,
        }
    guard = row["v2_guard"]
    return {
        "symbol": row["symbol"],
        "ticker": ticker,
        "status": "READY",
        "v1_action": row["v1_action"],
        "v2_action": row["v2_action"],
        "v2_override": bool(row["v2_override"]),
        "timing_score_0_100_not_probability": row[
            "timing_score_0_100_not_probability"
        ],
        "market_regime": row["market_regime"],
        "close_adjusted": row["close_adjusted"],
        "return_1d_pct": guard["return_1d_pct"],
        "benchmark_return_1d_pct": guard["benchmark_return_1d_pct"],
        "relative_1d_pp": guard["relative_1d_pp"],
        "return_20d_pct": row["return_20d_pct"],
        "relative_20d_pp": row["relative_20d_pp"],
        "return_60d_pct": row["return_60d_pct"],
        "relative_60d_pp": row["relative_60d_pp"],
        "rsi14": row["rsi14"],
        "downside_shock_z": guard["downside_shock_z"],
        "downside_shock": guard["downside_shock"],
        "prior10_closing_low": guard["prior10_closing_low"],
        "closing_breakdown_10d": guard["closing_breakdown_10d"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# H020 v1-v2 prospective parallel screen",
        "",
        f"Requested as-of: **{report['requested_as_of']}**",
        f"Latest completed benchmark session: **{report.get('as_of_session', 'none')}**",
        f"Status: **{report['status']}**",
        "",
        "**RESEARCH ONLY. LIVE CAPITAL DISABLED. V2 starts prospectively with the completed 2026-09-16 session.**",
        "",
    ]
    if report["status"] != "SEALED_DECISION":
        lines.append(report.get("reason", "No prospective decision was sealed."))
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "| Symbol | V1 | V2 | Override | Score | 1d | Rel 1d | Shock z | 10d break |",
            "|---|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in report["results"]:
        if row["status"] == "BLOCKED_DATA":
            lines.append(
                f"| {row['symbol']} | BLOCKED_DATA | BLOCKED_DATA | no | | | | | |"
            )
            continue
        z = row.get("downside_shock_z")
        z_text = "" if z is None else f"{z:.2f}"
        lines.append(
            "| {symbol} | {v1} | {v2} | {override} | {score} | {r1:.2f}% | "
            "{rel1:.2f}pp | {z} | {breakdown} |".format(
                symbol=row["symbol"],
                v1=row["v1_action"],
                v2=row["v2_action"],
                override="yes" if row["v2_override"] else "no",
                score=row["timing_score_0_100_not_probability"],
                r1=row["return_1d_pct"],
                rel1=row["relative_1d_pp"],
                z=z_text,
                breakdown="yes" if row["closing_breakdown_10d"] else "no",
            )
        )
    lines.extend(
        [
            "",
            "Yahoo Finance raw responses are retained and hashed for this exploratory prospective comparison. They are not exchange-certified promotion evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    config = yaml.safe_load(args.candidates.read_text(encoding="utf-8"))
    benchmark_ticker = str(config["benchmark_ticker"])
    raw_dir = args.out_dir / "raw"
    benchmark, benchmark_source = fetch_yahoo_history(
        benchmark_ticker, args.as_of, raw_dir
    )
    as_of_session = date.fromisoformat(str(benchmark_source["last_session"]))

    if as_of_session < V2_PROSPECTIVE_START_SESSION:
        report = {
            "schema_version": 1,
            "hypothesis_id": "H020",
            "requested_as_of": args.as_of,
            "as_of_session": as_of_session.isoformat(),
            "status": "NO_PROSPECTIVE_V2_SESSION",
            "reason": (
                "latest completed benchmark session predates the frozen H020-v2 "
                "prospective start session"
            ),
            "outcome_data_attached": False,
            "live_capital_allowed": False,
        }
        write_outputs(args.out_dir, report)
        print(render_markdown(report))
        return 0

    results: list[dict[str, Any]] = []
    raw_hashes: dict[str, str | None] = {benchmark_ticker: benchmark_source["raw_sha256"]}
    for item in config["candidates"]:
        symbol = str(item["symbol"])
        ticker = str(item["ticker"])
        try:
            frame, source = fetch_yahoo_history(ticker, args.as_of, raw_dir)
            raw_hashes[ticker] = str(source["raw_sha256"])
            if source["last_session"] != as_of_session.isoformat():
                raise RuntimeError(
                    f"stock latest session {source['last_session']} != benchmark {as_of_session}"
                )
            full = compute_snapshot_v2(
                frame,
                benchmark,
                symbol=symbol,
                design_influenced=bool(item.get("design_influenced", False)),
            )
            row = compact_result(full, ticker=ticker)
        except Exception as exc:  # noqa: BLE001
            raw_hashes.setdefault(ticker, None)
            row = {
                "symbol": symbol,
                "ticker": ticker,
                "status": "BLOCKED_DATA",
                "reason": f"{type(exc).__name__}: {exc}",
                "v1_action": "BLOCKED_DATA",
                "v2_action": "BLOCKED_DATA",
                "v2_override": False,
            }
        results.append(row)

    results.sort(key=lambda row: row["symbol"])
    market_regime = next(
        (
            str(row["market_regime"])
            for row in results
            if row.get("status") == "READY" and row.get("market_regime")
        ),
        "UNKNOWN",
    )
    source_fingerprint = canonical_hash(raw_hashes)
    record_core = {
        "as_of_session": as_of_session.isoformat(),
        "candidate_config_sha256": hashlib.sha256(args.candidates.read_bytes()).hexdigest(),
        "benchmark_ticker": benchmark_ticker,
        "market_regime": market_regime,
        "source_fingerprint_sha256": source_fingerprint,
        "results": results,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    record = dict(record_core)
    record["record_sha256"] = canonical_hash(record_core)

    ledger = load_ledger(args.ledger)
    existing = next(
        (
            row
            for row in ledger["records"]
            if row["as_of_session"] == as_of_session.isoformat()
        ),
        None,
    )
    appended = False
    if existing is not None:
        if existing["record_sha256"] != record["record_sha256"]:
            raise RuntimeError(
                "H020 same-session prospective record changed; refuse immutable rewrite"
            )
    else:
        ledger["records"].append(record)
        ledger = seal_ledger(ledger)
        args.ledger.parent.mkdir(parents=True, exist_ok=True)
        args.ledger.write_text(
            json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        appended = True

    report = {
        "schema_version": 1,
        "hypothesis_id": "H020",
        "requested_as_of": args.as_of,
        "as_of_session": as_of_session.isoformat(),
        "status": "SEALED_DECISION",
        "ledger_appended": appended,
        "record_sha256": record["record_sha256"],
        "source_fingerprint_sha256": source_fingerprint,
        "market_regime": market_regime,
        "results": results,
        "provider_note": (
            "Yahoo Finance is retained for continuity with H020-v1 exploratory data. "
            "Raw responses are hashed but are not exchange-certified promotion evidence."
        ),
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    write_outputs(args.out_dir, report)
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
