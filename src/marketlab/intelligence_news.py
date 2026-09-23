"""Date-aware discovery parsers. Text matches are research leads, never alpha.

Provider adapters describe document structure, not individual company releases.
No article URL or expected financial value is an input to discovery.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, time
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_http import MAX_BYTES, SourceBlocked, approved_url
from marketlab.intelligence_store import digest, timestamp

VERSION = "NEWS-DISCOVERY-V1"
ATOM = "{http://www.w3.org/2005/Atom}"
PRN_ARTICLE = re.compile(r"/(?:in/)?news-releases/[^/?]+-(\d{8,12})\.html$")
MONTHS = {name: i for i, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
TOPICS = {
    "CAPACITY_INVESTMENT": r"\b(?:capex|capacity|commission\w*|manufacturing facility|factory|invest\w*)\b",
    "ORDER_CUSTOMER": r"\b(?:order|orders|contract|contracts|bookings|customer win|letter of (?:award|acceptance))\b",
    "RESULTS_GUIDANCE": r"\b(?:earnings|quarter\w*|financial results|guidance|outlook|revenue|profit)\b",
    "PRODUCT_APPROVAL": r"\b(?:launch\w*|approval|approved|patent\w*|new product|commercialisation)\b",
    "CAPITAL_TRANSACTION": r"\b(?:merger|acqui\w*|divest\w*|disposal|buyback|share swap|fundrais\w*)\b",
    "GOVERNANCE_RISK": r"\b(?:fraud|default|resign\w*|auditor|investigation|insolvency|litigation)\b",
    "POLICY_REGULATION": r"\b(?:regulat\w*|circular|tariff\w*|government|tax|subsid\w*|policy)\b",
}
QUESTIONS = {
    "CAPACITY_INVESTMENT": "Verify announced versus commissioned capacity, utilisation, funding, incremental cash flow and diluted-share economics.",
    "ORDER_CUSTOMER": "Verify firm versus conditional award, incremental backlog, delivery dates, margins and working-capital requirements.",
    "RESULTS_GUIDANCE": "Reconcile reporting basis, forecast period, recurring earnings, cash conversion and prior independent expectations.",
    "PRODUCT_APPROVAL": "Verify approval scope, paying customers, commercial timing, unit economics and which listed entity benefits.",
    "CAPITAL_TRANSACTION": "Verify approvals, attributable proceeds, dilution, debt changes and per-share value rather than headline transaction size.",
    "GOVERNANCE_RISK": "Check the original disclosure, denials, scope and financing or governance consequences before interpreting direction.",
    "POLICY_REGULATION": "Verify legal scope and effective date, then establish company-specific exposure instead of assuming sector-wide benefit.",
}


def clean(value: str) -> str:
    return " ".join(value.split())


def canonical_url(value: str) -> str:
    """Remove tracking only. Preserve identifiers such as PRID and announcement ID."""
    p = urlparse(value)
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.casefold().startswith("utm_") and k.casefold() not in {"gclid", "fbclid"}]
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path, p.params,
                       urlencode(sorted(query)), ""))


def resource_key(url: str) -> str:
    p = urlparse(url)
    match = PRN_ARTICLE.search(p.path) if p.hostname == "www.prnewswire.com" else None
    return "prn:" + match[1] if match else canonical_url(url)


def publication(value: str, zone: str = "Asia/Kolkata") -> dict:
    """Never interpret a time-only listing label as today's publication date."""
    value = clean(value)
    if not value:
        return {"value": None, "precision": "UNKNOWN", "raw": value}
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            return {"value": dt.astimezone(UTC).isoformat(), "precision": "SECOND", "raw": value}
    except ValueError:
        pass
    try:
        day = date.fromisoformat(value)
    except ValueError:
        day = None
    if day is None and re.search(r"\b(?:19|20)\d{2}\b", value):
        try:
            dt = parsedate_to_datetime(value.replace(" IST", " +0530"))
            if dt.tzinfo is not None:
                return {"value": dt.astimezone(UTC).isoformat(), "precision": "SECOND", "raw": value}
        except (ValueError, TypeError):
            pass
        matches = [re.search(r"\b(\d{1,2})\s+([A-Za-z]+),?\s+(20\d{2})\b", value),
                   re.search(r"\b([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(20\d{2})\b", value)]
        for index, m in enumerate(matches):
            if m:
                d, month = (m[1], m[2]) if index == 0 else (m[2], m[1])
                if month.casefold()[:3] in MONTHS:
                    try:
                        day = date(int(m[3]), MONTHS[month.casefold()[:3]], int(d))
                    except ValueError:
                        continue
                    break
    if day:
        upper = datetime.combine(day, time.max, ZoneInfo(zone)).astimezone(UTC)
        return {"value": upper.isoformat(), "precision": "DAY_UPPER_BOUND", "raw": value}
    return {"value": None, "precision": "UNKNOWN", "raw": value}


def _xml_text(node, name: str) -> str:
    child = node.find(name)
    return clean("".join(child.itertext())) if child is not None else ""


def parse_feed(raw: bytes, source: dict) -> list[dict]:
    if len(raw) > MAX_BYTES or b"\x00" in raw or re.search(rb"<!\s*(DOCTYPE|ENTITY)", raw, re.IGNORECASE):
        raise EvidenceError("Unsafe or oversized XML")
    root = ET.fromstring(raw)
    if root.tag == "rss" and root.find("channel") is not None:
        nodes, atom = root.findall("./channel/item"), False
    elif root.tag == ATOM + "feed":
        nodes, atom = root.findall(ATOM + "entry"), True
    else:
        raise EvidenceError("Unsupported feed schema")
    if len(nodes) > 5000:
        raise EvidenceError("Feed item limit exceeded")
    result = []
    for node in nodes:
        prefix = ATOM if atom else ""
        title = _xml_text(node, prefix + "title")
        link = _xml_text(node, "link")
        if atom:
            links = [n.get("href", "") for n in node.findall(ATOM + "link")
                     if n.get("rel", "alternate") == "alternate"]
            link = links[0] if len(set(links)) == 1 else ""
        published = _xml_text(node, prefix + "published" if atom else "pubDate")
        if not published and not atom:
            published = _xml_text(node, "{http://purl.org/dc/elements/1.1/}date")
        result.append({"title": title, "url": canonical_url(urljoin(source["url"], link)) if link else "",
            "publication": publication(published, source.get("timezone", "Asia/Kolkata")),
            "provider_id": _xml_text(node, ATOM + "id" if atom else "guid"),
            "updated_raw": _xml_text(node, ATOM + "updated") if atom else "",
            "item_status": "DISCOVERED" if title and link else "MALFORMED_ITEM",
            "item_sha256": digest(ET.tostring(node, encoding="unicode"))})
    return result


def parse_listing(raw: bytes, source: dict) -> tuple[list[dict], list[str]]:
    if len(raw) > MAX_BYTES:
        raise EvidenceError("Listing exceeds body limit")
    soup = BeautifulSoup(raw, "html.parser")
    if not soup.find("h1", string=re.compile("All News Releases", re.IGNORECASE)):
        raise EvidenceError("PRNewswire listing identity changed")
    results = {}
    for node in soup.select("a[href]"):
        url = canonical_url(urljoin(source["url"], node["href"]))
        p = urlparse(url)
        if p.hostname != "www.prnewswire.com" or not PRN_ARTICLE.search(p.path):
            continue
        heading = node.find(["h2", "h3"])
        if heading is None:
            continue  # Excludes navigation, language copies and unrelated footer links.
        date_node = heading.find("small") or node.find("time")
        when = clean(date_node.get_text(" ")) if date_node else ""
        fragment = BeautifulSoup(str(heading), "html.parser")
        for small in fragment.select("small,time"):
            small.decompose()
        title = clean(fragment.get_text(" "))
        results[url] = {"title": title, "url": url, "publication": publication(when),
                        "provider_id": resource_key(url), "updated_raw": "",
                        "item_status": "DISCOVERED", "item_sha256": digest(str(node))}
    if not results:
        raise EvidenceError("No article cards found, cannot treat layout failure as empty news")
    pages = sorted({canonical_url(urljoin(source["url"], n["href"])) for n in soup.select("a[href]")
                    if n.get_text(strip=True).isdigit() and
                    urlparse(urljoin(source["url"], n["href"])).path == urlparse(source["url"]).path})
    return list(results.values()), pages


def entity_mentions(text: str, members: list[dict]) -> dict:
    """Resolve exact company aliases while keeping deep-panel scope distinct."""
    def normalize(value):
        return clean(re.sub(r"[^a-z0-9]+", " ", value.casefold().replace("&", " and ")))

    haystack = " " + normalize(text) + " "
    aliases: dict[str, set[str]] = {}
    deep_symbols: set[str] = set()
    official_symbols: set[str] = set()
    for row in members:
        symbol = row["symbol"]
        identity_source = row.get("identity_source")
        if bool(row.get("is_deep_panel", identity_source != "NSE_UDIFF_PRIOR_SESSION")):
            deep_symbols.add(symbol)
        if identity_source == "NSE_UDIFF_PRIOR_SESSION":
            official_symbols.add(symbol)
        name = re.sub(
            r"\b(?:limited|ltd)\.?$",
            "",
            row["company_name"],
            flags=re.IGNORECASE,
        ).strip()
        alias = normalize(name)
        if len(alias) >= 5:
            aliases.setdefault(alias, set()).add(symbol)

    matched: set[str] = set()
    ambiguous = []
    for alias, symbols in aliases.items():
        if " " + alias + " " in haystack:
            if len(symbols) == 1:
                matched.update(symbols)
            else:
                ambiguous.append({"alias": alias, "symbols": sorted(symbols)})

    explicit = sorted(
        set(re.findall(r"\bNSE\s*:\s*([A-Z0-9][A-Z0-9&_\-]{1,24})\b", text))
    )
    known = {row["symbol"] for row in members}
    matched.update(set(explicit) & known)
    return {
        "panel_symbols": sorted(matched & deep_symbols),
        "official_nse_symbols": sorted(matched & official_symbols),
        "ambiguous_mentions": ambiguous,
        "unverified_nse_symbols": sorted(set(explicit) - known),
        "bse_codes_for_review": sorted(
            set(re.findall(r"\bBSE\s*:\s*(\d{5,6})\b", text))
        ),
        "relationship_state": "MENTION_ONLY_NOT_BENEFICIARY_VERIFICATION",
    }


def topic_candidates(text: str) -> list[dict]:
    result = []
    for name, pattern in TOPICS.items():
        hit = re.search(pattern, text, flags=re.IGNORECASE)
        if hit:
            result.append({"topic": name, "match_start": hit.start(), "match_end": hit.end(),
                           "matched_text": hit.group(), "review_question": QUESTIONS[name],
                           "status": "TEXT_TOPIC_NOT_CONFIRMED_EVENT"})
    return result


def document_body(raw: bytes, source: dict) -> dict:
    if len(raw) > MAX_BYTES:
        raise EvidenceError("Document exceeds body limit")
    soup = BeautifulSoup(raw, "html.parser")
    provider = source["document_parser"]
    selector = {"prnewswire": "section.release-body", "pib": ".innner-page-main-about-us-content-right-part",
                "sebi": "#content"}.get(provider)
    if selector is None:
        raise EvidenceError("Unsupported document adapter")
    body = soup.select_one(selector)
    title = soup.select_one("article.news-release h1") if provider == "prnewswire" else soup.find("h1")
    if body is None or title is None:
        raise EvidenceError("Article body/title selectors did not resolve")
    for node in body.select("script,style,nav,header,footer,noscript"):
        node.decompose()
    text = clean(body.get_text(" ", strip=True))
    if len(text) < 100:
        raise EvidenceError("Article body too short")
    dates = []
    for node in soup.select('meta[name="date"],meta[property="article:published_time"]'):
        dates.append(publication(node.get("content", ""), source.get("timezone", "Asia/Kolkata")))
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(node.string or node.get_text())
        except (ValueError, TypeError):
            continue
        values = payload if isinstance(payload, list) else [payload]
        for item in values:
            if not isinstance(item, dict):
                continue
            nested = item.get("@graph", [item])
            for part in nested if isinstance(nested, list) else []:
                types = part.get("@type", []) if isinstance(part, dict) else []
                types = [types] if isinstance(types, str) else types
                if isinstance(types, list) and any(t in ("NewsArticle", "Article") for t in types):
                    dates.append(publication(str(part.get("datePublished", "")), source.get("timezone", "Asia/Kolkata")))
    dates = [d for d in dates if d["value"]]
    unique = {timestamp(d["value"]) for d in dates}
    chosen = dates[0] if len(unique) == 1 else {"value": None, "precision": "CONFLICTING" if unique else "UNKNOWN", "raw": ""}
    # Identity and topics use the lead, not references from the boilerplate list.
    lead = re.split(r"\bAbout\s+(?:the\s+)?[A-Z]", text, maxsplit=1)[0][:12000]
    return {"title": clean(title.get_text(" ", strip=True)), "body": text,
            "lead": lead, "publication": chosen, "publication_candidates": dates,
            "distributor": source["publisher"], "independent_corroboration": False}


def link_allowed(url: str, source: dict) -> bool:
    try:
        approved_url(url)
    except SourceBlocked:
        return False
    p = urlparse(url)
    return bool(p.hostname in source["article_hosts"] and
                re.fullmatch(source["article_path_pattern"], p.path))
