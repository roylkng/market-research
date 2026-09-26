import csv
import io
import zipfile
from datetime import UTC, date, datetime

import pytest

from marketlab.alpha_acquisition import (
    AlphaAcquisitionError,
    acquire_historical_market_panel,
)
from marketlab.marketdata import index_snapshot_url, udiff_url


def _udiff(day):
    fields = [
        "TradDt",
        "Sgmt",
        "Src",
        "FinInstrmTp",
        "ISIN",
        "TckrSymb",
        "SctySrs",
        "OpnPric",
        "HghPric",
        "LwPric",
        "ClsPric",
        "PrvsClsgPric",
        "TtlTradgVol",
        "TtlTrfVal",
        "TtlNbOfTxsExctd",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            "TradDt": day.isoformat(),
            "Sgmt": "CM",
            "Src": "NSE",
            "FinInstrmTp": "STK",
            "ISIN": "INE000000001",
            "TckrSymb": "TEST",
            "SctySrs": "EQ",
            "OpnPric": "100",
            "HghPric": "105",
            "LwPric": "99",
            "ClsPric": "102",
            "PrvsClsgPric": "100",
            "TtlTradgVol": "1000",
            "TtlTrfVal": "102000",
            "TtlNbOfTxsExctd": "100",
        }
    )
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("bhav.csv", text.getvalue())
    return raw.getvalue()


def _index(day):
    return (
        "Index Name,Index Date,Open Index Value,Closing Index Value\n"
        f"Nifty 500,{day.strftime('%d-%m-%Y')},22000,22100\n"
    ).encode()


def test_acquisition_probes_all_calendar_days_and_retains_sessions():
    trading_day = date(2026, 2, 1)

    def fetch(url):
        if url == udiff_url(trading_day):
            return _udiff(trading_day)
        if url == index_snapshot_url(trading_day):
            return _index(trading_day)
        return None

    panel = acquire_historical_market_panel(
        start_date=date(2026, 1, 31),
        end_date=date(2026, 2, 2),
        fetcher=fetch,
        captured_at_utc=datetime(2026, 9, 26, tzinfo=UTC),
    )
    assert panel["probed_calendar_day_count"] == 3
    assert panel["session_count"] == 1
    assert panel["sessions"][0]["session_date"] == "2026-02-01"
    assert panel["historical_archives_captured_prospectively"] is False


def test_acquisition_fails_if_session_lacks_benchmark_snapshot():
    day = date(2026, 1, 5)

    def fetch(url):
        if url == udiff_url(day):
            return _udiff(day)
        return None

    with pytest.raises(AlphaAcquisitionError, match="Nifty 500 snapshot"):
        acquire_historical_market_panel(
            start_date=day,
            end_date=day,
            fetcher=fetch,
        )
