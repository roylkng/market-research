"""Bounded public-source adapters. RSS entries are leads, not verified facts."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from datetime import time as day_time
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_http import MAX_BYTES, PublicFetcher, SourceBlocked, approved_url
from marketlab.intelligence_store import digest, timestamp

__all__ = ["PublicFetcher", "SourceBlocked", "approved_url", "extract_claims",
           "normalized_html", "parse_rss", "publication_upper_bound"]


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
                       "value": next(iter(values)), "period_end": field.get("period_end", spec["period_end"]),
                       "quote": matches[0].group(), "span_start": matches[0].start(),
                       "span_end": matches[0].end(), "role": field.get("role", "REPORTED_FACT")})
    return result


def publication_upper_bound(spec: dict) -> str | None:
    value = spec.get("publication_date")
    if value is None:
        return None
    day = date.fromisoformat(value)
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
            rb"<!\s*(DOCTYPE|ENTITY)", raw, re.IGNORECASE):
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
