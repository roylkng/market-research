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
SEMANTIC_FIELD_TOKENS = ("currency", "unit", "basis", "provider")
LEGACY_SAFE_FIELDS = (
    "symbol",
    "fiscal_period",
    "period_ending",
    "consensus_eps",
    "analyst_count",
    "source_url",
    "source_status",
    "source_observed_market_date",
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


def audit_legacy_snapshot_semantics(snapshot: dict, symbols: list[str]) -> dict:
    observations = snapshot.get("observations")
    if not isinstance(observations, list):
        raise ValueError("legacy snapshot observations must be a list")

    rows = [row for row in observations if isinstance(row, dict)]
    all_keys = sorted({key for row in rows for key in row})
    semantic_fields = sorted(
        key
        for key in all_keys
        if any(token in key.lower() for token in SEMANTIC_FIELD_TOKENS)
    )
    by_symbol = {row.get("symbol"): row for row in rows if isinstance(row.get("symbol"), str)}

    selected: list[dict] = []
    for symbol in symbols:
        row = by_symbol.get(symbol)
        if row is None:
            selected.append({"symbol": symbol, "present": False})
            continue
        retained_fields = {
            field: row.get(field)
            for field in (*LEGACY_SAFE_FIELDS, *semantic_fields)
            if field in row
        }
        retained_fields["present"] = True
        selected.append(retained_fields)

    rows_with_semantic_fields = sum(
        any(field in row and row.get(field) is not None for field in semantic_fields)
        for row in rows
    )
    rows_with_period_ending = sum(
        isinstance(row.get("period_ending"), str) and bool(row["period_ending"].strip())
        for row in rows
    )
    return {
        "observation_count": len(rows),
        "observation_keys": all_keys,
        "semantic_field_names": semantic_fields,
        "rows_with_non_null_semantic_field": rows_with_semantic_fields,
        "rows_with_period_ending": rows_with_period_ending,
        "selected_symbols": selected,
    }
