from __future__ import annotations

from datetime import date

from marketlab.h022_marketdata import parse_h022_nifty500_benchmark


def test_h022_benchmark_adapter_exposes_open_and_close() -> None:
    raw = (
        b"Index Name,Index Date,Open Index Value,Closing Index Value\n"
        b"Nifty 50,01-10-2025,25000,25100\n"
        b"Nifty 500,01-10-2025,22000,22150\n"
    )
    bar = parse_h022_nifty500_benchmark(raw, session_date=date(2025, 10, 1))

    assert bar["benchmark_id"] == "nifty_500"
    assert bar["session_date"] == "2025-10-01"
    assert bar["open"] == 22000.0
    assert bar["close"] == 22150.0
    assert "open_price" not in bar
    assert "close_price" not in bar
