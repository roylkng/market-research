from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_history import HISTORICAL_EVIDENCE_CLASS
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.events import sha256_bytes
from marketlab.marketdata import (
    MarketArtifactStore,
    MarketDataError,
    MarketDataMissingRow,
    index_snapshot_url,
    parse_index_snapshot,
    udiff_url,
)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/152.0 Safari/537.36"
)


class AlphaAcquisitionError(RuntimeError):
    """Raised when AE001 historical market evidence cannot be acquired safely."""


Fetcher = Callable[[str], bytes | None]


def http_fetcher(*, attempts: int, timeout: float) -> Fetcher:
    if attempts < 1 or timeout <= 0:
        raise AlphaAcquisitionError("invalid HTTP acquisition settings")
    http = requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})

    def fetch(url: str) -> bytes | None:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = http.get(url, timeout=timeout)
                if response.status_code == 404:
                    return None
                if (
                    response.status_code in {403, 429} or response.status_code >= 500
                ) and attempt < attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                response.raise_for_status()
                if not response.content:
                    raise AlphaAcquisitionError(f"empty archive response: {url}")
                return response.content
            except (requests.RequestException, AlphaAcquisitionError) as exc:
                last_error = exc
                if attempt < attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                break
        raise AlphaAcquisitionError(f"archive fetch failed: {url}: {last_error}")

    return fetch


def acquire_historical_market_panel(
    *,
    start_date: date,
    end_date: date,
    fetcher: Fetcher,
    store_root: str | Path | None = None,
    captured_at_utc: datetime | None = None,
    pause_seconds: float = 0.0,
) -> dict[str, Any]:
    """Acquire official historical NSE EQ + Nifty 500 daily evidence.

    Every calendar date is probed for UDiFF so special weekend sessions are not
    silently lost. Nifty 500 is required for each observed UDiFF session.
    """

    if start_date > end_date:
        raise AlphaAcquisitionError("historical start date exceeds end date")
    if pause_seconds < 0:
        raise AlphaAcquisitionError("pause_seconds cannot be negative")
    captured = captured_at_utc or datetime.now(UTC)
    if captured.tzinfo is None:
        raise AlphaAcquisitionError("captured_at_utc must be timezone-aware")

    store = MarketArtifactStore(store_root) if store_root is not None else None
    sessions: list[dict[str, Any]] = []
    cursor = start_date
    probed_days = 0

    while cursor <= end_date:
        probed_days += 1
        stock_url = udiff_url(cursor)
        raw_udiff = fetcher(stock_url)
        if raw_udiff is None:
            cursor += timedelta(days=1)
            continue

        try:
            equities = parse_udiff_eq_panel(raw_udiff, session_date=cursor)
        except AlphaContractError as exc:
            raise AlphaAcquisitionError(
                f"{cursor}: official UDiFF could not satisfy AE001 parser contract"
            ) from exc
        udiff_sha = sha256_bytes(raw_udiff)
        if store is not None:
            store.retain(
                raw_udiff,
                source_url=stock_url,
                captured_at=captured,
                suffix=".csv.zip",
            )

        benchmark_url = index_snapshot_url(cursor)
        raw_index = fetcher(benchmark_url)
        if raw_index is None:
            raise AlphaAcquisitionError(
                f"{cursor}: UDiFF proves a session but Nifty 500 snapshot is unavailable"
            )
        try:
            benchmark = parse_index_snapshot(
                raw_index,
                benchmark_id="nifty_500",
                session_date=cursor,
            )
        except (MarketDataError, MarketDataMissingRow) as exc:
            raise AlphaAcquisitionError(
                f"{cursor}: Nifty 500 snapshot failed closed"
            ) from exc
        benchmark_sha = sha256_bytes(raw_index)
        if store is not None:
            store.retain(
                raw_index,
                source_url=benchmark_url,
                captured_at=captured,
                suffix=".csv",
            )

        sessions.append(
            {
                "session_date": cursor.isoformat(),
                "udiff_url": stock_url,
                "udiff_sha256": udiff_sha,
                "benchmark_url": benchmark_url,
                "benchmark_sha256": benchmark_sha,
                "equities": [asdict(row) for row in equities],
                "benchmark": asdict(benchmark),
            }
        )
        if pause_seconds:
            time.sleep(pause_seconds)
        cursor += timedelta(days=1)

    if not sessions:
        raise AlphaAcquisitionError("no completed NSE sessions were acquired")

    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": "AE001-HISTORICAL-MARKET-v1",
        "evidence_class": HISTORICAL_EVIDENCE_CLASS,
        "historical_archives_captured_prospectively": False,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "probed_calendar_day_count": probed_days,
        "session_count": len(sessions),
        "sessions": sessions,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
