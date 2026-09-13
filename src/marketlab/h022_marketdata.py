from __future__ import annotations

from datetime import date
from typing import Any

from marketlab.marketdata import index_snapshot_url
from marketlab.pf001_marketdata import parse_pf001_nifty500_index


def parse_h022_nifty500_benchmark(raw_csv: bytes, *, session_date: date) -> dict[str, Any]:
    """Convert the official NSE index row to H022's frozen open/close attribution shape."""
    parsed = parse_pf001_nifty500_index(raw_csv, session_date=session_date)
    return {
        "benchmark_id": parsed.benchmark_id,
        "session_date": parsed.session_date,
        **parsed.attribution_bar(),
        "source_url": index_snapshot_url(session_date),
    }
