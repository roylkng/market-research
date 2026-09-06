from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

JSONPayload = dict[str, Any] | list[Any]


@dataclass(frozen=True)
class NSEEndpoint:
    name: str
    url: str


class NSEAcquisitionError(RuntimeError):
    """Raised when a source-of-record discovery call cannot be completed safely."""


class NSEClient:
    """Small client for NSE web-facing and archive acquisition interfaces.

    Web JSON endpoints are discovery helpers. Research provenance must point to
    the original exchange file/document and retain its exact bytes/hash.
    """

    BASE_URL = "https://www.nseindia.com"
    SESSION_PAGE = f"{BASE_URL}/get-quotes/equity?symbol=LT"
    INDEX_ENDPOINT = NSEEndpoint(
        "equity_stock_indices", f"{BASE_URL}/api/equity-stock-indices"
    )
    QUOTE_ENDPOINT = NSEEndpoint("quote_equity", f"{BASE_URL}/api/quote-equity")
    INTEGRATED_FILING_ENDPOINT = NSEEndpoint(
        "integrated_filing_results", f"{BASE_URL}/api/integrated-filing-results"
    )
    CORPORATE_ACTION_ENDPOINT = NSEEndpoint(
        "corporate_actions", f"{BASE_URL}/api/corporates-corporateActions"
    )
    CORPORATE_ANNOUNCEMENT_ENDPOINT = NSEEndpoint(
        "corporate_announcements", f"{BASE_URL}/api/corporate-announcements"
    )
    HOLIDAY_ENDPOINT = NSEEndpoint("trading_holidays", f"{BASE_URL}/api/holiday-master")
    NIFTY200_CONSTITUENT_CSV = (
        "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
    )
    ALLOWED_ARCHIVE_HOSTS = frozenset({"nsearchives.nseindia.com", "archives.nseindia.com"})

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

    def _json_get_with_raw(
        self, endpoint: NSEEndpoint, *, params: dict[str, Any]
    ) -> tuple[JSONPayload, bytes]:
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                if not self._session_initialized:
                    self._initialize_session()
                response = self.session.get(endpoint.url, params=params, timeout=self.timeout)
                if response.status_code in {401, 403}:
                    self._session_initialized = False
                    if attempt < self.attempts:
                        time.sleep(0.25 * attempt)
                        continue
                if (
                    response.status_code == 429 or response.status_code >= 500
                ) and attempt < self.attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                response.raise_for_status()
                raw = response.content
                payload = response.json()
                if not isinstance(payload, (dict, list)):
                    raise NSEAcquisitionError(
                        f"{endpoint.name} returned {type(payload).__name__}, expected JSON"
                    )
                if not raw:
                    raise NSEAcquisitionError(f"{endpoint.name} returned empty bytes")
                return payload, raw
            except (requests.RequestException, ValueError, NSEAcquisitionError) as exc:
                last_error = exc
                if attempt < self.attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                break
        raise NSEAcquisitionError(f"NSE {endpoint.name} failed: {last_error}") from last_error

    def _json_get(self, endpoint: NSEEndpoint, *, params: dict[str, Any]) -> JSONPayload:
        payload, _ = self._json_get_with_raw(endpoint, params=params)
        return payload

    @staticmethod
    def _require_mapping(payload: JSONPayload, endpoint_name: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise NSEAcquisitionError(
                f"NSE {endpoint_name} returned {type(payload).__name__}, expected JSON object"
            )
        return payload

    def index_snapshot(self, index_name: str = "NIFTY 200") -> dict[str, Any]:
        payload = self._json_get(self.INDEX_ENDPOINT, params={"index": index_name})
        return self._require_mapping(payload, self.INDEX_ENDPOINT.name)

    def nifty200_constituent_csv(self) -> bytes:
        """Fetch the official Nifty 200 constituent CSV as exact source bytes."""
        try:
            response = requests.get(
                self.NIFTY200_CONSTITUENT_CSV,
                headers={"User-Agent": self.session.headers["User-Agent"]},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NSEAcquisitionError(f"NSE Nifty 200 constituent CSV failed: {exc}") from exc
        if not response.content:
            raise NSEAcquisitionError("NSE Nifty 200 constituent CSV returned empty bytes")
        return response.content

    def quote_equity(self, symbol: str) -> dict[str, Any]:
        payload = self._json_get(self.QUOTE_ENDPOINT, params={"symbol": symbol})
        return self._require_mapping(payload, self.QUOTE_ENDPOINT.name)

    def integrated_filings(
        self,
        *,
        symbol: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> JSONPayload:
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

    def integrated_financial_filings_with_raw(
        self, symbol: str, *, period: str = "Quarterly"
    ) -> tuple[JSONPayload, bytes]:
        """Fetch exact discovery bytes for one symbol's Integrated Financial filings."""
        return self._json_get_with_raw(
            self.INTEGRATED_FILING_ENDPOINT,
            params={"index": "equities", "symbol": symbol, "period": period},
        )

    def corporate_actions_with_raw(
        self,
        symbol: str,
        *,
        from_date: str,
        to_date: str,
    ) -> tuple[JSONPayload, bytes]:
        """Fetch exact NSE corporate-action discovery bytes for an EPS-basis audit."""
        return self._json_get_with_raw(
            self.CORPORATE_ACTION_ENDPOINT,
            params={
                "index": "equities",
                "symbol": symbol,
                "from_date": from_date,
                "to_date": to_date,
            },
        )

    def trading_holidays_with_raw(self) -> tuple[JSONPayload, bytes]:
        """Fetch exact NSE trading-holiday master bytes for calendar snapshotting."""
        return self._json_get_with_raw(self.HOLIDAY_ENDPOINT, params={"type": "trading"})

    def corporate_announcements_with_raw(
        self,
        symbol: str,
        *,
        from_date: str,
        to_date: str,
    ) -> tuple[JSONPayload, bytes]:
        """Fetch exact NSE announcement discovery bytes for one equity symbol."""
        return self._json_get_with_raw(
            self.CORPORATE_ANNOUNCEMENT_ENDPOINT,
            params={
                "index": "equities",
                "symbol": symbol,
                "from_date": from_date,
                "to_date": to_date,
            },
        )

    def archive_bytes(self, url: str) -> bytes:
        """Fetch original NSE archive bytes, rejecting arbitrary external URLs."""
        parsed = urlparse(url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in self.ALLOWED_ARCHIVE_HOSTS:
            raise NSEAcquisitionError(f"unsupported NSE archive URL: {url}")
        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": self.session.headers["User-Agent"],
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NSEAcquisitionError(f"NSE archive fetch failed: {exc}") from exc
        if not response.content:
            raise NSEAcquisitionError("NSE archive returned empty bytes")
        return response.content
