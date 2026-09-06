from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class NSEEndpoint:
    name: str
    url: str


class NSEAcquisitionError(RuntimeError):
    """Raised when a source-of-record discovery call cannot be completed safely."""


class NSEClient:
    """Small client for NSE's web-facing JSON interfaces.

    These endpoints are acquisition helpers, not a contractual public API. The
    research source of record remains the original filing/XBRL document URL.
    """

    BASE_URL = "https://www.nseindia.com"
    SESSION_PAGE = f"{BASE_URL}/market-data/live-equity-market"
    INDEX_ENDPOINT = NSEEndpoint("equity_stock_indices", f"{BASE_URL}/api/equity-stockIndices")
    QUOTE_ENDPOINT = NSEEndpoint("quote_equity", f"{BASE_URL}/api/quote-equity")
    INTEGRATED_FILING_ENDPOINT = NSEEndpoint(
        "integrated_filing_results", f"{BASE_URL}/api/integrated-filing-results"
    )

    def __init__(self, *, timeout: float = 12.0, attempts: int = 3) -> None:
        self.timeout = timeout
        self.attempts = attempts
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "Chrome/151.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": self.SESSION_PAGE,
                "Cache-Control": "no-cache",
            }
        )
        self._session_initialized = False

    def _initialize_session(self) -> None:
        response = self.session.get(self.SESSION_PAGE, timeout=self.timeout)
        if response.status_code >= 400:
            raise NSEAcquisitionError(
                f"NSE session initialization failed with HTTP {response.status_code}"
            )
        self._session_initialized = True

    def _json_get(self, endpoint: NSEEndpoint, *, params: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                if not self._session_initialized:
                    self._initialize_session()
                response = self.session.get(endpoint.url, params=params, timeout=self.timeout)
                if response.status_code in {401, 403}:
                    self._session_initialized = False
                    if attempt < self.attempts:
                        continue
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.attempts:
                        time.sleep(0.5 * (2 ** (attempt - 1)))
                        continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise NSEAcquisitionError(
                        f"{endpoint.name} returned {type(payload).__name__}, expected JSON object"
                    )
                return payload
            except (requests.RequestException, ValueError, NSEAcquisitionError) as exc:
                last_error = exc
                if attempt < self.attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                break
        raise NSEAcquisitionError(f"NSE {endpoint.name} failed: {last_error}") from last_error

    def index_snapshot(self, index_name: str = "NIFTY 200") -> dict[str, Any]:
        return self._json_get(self.INDEX_ENDPOINT, params={"index": index_name})

    def quote_equity(self, symbol: str) -> dict[str, Any]:
        return self._json_get(self.QUOTE_ENDPOINT, params={"symbol": symbol})

    def integrated_filings(
        self,
        *,
        symbol: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "type": "Integrated Filing- Financials",
            "page": page,
            "size": size,
        }
        if symbol:
            params["symbol"] = symbol
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        return self._json_get(self.INTEGRATED_FILING_ENDPOINT, params=params)
