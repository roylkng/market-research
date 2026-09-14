from __future__ import annotations

import hashlib
from urllib.parse import quote, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

STOCKANALYSIS_HOST = "stockanalysis.com"
ROBOTS_URL = "https://stockanalysis.com/robots.txt"
REQUIRED_TEXT_MARKERS = (
    "Financial Forecast",
    "EPS Forecast",
    "Revenue Forecast",
    "No. Analysts",
    "S&P Global Market Intelligence",
)


def forecast_url(symbol: str) -> str:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")
    encoded = quote(symbol.strip(), safe="-")
    return f"https://stockanalysis.com/quote/nse/{encoded}/forecast/"


def robots_allows(robots_text: str, user_agent: str, url: str) -> bool:
    parser = RobotFileParser()
    parser.set_url(ROBOTS_URL)
    parser.parse(robots_text.splitlines())
    return parser.can_fetch(user_agent, url)


def inspect_forecast_page(
    *,
    symbol: str,
    requested_url: str,
    status_code: int,
    final_url: str,
    content_type: str | None,
    body: bytes,
) -> dict:
    body_sha256 = hashlib.sha256(body).hexdigest()
    final_host = (urlparse(final_url).hostname or "").lower()
    is_html = bool(content_type and "text/html" in content_type.lower())

    text = ""
    if body and is_html:
        text = BeautifulSoup(body, "html.parser").get_text(" ", strip=True)
    marker_presence = {marker: marker in text for marker in REQUIRED_TEXT_MARKERS}
    identity_marker = f"NSE:{symbol}"
    identity_verified = identity_marker in text

    probe_pass = (
        status_code == 200
        and final_host == STOCKANALYSIS_HOST
        and is_html
        and identity_verified
        and all(marker_presence.values())
    )
    return {
        "symbol": symbol,
        "requested_url": requested_url,
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "content_length": len(body),
        "sha256": body_sha256,
        "identity_marker": identity_marker,
        "identity_verified": identity_verified,
        "required_marker_presence": marker_presence,
        "probe_pass": probe_pass,
    }
