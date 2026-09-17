"""Broad prior-session NSE identities for company-news discovery.

The deep 100-company panel remains the dossier universe. This module only expands
name-to-symbol resolution using official prior-session NSE EQ identities. Aliases
are deterministic text variants, not investment relationships or beneficiaries.
"""
from __future__ import annotations

import re
from datetime import date

from marketlab.intelligence_market_audit import _read_udiff_rows

ABBREVIATIONS = {
    "ASSU": "ASSURANCE",
    "CORP": "CORPORATION",
    "ENGG": "ENGINEERING",
    "INS": "INSURANCE",
    "TECH": "TECHNOLOGY",
}
LEGAL_SUFFIX = re.compile(r"\b(?:LTD|LIMITED|L)\.?$", re.IGNORECASE)


def _clean(value: str) -> str:
    return " ".join(value.replace(".", " ").split())


def _variants(name: str) -> list[str]:
    base = _clean(LEGAL_SUFFIX.sub("", name).strip())
    tokens = base.split()
    expanded = " ".join(ABBREVIATIONS.get(token.upper(), token) for token in tokens)
    values = {base, expanded}
    candidates = [expanded]
    if expanded.casefold().startswith("the "):
        without_the = expanded[4:].strip()
        values.add(without_the)
        candidates.append(without_the)
    for candidate in candidates:
        lowered = candidate.casefold()
        for suffix in (" insurance company", " assurance company", " corporation", " company"):
            if lowered.endswith(suffix):
                shorter = candidate[: -len(suffix)].strip()
                if len(shorter.split()) >= 2:
                    values.add(shorter)
    return sorted(value for value in values if len(value) >= 5)


def identity_members_from_udiff(
    raw_udiff: bytes,
    *,
    session_date: date,
    deep_members: list[dict],
) -> list[dict]:
    """Return alias rows suitable for the existing exact entity matcher."""
    rows = _read_udiff_rows(raw_udiff, session_date)
    aliases = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not row["isin"].startswith("INE"):
            continue
        for name in _variants(row["security_name"]):
            key = (row["symbol"], name.casefold())
            if key in seen:
                continue
            seen.add(key)
            aliases.append({
                "symbol": row["symbol"],
                "company_name": name,
                "isin": row["isin"],
                "identity_source": "NSE_UDIFF_PRIOR_SESSION",
            })
    for member in deep_members:
        key = (member["symbol"], member["company_name"].casefold())
        if key in seen:
            continue
        seen.add(key)
        aliases.append({
            "symbol": member["symbol"],
            "company_name": member["company_name"],
            "isin": member.get("isin"),
            "identity_source": "DEEP_PANEL_FULL_NAME",
        })
    return sorted(aliases, key=lambda row: (row["symbol"], row["company_name"]))
