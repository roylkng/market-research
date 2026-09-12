from __future__ import annotations

import io
import zipfile
from datetime import date

import pytest

from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    PF001MarketDataMissingRow,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)


def _udiff_zip(rows: list[str]) -> bytes:
    header = (
        "TradDt,Sgmt,Src,FinInstrmTp,ISIN,TckrSymb,SctySrs,"
        "OpnPric,HghPric,LwPric,ClsPric\n"
    )
    payload = (header + "\n".join(rows) + "\n").encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BhavCopy_NSE_CM_test.csv", payload)
    return out.getvalue()


def test_parse_pf001_udiff_retains_real_ohlc() -> None:
    raw = _udiff_zip(
        ["2026-09-11,CM,NSE,STK,INE000A01001,AAA,EQ,100,110,95,108"]
    )
    bar = parse_pf001_udiff_equity(
        raw,
        symbol="AAA",
        session_date=date(2026, 9, 11),
        expected_isin="INE000A01001",
    )
    assert bar.open_price == 100.0
    assert bar.high_price == 110.0
    assert bar.low_price == 95.0
    assert bar.close_price == 108.0
    assert bar.fund_bar() == {
        "open": 100.0,
        "high": 110.0,
        "low": 95.0,
        "close": 108.0,
    }
    assert "BhavCopy_NSE_CM_0_0_0_20260911_F_0000.csv.zip" in bar.source_url


def test_udiff_isin_mismatch_fails_closed() -> None:
    raw = _udiff_zip(
        ["2026-09-11,CM,NSE,STK,INE000A01001,AAA,EQ,100,110,95,108"]
    )
    with pytest.raises(PF001MarketDataError, match="ISIN mismatch"):
        parse_pf001_udiff_equity(
            raw,
            symbol="AAA",
            session_date=date(2026, 9, 11),
            expected_isin="INE999A01001",
        )


def test_udiff_inconsistent_ohlc_fails_closed() -> None:
    raw = _udiff_zip(
        ["2026-09-11,CM,NSE,STK,INE000A01001,AAA,EQ,100,105,95,108"]
    )
    with pytest.raises(PF001MarketDataError, match="close falls outside"):
        parse_pf001_udiff_equity(
            raw,
            symbol="AAA",
            session_date=date(2026, 9, 11),
        )


def test_udiff_missing_symbol_is_explicit() -> None:
    raw = _udiff_zip(
        ["2026-09-11,CM,NSE,STK,INE000A01001,AAA,EQ,100,110,95,108"]
    )
    with pytest.raises(PF001MarketDataMissingRow):
        parse_pf001_udiff_equity(
            raw,
            symbol="BBB",
            session_date=date(2026, 9, 11),
        )


def test_parse_official_nifty500_index_open_close() -> None:
    raw = (
        "Index Name,Index Date,Open Index Value,Closing Index Value\n"
        "Nifty 50,11-09-2026,23000,23100\n"
        "Nifty 500,11-09-2026,21000,21150\n"
    ).encode()
    bar = parse_pf001_nifty500_index(raw, session_date=date(2026, 9, 11))
    assert bar.benchmark_id == "nifty_500"
    assert bar.open_price == 21000.0
    assert bar.close_price == 21150.0
    assert bar.attribution_bar() == {"open": 21000.0, "close": 21150.0}
    assert "ind_close_all_11092026.csv" in bar.source_url


def test_nifty500_missing_row_fails_closed() -> None:
    raw = (
        "Index Name,Index Date,Open Index Value,Closing Index Value\n"
        "Nifty 50,11-09-2026,23000,23100\n"
    ).encode()
    with pytest.raises(PF001MarketDataMissingRow):
        parse_pf001_nifty500_index(raw, session_date=date(2026, 9, 11))
