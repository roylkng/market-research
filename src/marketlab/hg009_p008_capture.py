"""Capture original FY26 NSE issuer iXBRL bytes with actual UTC provenance.

The source is BLOCKED unless company, ISIN, consolidated FY26 basis and
the exact originally transcribed cash-flow row numbers match. An NSE 403
or missing row is an explicit failed source receipt, never a financial fact.
"""

from __future__ import annotations

import gzip
import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from requests.exceptions import RequestException

from marketlab.alpha import AlphaContractError, digest

SOURCE_URL_PREFIX = "https://nsearchives.nseindia.com/corporate/ixbrl/"
EXPECTED_ROWS = {
    "pretax_profit": ("profit before tax", "total profit before tax"),
    "operating_cfo": ("net cash flows from (used in) operating activities",),
    "ppe_purchase": ("purchase of property, plant and equipment",),
}


def _source_token(amount: float) -> str:
    return f"{float(amount):,.2f}"


def validate_issuer_html(
    raw: bytes, facts: dict[str, Any], *, observed_at_utc: str
) -> dict[str, Any]:
    if not raw or len(raw) > 2_000_000:
        raise AlphaContractError("P008 original NSE issuer HTML empty or oversized")
    url = facts.get("original_url")
    if not isinstance(url, str) or not url.startswith(SOURCE_URL_PREFIX):
        raise AlphaContractError("P008 original NSE source URL invalid")
    if re.search(r"https?://", url[len(SOURCE_URL_PREFIX):]):
        raise AlphaContractError("P008 source URL cannot contain external redirect")
    stamp = datetime.fromisoformat(observed_at_utc)
    if stamp.tzinfo is None:
        raise AlphaContractError("P008 original retrieval timestamp lacks timezone")
    content = BeautifulSoup(raw, "html.parser")
    text = content.get_text(" ", strip=True)
    symbol = facts.get("symbol")
    isin = facts.get("isin")
    if (
        not isinstance(symbol, str)
        or not isinstance(isin, str)
        or not re.search(rf"\b{re.escape(symbol)}\b", text, re.IGNORECASE)
        or not re.search(rf"\b{re.escape(isin)}\b", text, re.IGNORECASE)
        or "31-03-2026" not in text
        or "Consolidated" not in text
        or "Audited" not in text
    ):
        raise AlphaContractError("P008 wrong symbol/ISIN/period/reporting basis")
    # NSE iXBRL cash-flow labels contain embedded newlines/indentation in
    # the ORIGINAL HTML text nodes. get_text(separator=...) does not normalize
    # whitespace within a node, which previously quarantined valid FY26 rows.
    # Restrict matching to leaf table rows rather than outer nested tables.
    rows = [
        " ".join(row.get_text(" ", strip=True).casefold().split())
        for row in content.find_all("tr")
        if row.find("tr") is None
    ]
    for key, labels in EXPECTED_ROWS.items():
        token = _source_token(facts[key]).casefold()
        if not any(
            token in line and any(label in line for label in labels)
            for line in rows
        ):
            raise AlphaContractError(f"P008 original NSE statement row unverified: {key}")
    return {
        "symbol": symbol,
        "isin": isin,
        "period_end": facts["period_end"],
        "reporting_basis": facts["reporting_basis"],
        "original_exchange_url": url,
        "captured_at_utc": stamp.astimezone(UTC).isoformat(),
        "raw_byte_count": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "validation_state": "ORIGINAL_NSE_FY26_CASHFLOW_SOURCE_BYTES_ROW_MATCHED",
        "financial_values_are_normalized_owner_fcf": False,
        "fully_diluted_parent_value_verified": False,
        "live_capital_allowed": False,
    }


def capture_issuer(
    facts: dict[str, Any],
    *,
    fetch: Callable[[str], tuple[int, bytes | None]],
    now_utc: datetime,
    root: Path,
) -> dict[str, Any]:
    symbol = facts["symbol"]
    if now_utc.tzinfo is None:
        raise AlphaContractError("P008 actual capture clock must be aware")
    captured = now_utc.astimezone(UTC).isoformat()
    try:
        status, raw = fetch(facts["original_url"])
    except (RequestException, OSError) as exc:
        status, raw = None, None
        failure = type(exc).__name__
    else:
        failure = None
    if status != 200 or raw is None:
        return {
            "symbol": symbol,
            "source_url": facts["original_url"],
            "captured_at_utc": captured,
            "state": "BLOCKED_ORIGINAL_NSE_HTTP",
            "http_status": status,
            "error_class": failure,
            "raw_sha256": None,
            "original_raw_repo_path": None,
            "live_capital_allowed": False,
        }
    try:
        parsed = validate_issuer_html(raw, facts, observed_at_utc=captured)
    except (AlphaContractError, UnicodeError, ValueError) as exc:
        # An unverified NSE HTTP 200 payload is still original research
        # evidence. Preserve its exact bytes in a segregated quarantine for
        # independent inspection, never as a validated financial statement.
        sha = hashlib.sha256(raw).hexdigest()
        quarantined = None
        if 0 < len(raw) <= 2_000_000:
            target = (
                root / "research/hg009/p008-originals/quarantine"
                / symbol / f"{sha}.html.gz"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            compressed = gzip.compress(raw, compresslevel=9, mtime=0)
            if target.exists() and target.read_bytes() != compressed:
                raise AlphaContractError("P008 quarantined original byte collision")
            target.write_bytes(compressed)
            quarantined = str(target.relative_to(root))
        return {
            "symbol": symbol,
            "source_url": facts["original_url"],
            "captured_at_utc": captured,
            "state": "BLOCKED_ORIGINAL_NSE_IDENTITY_OR_CASH_ROW",
            "http_status": 200,
            "error_class": type(exc).__name__,
            "blocked_reason": str(exc)[:256],
            "raw_sha256": sha,
            "raw_byte_count": len(raw),
            "original_raw_repo_path": None,
            "quarantined_source_path_not_validated": quarantined,
            "financial_fields_cleared_for_valuation": False,
            "live_capital_allowed": False,
        }
    sha = parsed["raw_sha256"]
    path = root / "research/hg009/p008-originals" / symbol / f"{sha}.html.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    if path.exists() and path.read_bytes() != compressed:
        raise AlphaContractError("P008 content-addressed original file collision")
    path.write_bytes(compressed)
    result = {
        **parsed,
        "source_url": facts["original_url"],
        "state": "ORIGINAL_RAW_ARCHIVED_WITH_VERIFIED_ROWS",
        "original_raw_repo_path": str(path.relative_to(root)),
        "http_status": 200,
    }
    result["receipt_sha256"] = digest(result)
    return result
