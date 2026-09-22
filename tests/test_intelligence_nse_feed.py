from __future__ import annotations

import pytest
import requests

from marketlab.intelligence_http import SourceBlocked
from marketlab.intelligence_nse_feed import (
    NSE_ANNOUNCEMENTS_URL,
    SOURCE_CONTRACT_ID,
    NSEAnnouncementFetcher,
    validate_nse_announcement_source,
)


def source(**overrides):
    base = {
        "source_id": "nse-announcements",
        "kind": "nse_feed",
        "url": NSE_ANNOUNCEMENTS_URL,
        "publisher": "NSE",
        "region": "IN",
        "timezone": "Asia/Kolkata",
        "source_class": "EXCHANGE_DISCLOSURE",
        "access": "HEADLINES_ONLY",
        "document_parser": None,
        "article_hosts": [],
        "article_path_pattern": "(?!)",
    }
    return {**base, **overrides}


class Response:
    def __init__(self, status=200, body=b"<rss><channel/></rss>"):
        self.status_code = status
        self.body = body
        self.headers = {"Content-Type": "application/xml"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def iter_content(self, chunk_size):
        if self.body:
            yield self.body


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def test_reviewed_source_contract_is_exact():
    validate_nse_announcement_source(source())
    with pytest.raises(SourceBlocked, match="Unreviewed NSE RSS URL"):
        validate_nse_announcement_source(source(url="https://nsearchives.nseindia.com/other.xml"))
    with pytest.raises(SourceBlocked, match="headlines-only"):
        validate_nse_announcement_source(source(access="PUBLIC_DOCUMENTS"))


def test_transient_timeout_retries_only_reviewed_nse_feed():
    session = Session(requests.ReadTimeout("temporary"), Response())
    fetcher = NSEAnnouncementFetcher(
        session=session,
        attempts=2,
        read_timeout=0.1,
        retry_delay=0,
    )
    raw, meta = fetcher.fetch(NSE_ANNOUNCEMENTS_URL)
    assert raw == b"<rss><channel/></rss>"
    assert len(session.calls) == 2
    assert meta["source_contract_id"] == SOURCE_CONTRACT_ID
    assert meta["redirect_policy"] == "NO_REDIRECTS"


def test_transient_server_error_retries_but_policy_denial_does_not():
    retry_session = Session(Response(503), Response())
    fetcher = NSEAnnouncementFetcher(
        session=retry_session,
        attempts=2,
        retry_delay=0,
    )
    fetcher.fetch(NSE_ANNOUNCEMENTS_URL)
    assert len(retry_session.calls) == 2

    denied = Session(Response(403))
    fetcher = NSEAnnouncementFetcher(session=denied, attempts=4, retry_delay=0)
    with pytest.raises(SourceBlocked, match="HTTP 403"):
        fetcher.fetch(NSE_ANNOUNCEMENTS_URL)
    assert len(denied.calls) == 1


def test_redirect_and_arbitrary_path_are_rejected():
    wrong = "https://nsearchives.nseindia.com/content/RSS/other.xml"
    fetcher = NSEAnnouncementFetcher(session=Session(Response()), retry_delay=0)
    with pytest.raises(SourceBlocked, match="Unreviewed NSE RSS URL"):
        fetcher.fetch(wrong)

    redirected = Session(Response(302))
    fetcher = NSEAnnouncementFetcher(session=redirected, retry_delay=0)
    with pytest.raises(SourceBlocked, match="HTTP 302"):
        fetcher.fetch(NSE_ANNOUNCEMENTS_URL)


def test_response_size_bound_is_fail_closed():
    oversized = b"x" * (4 * 1024 * 1024 + 1)
    fetcher = NSEAnnouncementFetcher(
        session=Session(Response(200, oversized)),
        retry_delay=0,
    )
    with pytest.raises(SourceBlocked, match="size bound"):
        fetcher.fetch(NSE_ANNOUNCEMENTS_URL)
