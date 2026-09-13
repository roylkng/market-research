from __future__ import annotations

import argparse
import hashlib
import json
import time as time_module
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from marketlab.h022 import validate_feature_panel
from marketlab.h022_outcomes import CUTOFF_SESSION, HORIZONS, NSE_OPEN, parse_universe
from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.pf001_marketdata import (
    PF001MarketDataMissingRow,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

IST = ZoneInfo("Asia/Kolkata")
USER_AGENT = "Mozilla/5.0 (compatible; market-research-h022/1.0)"
CALENDAR_START = date(2025, 10, 1)
CORPORATE_ACTION_START = date(2025, 10, 1)


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fetch(
    session: requests.Session,
    url: str,
    *,
    attempts: int,
    sleep_seconds: float,
    allow_404: bool = False,
) -> tuple[bytes | None, int]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 404 and allow_404:
                return None, 404
            response.raise_for_status()
            if not response.content:
                raise ValueError(f"empty response from {url}")
            return response.content, response.status_code
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            time_module.sleep(sleep_seconds)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def _dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _collect_calendar(
    session: requests.Session,
    *,
    raw_root: Path,
    attempts: int,
    sleep_seconds: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for day in _dates(CALENDAR_START, CUTOFF_SESSION):
        url = index_snapshot_url(day)
        raw, status = _fetch(
            session,
            url,
            attempts=attempts,
            sleep_seconds=sleep_seconds,
            allow_404=True,
        )
        if raw is None:
            continue
        bar = parse_pf001_nifty500_index(raw, session_date=day)
        digest = _sha256(raw)
        path = raw_root / "index" / f"{day.isoformat()}-{digest}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        rows.append(
            {
                "session_date": day.isoformat(),
                "open": bar.open_price,
                "close": bar.close_price,
            }
        )
        manifest.append(
            {
                "session_date": day.isoformat(),
                "url": url,
                "http_status": status,
                "sha256": digest,
                "byte_count": len(raw),
            }
        )
    if not rows or rows[-1]["session_date"] != CUTOFF_SESSION.isoformat():
        raise RuntimeError("official NIFTY 500 calendar did not reach frozen cutoff session")
    return rows, manifest


def _entry_index(published_at: str, calendar: list[dict[str, Any]]) -> int | None:
    parsed = datetime.fromisoformat(published_at).astimezone(UTC)
    for index, row in enumerate(calendar):
        session_day = date.fromisoformat(row["session_date"])
        open_utc = datetime.combine(session_day, NSE_OPEN, tzinfo=IST).astimezone(UTC)
        if open_utc > parsed:
            return index
    return None


def _required_stock_dates(
    feature_panel: dict[str, Any], calendar: list[dict[str, Any]]
) -> dict[str, set[str]]:
    required: dict[str, set[str]] = {}
    for row in feature_panel["records"]:
        if row.get("historical_split") != "CHALLENGE" or row.get("feature_status") != "SIGNAL":
            continue
        entry_index = _entry_index(row["exchange_published_at_utc"], calendar)
        if entry_index is None:
            continue
        symbol = str(row["symbol"]).upper()
        entry_date = calendar[entry_index]["session_date"]
        required.setdefault(entry_date, set()).add(symbol)
        for horizon in HORIZONS:
            exit_index = entry_index + horizon - 1
            if exit_index < len(calendar):
                required.setdefault(calendar[exit_index]["session_date"], set()).add(symbol)
    return required


def _collect_stock_prices(
    session: requests.Session,
    required: dict[str, set[str]],
    identities: dict[str, dict[str, str]],
    *,
    raw_root: Path,
    attempts: int,
    sleep_seconds: float,
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]], list[dict[str, str]]]:
    prices: dict[str, dict[str, dict[str, Any]]] = {}
    manifest: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for raw_day in sorted(required):
        day = date.fromisoformat(raw_day)
        url = udiff_url(day)
        raw, status = _fetch(
            session,
            url,
            attempts=attempts,
            sleep_seconds=sleep_seconds,
            allow_404=False,
        )
        assert raw is not None
        digest = _sha256(raw)
        path = raw_root / "udiff" / f"{raw_day}-{digest}.zip"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        manifest.append(
            {
                "session_date": raw_day,
                "url": url,
                "http_status": status,
                "sha256": digest,
                "byte_count": len(raw),
                "symbols_requested": sorted(required[raw_day]),
            }
        )
        for symbol in sorted(required[raw_day]):
            identity = identities[symbol]
            try:
                bar = parse_pf001_udiff_equity(
                    raw,
                    symbol=symbol,
                    session_date=day,
                    expected_isin=identity["isin"],
                    series=identity["series"],
                )
            except PF001MarketDataMissingRow:
                missing.append({"session_date": raw_day, "symbol": symbol})
                continue
            prices.setdefault(raw_day, {})[symbol] = {
                "isin": bar.isin,
                "series": bar.series,
                "open": bar.open_price,
                "high": bar.high_price,
                "low": bar.low_price,
                "close": bar.close_price,
            }
    return prices, manifest, missing


def _parse_nse_date(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            parsed = time_module.strptime(value.strip(), fmt)
        except ValueError:
            continue
        return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
    return None


def _collect_corporate_actions(
    *,
    raw_root: Path,
    attempts: int,
    sleep_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
        }
    )
    _fetch(
        session,
        "https://www.nseindia.com/",
        attempts=attempts,
        sleep_seconds=sleep_seconds,
    )
    from_date = CORPORATE_ACTION_START.strftime("%d-%m-%Y")
    to_date = CUTOFF_SESSION.strftime("%d-%m-%Y")
    url = (
        "https://www.nseindia.com/api/corporates-corporateActions"
        f"?index=equities&from_date={from_date}&to_date={to_date}"
    )
    raw, status = _fetch(
        session,
        url,
        attempts=attempts,
        sleep_seconds=sleep_seconds,
    )
    assert raw is not None
    digest = _sha256(raw)
    path = raw_root / "corporate-actions" / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise TypeError("NSE corporate-actions endpoint did not return a list")
    actions: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        ex_date = _parse_nse_date(row.get("exDate"))
        if ex_date is None:
            continue
        actions.append(
            {
                "symbol": str(row.get("symbol") or "").strip().upper(),
                "series": str(row.get("series") or "").strip().upper(),
                "subject": str(row.get("subject") or "").strip(),
                "ex_date": ex_date,
            }
        )
    actions.sort(key=lambda row: (row["ex_date"], row["symbol"], row["subject"]))
    return actions, {
        "url": url,
        "http_status": status,
        "sha256": digest,
        "byte_count": len(raw),
        "action_count": len(actions),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect exact historical NSE inputs for H022-O001")
    parser.add_argument("--feature-panel", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    args = parser.parse_args()

    feature_panel = _load(args.feature_panel)
    universe = _load(args.universe)
    if not isinstance(feature_panel, dict) or not isinstance(universe, dict):
        raise TypeError("feature panel and universe must be objects")
    validate_feature_panel(feature_panel)
    identities = parse_universe(universe)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    raw_root = Path(args.raw_dir)
    calendar, index_manifest = _collect_calendar(
        session,
        raw_root=raw_root,
        attempts=args.attempts,
        sleep_seconds=args.sleep_seconds,
    )
    required = _required_stock_dates(feature_panel, calendar)
    prices, udiff_manifest, missing = _collect_stock_prices(
        session,
        required,
        identities,
        raw_root=raw_root,
        attempts=args.attempts,
        sleep_seconds=args.sleep_seconds,
    )
    actions, actions_manifest = _collect_corporate_actions(
        raw_root=raw_root,
        attempts=args.attempts,
        sleep_seconds=args.sleep_seconds,
    )

    out = Path(args.out_dir)
    _write(out / "index-sessions.json", calendar)
    _write(out / "stock-prices.json", prices)
    _write(out / "corporate-actions.json", actions)
    _write(
        out / "source-manifest.json",
        {
            "schema_version": 1,
            "hypothesis_id": "H022",
            "outcome_rule_id": "H022-O001",
            "captured_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "calendar_start": CALENDAR_START.isoformat(),
            "availability_cutoff_session": CUTOFF_SESSION.isoformat(),
            "index_session_count": len(calendar),
            "required_stock_session_count": len(required),
            "normalized_stock_session_count": len(prices),
            "missing_stock_rows": missing,
            "index_files": index_manifest,
            "udiff_files": udiff_manifest,
            "corporate_actions": actions_manifest,
        },
    )


if __name__ == "__main__":
    main()
