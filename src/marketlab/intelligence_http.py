"""Observable, bounded public-source transport. No credentials or access bypass.

404/410 robots responses mean unavailable policy (RFC 9309 section 2.3.1.3).
401/403/429, transport failures and server errors remain blocking. A content
404 never inherits the robots exception. Every redirect is checked before GET.
"""
from __future__ import annotations

import time
from urllib.parse import urljoin, urlparse

import requests

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_robots import ConservativeRobotPolicy
from marketlab.intelligence_store import now_text, sha256

USER_AGENT = "MarketLabResearch/2.0 (+https://github.com/roylkng/market-research)"
ALLOWED_HOSTS = frozenset({
    "www.nseindia.com", "nsearchives.nseindia.com", "archives.nseindia.com",
    "www.tcs.com", "www.infosys.com", "investors.larsentoubro.com",
    "www.larsentoubro.com", "www.hcltech.com", "www.prnewswire.com",
    "www.sebi.gov.in", "www.pib.gov.in", "www.livemint.com",
})
MAX_BYTES = 4 * 1024 * 1024
REDIRECTS = {301, 302, 303, 307, 308}


class SourceBlocked(EvidenceError):
    def __init__(self, reason: str, *, stage="POLICY", url="", status_code=None,
                 error_type=None):
        super().__init__(reason)
        self.details = {"stage": stage, "url": url, "status_code": status_code,
                        "reason": reason, "error_type": error_type,
                        "observed_at": now_text()}


def approved_url(value: str) -> str:
    try:
        p = urlparse(value)
        valid = (p.scheme == "https" and p.hostname in ALLOWED_HOSTS
                 and not p.username and not p.password and p.port in (None, 443)
                 and not p.fragment)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise SourceBlocked("Unapproved source URL or redirect")
    return value


class PublicFetcher:
    """One source run has a shared policy cache and host-block circuit breaker.

    Trace records retain stage, URL, status and observation time, never tokens or
    response headers. No error proves that all documents on a domain are absent.
    """
    def __init__(self, *, session=None, delay=1.0, read_timeout=20.0):
        if delay < 0 or read_timeout <= 0:
            raise EvidenceError("Invalid fetch bounds")
        self.session = session if session is not None else requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.delay, self.read_timeout = delay, read_timeout
        self.policies = {}
        self.blocks = {}
        self.trace = []

    def _request(self, url, stage, *, max_bytes=MAX_BYTES):
        approved_url(url)
        started = time.monotonic()
        event = {"stage": stage, "url": url, "started_at": now_text()}
        try:
            if self.delay:
                time.sleep(self.delay)
            with self.session.get(url, timeout=(10, self.read_timeout),
                                  allow_redirects=False, stream=True) as response:
                status = response.status_code
                event["status_code"] = status
                metadata = {"resolved_url": url, "status_code": status,
                            "content_type": response.headers.get("Content-Type", "")}
                if status in REDIRECTS:
                    location = response.headers.get("Location")
                    if not location:
                        raise SourceBlocked("Redirect has no destination", stage=stage,
                                            url=url, status_code=status)
                    metadata["location"] = urljoin(url, location)
                    return b"", metadata
                if stage == "ROBOTS" and status in {404, 410}:
                    return b"", metadata
                if status != 200:
                    raise SourceBlocked(f"HTTP {status}", stage=stage, url=url,
                                        status_code=status)
                chunks, size = [], 0
                for chunk in response.iter_content(chunk_size=32768):
                    size += len(chunk)
                    if size > max_bytes or time.monotonic() - started > self.read_timeout + 10:
                        raise SourceBlocked("Response exceeds size/time bounds", stage=stage,
                                            url=url, status_code=status)
                    chunks.append(chunk)
                raw = b"".join(chunks)
                event["byte_count"] = len(raw)
                event["raw_sha256"] = sha256(raw)
                return raw, metadata
        except requests.RequestException as exc:
            event["error_type"] = type(exc).__name__
            raise SourceBlocked("Transport failure", stage=stage, url=url,
                                error_type=type(exc).__name__) from exc
        except SourceBlocked as exc:
            event.update(error_type=type(exc).__name__, reason=str(exc))
            raise
        finally:
            event["completed_at"] = now_text()
            self.trace.append(event)

    def _policy(self, origin):
        cached = self.policies.get(origin)
        if cached and time.monotonic() - cached[2] < 24 * 3600:
            return cached[:2]
        url = origin + "/robots.txt"
        for attempt in range(1, 6):
            try:
                raw, response = self._request(url, "ROBOTS", max_bytes=512000)
            except SourceBlocked as exc:
                details = exc.details
                transient = (
                    details.get("stage") == "ROBOTS"
                    and (
                        details.get("error_type") in {
                            "ReadTimeout", "ConnectTimeout", "ConnectionError", "Timeout"
                        }
                        or details.get("status_code") in {429, 500, 502, 503, 504}
                    )
                )
                if transient and attempt < 5:
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
                raise
            if response["status_code"] in REDIRECTS:
                target = approved_url(response["location"])
                if f"https://{urlparse(target).netloc}" != origin:
                    raise SourceBlocked(
                        "Cross-origin policy redirect requires review",
                        stage="ROBOTS",
                        url=target,
                    )
                url = target
                continue
            status = response["status_code"]
            parser = ConservativeRobotPolicy(origin + "/robots.txt")
            if status in {404, 410}:
                parser.parse(["User-agent: *", "Disallow:"])
                metadata = {
                    "url": url,
                    "status_code": status,
                    "policy_state": "UNAVAILABLE_404_410",
                    "raw_sha256": None,
                    "observed_at": now_text(),
                }
            else:
                text = raw.decode("utf-8-sig", errors="strict")
                if "<html" in text.casefold() or "<body" in text.casefold():
                    raise SourceBlocked(
                        "Robots response is HTML",
                        stage="ROBOTS",
                        url=url,
                        status_code=status,
                    )
                parser.parse(text.splitlines())
                metadata = {
                    "url": url,
                    "status_code": status,
                    "policy_state": "PARSED",
                    "raw_sha256": sha256(raw),
                    "observed_at": now_text(),
                }
            self.policies[origin] = (parser, metadata, time.monotonic())
            return parser, metadata
        raise SourceBlocked("Too many policy redirects", stage="ROBOTS", url=url)

    def fetch(self, url, *, url_guard=None):
        approved_url(url)
        origin = f"https://{urlparse(url).netloc}"
        cached = self.blocks.get(origin)
        if cached and time.monotonic() - cached[1] < 3600:
            prior = cached[0]
            error = SourceBlocked("Host blocked earlier in this source run", stage=prior["stage"],
                                  url=prior["url"], status_code=prior["status_code"],
                                  error_type=prior["error_type"])
            error.details["cached_failure"] = True
            error.details["original_failure"] = prior
            raise error
        try:
            parser, policy = self._policy(origin)
            for _ in range(5):
                approved_url(url)
                if f"https://{urlparse(url).netloc}" != origin:
                    raise SourceBlocked("Cross-origin content redirect requires review", stage="DOCUMENT", url=url)
                if url_guard is not None and not url_guard(url):
                    raise SourceBlocked("Discovery scope rejects redirect or path", stage="DOCUMENT", url=url)
                if not parser.can_fetch(USER_AGENT, url):
                    raise SourceBlocked("Robots disallows source", stage="POLICY", url=url)
                delay = parser.crawl_delay(USER_AGENT) or 0
                rate = parser.request_rate(USER_AGENT)
                required = max(delay, rate.seconds / rate.requests if rate else 0)
                if required > self.delay:
                    time.sleep(required - self.delay)
                raw, metadata = self._request(url, "DOCUMENT")
                if metadata["status_code"] in REDIRECTS:
                    url = approved_url(metadata["location"])
                    continue
                return raw, {**metadata, "observed_at": now_text(), "robots_policy": policy}
            raise SourceBlocked("Too many content redirects", stage="DOCUMENT", url=url)
        except SourceBlocked as exc:
            if exc.details["stage"] == "ROBOTS" or exc.details["status_code"] in {401, 403, 429}:
                self.blocks[origin] = (dict(exc.details), time.monotonic())
            raise
