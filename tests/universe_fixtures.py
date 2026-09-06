from __future__ import annotations

import csv
import io
from typing import Any


def make_nifty200_sources(entries: list[dict[str, Any]]) -> tuple[dict[str, Any], bytes]:
    """Build matching 200-row Nifty 200 index/constituent fixtures.

    Custom entries are preserved exactly. Remaining rows are deterministic
    Financial Services padding so selection tests exercise the production U001
    exclusion rule without weakening the 200-member source invariant.
    """

    if len(entries) > 200:
        raise ValueError("entries cannot exceed 200")

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        symbol = str(entry["symbol"]).strip().upper()
        if not symbol or symbol in seen:
            raise ValueError(f"invalid or duplicate symbol: {symbol!r}")
        seen.add(symbol)
        normalized.append(
            {
                "symbol": symbol,
                "ffmc": float(entry["ffmc"]),
                "industry": str(entry.get("industry", "Industrials")),
                "isin": str(entry.get("isin", f"INE{len(normalized):09d}")),
                "company_name": str(entry.get("company_name", f"{symbol} Limited")),
                "series": str(entry.get("series", "EQ")),
            }
        )

    pad_index = 0
    while len(normalized) < 200:
        symbol = f"PAD{pad_index:03d}"
        pad_index += 1
        if symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(
            {
                "symbol": symbol,
                "ffmc": max(1.0, 100.0 - pad_index / 10.0),
                "industry": "Financial Services",
                "isin": f"INP{pad_index:09d}",
                "company_name": f"Padding Financial {pad_index} Limited",
                "series": "EQ",
            }
        )

    index_payload = {
        "timestamp": "06-Sep-2026 15:30:00",
        "data": [
            {"symbol": row["symbol"], "ffmc": row["ffmc"]}
            for row in normalized
        ],
    }

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=["Company Name", "Industry", "Symbol", "Series", "ISIN Code"],
    )
    writer.writeheader()
    for row in normalized:
        writer.writerow(
            {
                "Company Name": row["company_name"],
                "Industry": row["industry"],
                "Symbol": row["symbol"],
                "Series": row["series"],
                "ISIN Code": row["isin"],
            }
        )

    return index_payload, buffer.getvalue().encode("utf-8")
