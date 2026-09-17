from __future__ import annotations

import pytest
import requests

from marketlab.intelligence_http import PublicFetcher, SourceBlocked


class Response:
    def __init__(self, status, body=b"", **headers):
        self.status_code = status
        self.body = body
        self.headers = {"Content-Type": "text/plain", **headers}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def iter_content(self, chunk_size):
        yield self.body


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.headers = {}
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.parametrize("status", [404, 410])
def test_missing_robots_is_not_a_content_failure(status):
    session = Session(Response(status), Response(200, b"actual document", **{"Content-Type": "text/html"}))
    fetcher = PublicFetcher(session=session, delay=0)
    raw, metadata = fetcher.fetch("https://www.tcs.com/report")
    assert raw == b"actual document"
    assert metadata["robots_policy"]["policy_state"] == "UNAVAILABLE_404_410"
    assert [r["stage"] for r in fetcher.trace] == ["ROBOTS", "DOCUMENT"]


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_auth_limits_and_server_failures_do_not_bypass_robots(status):
    session = Session(Response(status))
    fetcher = PublicFetcher(session=session, delay=0)
    with pytest.raises(SourceBlocked) as error:
        fetcher.fetch("https://www.tcs.com/report")
    assert error.value.details["stage"] == "ROBOTS"
    assert error.value.details["status_code"] == status
    with pytest.raises(SourceBlocked) as retry:
        fetcher.fetch("https://www.tcs.com/other")
    assert retry.value.details["cached_failure"] is True
    assert len(session.urls) == 1


def test_timeout_blocks_and_records_phase_without_retry_storm():
    session = Session(requests.exceptions.ReadTimeout())
    fetcher = PublicFetcher(session=session, delay=0)
    with pytest.raises(SourceBlocked) as error:
        fetcher.fetch("https://www.tcs.com/report")
    assert error.value.details["error_type"] == "ReadTimeout"
    assert error.value.details["stage"] == "ROBOTS"


def test_content_404_does_not_get_robots_exception():
    session = Session(Response(404), Response(404))
    with pytest.raises(SourceBlocked) as error:
        PublicFetcher(session=session, delay=0).fetch("https://www.tcs.com/report")
    assert error.value.details["stage"] == "DOCUMENT"
    assert error.value.details["status_code"] == 404


def test_redirect_to_disallowed_path_is_not_requested():
    session = Session(Response(200, b"User-agent: *\nDisallow: /private\n"),
                      Response(302, Location="/private/report"))
    with pytest.raises(SourceBlocked, match="disallows"):
        PublicFetcher(session=session, delay=0).fetch("https://www.tcs.com/report")
    assert len(session.urls) == 2


def test_cross_host_redirect_is_not_requested():
    session = Session(Response(404), Response(302, Location="https://www.infosys.com/report"))
    with pytest.raises(SourceBlocked, match="Cross-origin"):
        PublicFetcher(session=session, delay=0).fetch("https://www.tcs.com/report")
    assert len(session.urls) == 2


def test_one_policy_fetch_for_same_origin():
    session = Session(Response(404), Response(200, b"one"), Response(200, b"two"))
    fetcher = PublicFetcher(session=session, delay=0)
    fetcher.fetch("https://www.tcs.com/one")
    fetcher.fetch("https://www.tcs.com/two")
    assert sum(url.endswith("robots.txt") for url in session.urls) == 1


def test_content_403_opens_host_circuit():
    session = Session(Response(404), Response(403))
    fetcher = PublicFetcher(session=session, delay=0)
    with pytest.raises(SourceBlocked):
        fetcher.fetch("https://www.tcs.com/one")
    with pytest.raises(SourceBlocked) as retry:
        fetcher.fetch("https://www.tcs.com/two")
    assert retry.value.details["cached_failure"] is True
    assert len(session.urls) == 2
