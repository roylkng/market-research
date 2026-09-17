"""Bounded public-source adapters. RSS entries are leads, not verified facts."""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, time as day_time
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_store import digest, now_text, timestamp

USER_AGENT = "MarketLabResearch/2.0 (+https://github.com/roylkng/market-research)"
ALLOWED_HOSTS = frozenset({"www.nseindia.com", "nsearchives.nseindia.com",
                           "archives.nseindia.com", "www.tcs.com", "www.infosys.com",
                           "investors.larsentoubro.com", "www.larsentoubro.com"})
MAX_BYTES = 4 * 1024 * 1024


class SourceBlocked(EvidenceError):
    pass


def approved_url(value: str) -> str:
    p = urlparse(value)
    if (p.scheme != "https" or p.hostname not in ALLOWED_HOSTS or
            p.username or p.password or p.port not in (None, 443)):
        raise SourceBlocked("Unapproved source URL or redirect")
    return value


class PublicFetcher:
    """No cookies/login, browser impersonation, proxy rotation or access bypass.

    A robots failure blocks acquisition. No automatic retries on 401/403/429.
    Redirect destinations are checked before requesting them.
    """

    def __init__(self, *, session=None, delay: float = 1.0):
        self.session = session if session is not None else requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.robots: dict[str, tuple[RobotFileParser, dict]] = {}
        self.delay = delay

    def _read(self, url: str) -> tuple[bytes, dict]:
        initial_host = urlparse(url).netloc
        for _ in range(4):
            approved_url(url)
            if urlparse(url).netloc != initial_host:
                raise SourceBlocked("Cross-origin redirect requires a separately reviewed URL")
            if self.delay:
                time.sleep(self.delay)
            with self.session.get(url, timeout=(10, 30), allow_redirects=False,
                                  stream=True) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        raise SourceBlocked("Redirect has no destination")
                    url = approved_url(urljoin(url, location))
                    continue
                if response.status_code in {401, 403, 429}:
                    raise SourceBlocked(f"Access/rate limit HTTP {response.status_code}")
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_content(chunk_size=32768):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise SourceBlocked("Source exceeds bounded body size")
                    chunks.append(chunk)
                return b"".join(chunks), {"resolved_url": url,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("Content-Type", ""),
                    "observed_at": now_text()}
        raise SourceBlocked("Too many redirects")

    def fetch(self, url: str) -> tuple[bytes, dict]:
        approved_url(url)
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self.robots:
            raw, metadata = self._read(origin + "/robots.txt")
            text = raw.decode("utf-8-sig", errors="strict")
            if "<html" in text.lower() or "<body" in text.lower():
                raise SourceBlocked("Robots response is HTML, not a policy")
            parser = RobotFileParser(origin + "/robots.txt")
            parser.parse(text.splitlines())
            self.robots[origin] = (parser, {**metadata, "policy_sha256": digest(text)})
        parser, policy = self.robots[origin]
        if not parser.can_fetch(USER_AGENT, url):
            raise SourceBlocked("Robots disallows source")
        delay = parser.crawl_delay(USER_AGENT)
        rate = parser.request_rate(USER_AGENT)
        if delay and delay > self.delay:
            time.sleep(delay - self.delay)
        if rate:
            time.sleep(rate.seconds / rate.requests)
        raw, metadata = self._read(url)
        # Cross-origin redirects require a separate robots check, not implicit trust.
        if urlparse(metadata["resolved_url"]).netloc != p.netloc:
            raise SourceBlocked("Cross-origin content redirect requires reviewed source URL")
        return raw, {**metadata, "robots_policy": policy}


def normalized_html(raw: bytes) -> str:
    if len(raw) > MAX_BYTES:
        raise EvidenceError("HTML exceeds body limit")
    soup = BeautifulSoup(raw, "html.parser")
    for node in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        node.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


def extract_claims(text: str, spec: dict) -> list[dict]:
    """Reviewed deterministic extractors. Matching bytes establish reported text,
    not economic truth, completeness, independent corroboration or a forecast.
    """
    if any(marker not in text for marker in spec.get("required_markers", [])):
        raise EvidenceError("Source identity/period markers changed")
    result = []
    for field in spec.get("fields", []):
        matches = list(re.finditer(field["pattern"], text, flags=re.IGNORECASE))
        if not matches:
            raise EvidenceError(f"Required field not found: {field['concept']}")
        values = {match.group("value").replace(",", "").strip() for match in matches}
        if len(values) != 1:
            raise EvidenceError(f"Ambiguous reported field: {field['concept']}")
        result.append({**{k: field[k] for k in ("concept", "facet", "unit", "currency", "basis")},
                       "value": next(iter(values)), "period_end": spec["period_end"],
                       "quote": matches[0].group(), "span_start": matches[0].start(),
                       "span_end": matches[0].end(), "role": field.get("role", "REPORTED_FACT")})
    return result


def publication_upper_bound(spec: dict) -> str | None:
    value = spec.get("publication_date")
    if value is None:
        return None
    day = datetime.strptime(value, "%Y-%m-%d").date()
    return datetime.combine(day, day_time.max, ZoneInfo("Asia/Kolkata")).astimezone(UTC).isoformat()


def _rss_time(value: str) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(UTC).isoformat()
    except (TypeError, ValueError):
        return None


def _identity(text: str) -> str:
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"\bltd\b", "limited", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def parse_rss(raw: bytes, *, members: list[dict], source_id: str,
              observed_at: str) -> list[dict]:
    """Retain every item, including unmatched/out-of-panel/malformed items.

    Snapshot-only feeds never prove a complete historical news window. No
    financial fact or tradability label is inferred from a headline.
    """
    timestamp(observed_at)
    if len(raw) > MAX_BYTES or b"\x00" in raw or re.search(
            rb"<!\s*(DOCTYPE|ENTITY)", raw, re.I):
        raise EvidenceError("Unsafe or unsupported XML")
    root = ET.fromstring(raw)
    if root.tag != "rss" or root.find("channel") is None:
        raise EvidenceError("Unsupported RSS schema")
    aliases: dict[str, set[str]] = {}
    for company in members:
        for name in (company["symbol"], company["company_name"]):
            aliases.setdefault(_identity(name), set()).add(company["symbol"])
    result = []
    for index, item in enumerate(root.findall("./channel/item")):
        title = " ".join("".join(item.findtext("title", "")).split())
        link = item.findtext("link", "").strip()
        guid = item.findtext("guid", "").strip() or link or f"missing-id:{index}"
        published = _rss_time(item.findtext("pubDate", "").strip())
        explicit_symbol = item.findtext("symbol", "").strip()
        matched = aliases.get(_identity(explicit_symbol or title), set())
        status = "MATCHED" if len(matched) == 1 else "AMBIGUOUS" if matched else "UNRESOLVED"
        try:
            approved_url(link)
            link_state = "APPROVED_NOT_FETCHED"
        except SourceBlocked:
            link_state = "BLOCKED_UNREVIEWED_LINK"
        payload = {"source_id": source_id, "origin_id": digest([source_id, guid]),
                   "title": title, "link": link, "published_at": published,
                   "publication_state": "OBSERVED" if published else "UNRESOLVED",
                   "first_seen_at": observed_at, "symbols": sorted(matched),
                   "identity_state": status, "attachment_state": link_state,
                   "status": "DISCOVERY_LEAD_NOT_VERIFIED_FACT",
                   "description_sha256": digest(item.findtext("description", ""))}
        payload["lead_id"] = digest({k: v for k, v in payload.items() if k != "first_seen_at"})
        result.append(payload)
    return result
