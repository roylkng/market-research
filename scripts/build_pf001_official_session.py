from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests

from marketlab.marketdata import MarketArtifactStore, index_snapshot_url, udiff_url
from marketlab.pf001_marketdata import (
    PF001MarketDataMissingRow,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

USER_AGENT = "market-research-pf001/1.0"


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _fetch(
    url: str,
    *,
    attempts: int,
    sleep_seconds: float,
) -> tuple[bytes | None, int]:
    last_status = 0
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            )
            last_status = response.status_code
            if response.status_code == 404:
                return None, response.status_code
            response.raise_for_status()
            if not response.content:
                raise ValueError(f"empty response from {url}")
            return response.content, response.status_code
        except (requests.RequestException, ValueError):
            if attempt == attempts:
                raise
            time.sleep(sleep_seconds)
    raise RuntimeError(f"unreachable fetch state for {url}, status={last_status}")


def _register_security(
    securities: dict[str, str],
    *,
    symbol: object,
    isin: object,
) -> None:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("security symbol must be non-empty")
    if not isinstance(isin, str) or not isin.strip():
        raise ValueError(f"security ISIN must be non-empty for {symbol}")
    normalized_symbol = symbol.strip().upper()
    normalized_isin = isin.strip()
    prior = securities.get(normalized_symbol)
    if prior is not None and prior != normalized_isin:
        raise ValueError(
            f"conflicting ISINs for {normalized_symbol}: {prior} vs {normalized_isin}"
        )
    securities[normalized_symbol] = normalized_isin


def _collect_securities(state_paths: list[str], decision_paths: list[str]) -> dict[str, str]:
    securities: dict[str, str] = {}
    for raw_path in state_paths:
        payload = _load_json(Path(raw_path))
        if not isinstance(payload, dict):
            raise TypeError(f"fund state must be an object: {raw_path}")
        positions = payload.get("open_positions")
        if not isinstance(positions, dict):
            raise TypeError(f"fund state open_positions invalid: {raw_path}")
        for position in positions.values():
            if not isinstance(position, dict):
                raise TypeError(f"open position must be an object: {raw_path}")
            _register_security(
                securities,
                symbol=position.get("symbol"),
                isin=position.get("isin"),
            )

    for raw_path in decision_paths:
        payload = _load_json(Path(raw_path))
        if not isinstance(payload, list):
            raise TypeError(f"decision payload must be a list: {raw_path}")
        for decision in payload:
            if not isinstance(decision, dict):
                raise TypeError(f"decision row must be an object: {raw_path}")
            _register_security(
                securities,
                symbol=decision.get("symbol"),
                isin=decision.get("isin"),
            )
    return securities


def _artifact_dict(artifact: Any) -> dict[str, Any]:
    return artifact.to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build one PF001 session from official NSE UDiFF and index files"
    )
    parser.add_argument("--session-date", required=True)
    parser.add_argument("--state", action="append", default=[])
    parser.add_argument("--decisions", action="append", default=[])
    parser.add_argument("--artifact-root", default=".marketlab/pf001")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--sleep-seconds", type=float, default=10.0)
    parser.add_argument("--allow-no-session", action="store_true")
    args = parser.parse_args()

    session_date = date.fromisoformat(args.session_date)
    if args.attempts < 1:
        raise ValueError("attempts must be >= 1")
    if args.sleep_seconds < 0:
        raise ValueError("sleep-seconds must be >= 0")

    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    securities = _collect_securities(args.state, args.decisions)
    store = MarketArtifactStore(args.artifact_root)
    captured_at = datetime.now(UTC)

    index_url = index_snapshot_url(session_date)
    index_raw, index_status = _fetch(
        index_url,
        attempts=args.attempts,
        sleep_seconds=args.sleep_seconds,
    )
    if index_raw is None:
        if not args.allow_no_session:
            raise ValueError(f"official index snapshot returned HTTP {index_status}")
        _write_json(
            output_dir / "source-manifest.json",
            {
                "schema_version": 1,
                "session_date": args.session_date,
                "status": "NO_SESSION_OR_OFFICIAL_FILE_UNAVAILABLE",
                "index_url": index_url,
                "index_http_status": index_status,
                "securities_requested": securities,
            },
        )
        return

    index_artifact = store.retain(
        index_raw,
        source_url=index_url,
        captured_at=captured_at,
        suffix=".csv",
    )
    benchmark = parse_pf001_nifty500_index(index_raw, session_date=session_date)

    bars: dict[str, dict[str, float]] = {}
    bar_records: dict[str, dict[str, Any]] = {}
    missing_symbols: list[str] = []
    udiff_artifact = None
    udiff_status = None
    equity_url = udiff_url(session_date)
    if securities:
        udiff_raw, udiff_status = _fetch(
            equity_url,
            attempts=args.attempts,
            sleep_seconds=args.sleep_seconds,
        )
        if udiff_raw is None:
            raise ValueError(
                "NIFTY 500 index snapshot exists but official CM UDiFF file returned 404"
            )
        udiff_artifact = store.retain(
            udiff_raw,
            source_url=equity_url,
            captured_at=captured_at,
            suffix=".zip",
        )
        for symbol, isin in sorted(securities.items()):
            try:
                bar = parse_pf001_udiff_equity(
                    udiff_raw,
                    symbol=symbol,
                    session_date=session_date,
                    expected_isin=isin,
                )
            except PF001MarketDataMissingRow:
                missing_symbols.append(symbol)
                continue
            bars[symbol] = bar.fund_bar()
            bar_records[symbol] = bar.to_dict()

    _write_json(output_dir / "bars.json", bars)
    _write_json(output_dir / "benchmark-bar.json", benchmark.attribution_bar())
    _write_json(
        output_dir / "source-manifest.json",
        {
            "schema_version": 1,
            "session_date": args.session_date,
            "status": "OK",
            "captured_at_utc": captured_at.isoformat().replace("+00:00", "Z"),
            "securities_requested": securities,
            "securities_observed": sorted(bars),
            "missing_symbols": missing_symbols,
            "benchmark": benchmark.to_dict(),
            "bar_records": bar_records,
            "index_http_status": index_status,
            "udiff_http_status": udiff_status,
            "artifacts": {
                "index_snapshot": _artifact_dict(index_artifact),
                "cm_udiff": _artifact_dict(udiff_artifact) if udiff_artifact else None,
            },
        },
    )


if __name__ == "__main__":
    main()
