"""Evaluate the H020 timing diagnostic on *supplied*, point-in-time CSV sources.

No automatic Yahoo lookup, future-data acquisition, trades, target prices,
portfolio entitlement or return outcomes. Adjusted price series must be
independently verified before interpreting the historical signal.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import date
from pathlib import Path

import pandas as pd

from marketlab.timing import compute_snapshot


def _load_csv(path: Path) -> tuple[pd.DataFrame, str]:
    raw = path.read_bytes()
    if not raw:
        raise ValueError(f"empty historical price source: {path}")
    frame = pd.read_csv(io.BytesIO(raw))
    if not {"date", "adj_close", "volume"}.issubset(frame.columns):
        raise ValueError(f"CSV requires date,adj_close,volume: {path}")
    if frame["date"].isna().any():
        raise ValueError("CSV contains missing observation date")
    normalized = []
    for value in frame["date"]:
        parsed = date.fromisoformat(str(value))
        if parsed.isoformat() != str(value):
            raise ValueError("CSV date must use ISO YYYY-MM-DD")
        normalized.append(parsed.isoformat())
    frame["date"] = pd.to_datetime(normalized, utc=True)
    frame = frame.set_index("date")
    return frame, hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-csv", required=True, type=Path)
    parser.add_argument("--benchmark-csv", required=True, type=Path)
    parser.add_argument("--as-of-session", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    stock, stock_sha = _load_csv(args.stock_csv)
    benchmark, benchmark_sha = _load_csv(args.benchmark_csv)
    snapshot = compute_snapshot(
        stock, benchmark,
        symbol=args.symbol,
        as_of_session=args.as_of_session,
    )
    record = {
        "schema_version": 1,
        "id": "H020-TIMING-READONLY-v1",
        "classification": "UNVALIDATED_TIMING_RESEARCH_NOT_PORTFOLIO",
        "as_of_session": args.as_of_session,
        "stock_source_sha256": stock_sha,
        "benchmark_source_sha256": benchmark_sha,
        "adjusted_price_and_corporate_actions_independently_verified": False,
        "source_observed_before_decision_proven": False,
        "result": snapshot,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
