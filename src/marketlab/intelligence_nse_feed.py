"""Explicit acquisition contract for NSE's public corporate-announcement RSS feed.

This is intentionally separate from the generic public-web fetcher. The contract
permits exactly one documented NSE RSS resource, follows no redirects, uses no
credentials, bounds retries and response size, and returns ordinary discovery
metadata. It does not generalise to other NSE paths or hosts.
"""
from __future__ import annotations

import time

import requests

from marketlab.intelligence_http import MAX_BYTES, SourceBlocked
from marketlab.intelligence_store import now_text

NSE_ANNOUNCEMENTS_URL = (
    "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"
)
SOURCE_CONTRACT_ID = "NSE-ONLINE-ANNOUNCEMENTS-RSS-V1"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)
TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})


def validate_nse_announcement_source(source: dict) -> None:
    if source.get("kind") != "nse_feed":
        raise SourceBlocked("NSE RSS source must use the reviewed nse_feed adapter")
    if source.get("url") != NSE_ANNOUNCEMENTS_URL:
        raise SourceBlocked("Unreviewed NSE RSS URL", url=str(source.get("url") or ""))
    if source.get("source_id") != "nse-announcements":
        raise SourceBlocked("Unreviewed NSE RSS source identity")
    if source.get("access") != "HEADLINES_ONLY":
        raise SourceBlocked("NSE RSS contract is headlines-only")
    if source.get("publisher") != "NSE":
        raise SourceBlocked("NSE RSS publisher identity changed")


class NSEAnnouncementFetcher:
    """Bounded reader for the single reviewed official NSE announcement feed."""

    def __init__(
        self,
        *,
        session=None,
        attempts: int = 4,
        read_timeout: float = 20.0,
        retry_delay: float = 0.75,
    ):
        if attempts < 1 or read_timeout <= 0 or retry_delay < 0:
            raise ValueError("invalid NSE announcement fetch bounds")
        self.session = session if session is not None else requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml,application/xml,text/xml,*/*;q=0.5",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.nseindia.com/static/rss-feed",
            }
        )
        self.attempts = attempts
        self.read_timeout = read_timeout
        self.retry_delay = retry_delay

    def fetch(self, url: str, *, url_guard=None):
        if url != NSE_ANNOUNCEMENTS_URL:
            raise SourceBlocked(
                "Unreviewed NSE RSS URL",
                stage="OFFICIAL_NSE_RSS",
                url=url,
            )
        if url_guard is not None and not url_guard(url):
            raise SourceBlocked(
                "Discovery scope rejects reviewed NSE RSS URL",
                stage="OFFICIAL_NSE_RSS",
                url=url,
            )

        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                with self.session.get(
                    url,
                    timeout=(10, self.read_timeout),
                    allow_redirects=False,
                    stream=True,
                ) as response:
                    status = response.status_code
                    if status == 200:
                        chunks: list[bytes] = []
                        size = 0
                        for chunk in response.iter_content(chunk_size=32768):
                            size += len(chunk)
                            if size > MAX_BYTES:
                                raise SourceBlocked(
                                    "NSE RSS response exceeds size bound",
                                    stage="OFFICIAL_NSE_RSS",
                                    url=url,
                                    status_code=status,
                                )
                            chunks.append(chunk)
                        raw = b"".join(chunks)
                        if not raw:
                            raise SourceBlocked(
                                "NSE RSS response is empty",
                                stage="OFFICIAL_NSE_RSS",
                                url=url,
                                status_code=status,
                            )
                        return raw, {
                            "resolved_url": url,
                            "status_code": status,
                            "content_type": response.headers.get("Content-Type", ""),
                            "observed_at": now_text(),
                            "source_contract_id": SOURCE_CONTRACT_ID,
                            "redirect_policy": "NO_REDIRECTS",
                        }
                    if status in TRANSIENT_STATUS and attempt < self.attempts:
                        last_error = RuntimeError(f"HTTP {status}")
                    else:
                        raise SourceBlocked(
                            f"NSE RSS HTTP {status}",
                            stage="OFFICIAL_NSE_RSS",
                            url=url,
                            status_code=status,
                        )
            except SourceBlocked:
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.attempts:
                    raise SourceBlocked(
                        "NSE RSS transport failure",
                        stage="OFFICIAL_NSE_RSS",
                        url=url,
                        error_type=type(exc).__name__,
                    ) from exc
            if attempt < self.attempts:
                time.sleep(self.retry_delay * (2 ** (attempt - 1)))

        raise SourceBlocked(
            f"NSE RSS acquisition exhausted retries: {last_error}",
            stage="OFFICIAL_NSE_RSS",
            url=url,
            error_type=type(last_error).__name__ if last_error else None,
        )
