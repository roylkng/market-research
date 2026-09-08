from __future__ import annotations

import json
from datetime import date

import h018_nifty500_historical_source as source
import pytest


def envelope(rows: list[dict[str, str]]) -> bytes:
    return json.dumps({"d": json.dumps(rows)}).encode()


def test_request_payload_is_frozen_nifty500_shape() -> None:
    payload = source.request_payload(date(2013, 11, 1), date(2017, 5, 31))
    assert payload == {
        "cinfo": (
            "{'name':'NIFTY 500','startDate':'01-Nov-2013','endDate':'31-May-2017',"
            "'indexName':'NIFTY 500'}"
        )
    }


def test_parse_official_history_accepts_both_known_name_fields() -> None:
    raw = envelope(
        [
            {
                "Index Name": "Nifty 500",
                "HistoricalDate": "02 Jan 2014",
                "OPEN": "6,100.25",
                "HIGH": "6,150.00",
                "LOW": "6,080.00",
                "CLOSE": "6,130.50",
            },
            {
                "indexName": "NIFTY 500",
                "HistoricalDate": "03-Jan-2014",
                "OPEN": "6130.50",
                "HIGH": "6160.25",
                "LOW": "6100.00",
                "CLOSE": "6142.75",
            },
        ]
    )
    parsed = source.parse_official_history(
        raw,
        start=date(2014, 1, 1),
        end=date(2014, 1, 31),
    )
    assert sorted(parsed) == [date(2014, 1, 2), date(2014, 1, 3)]
    assert parsed[date(2014, 1, 2)]["open"] == 6100.25
    assert parsed[date(2014, 1, 3)]["close"] == 6142.75


def test_duplicate_history_date_fails_closed() -> None:
    row = {
        "Index Name": "NIFTY 500",
        "HistoricalDate": "02 Jan 2014",
        "OPEN": "6100",
        "HIGH": "6150",
        "LOW": "6080",
        "CLOSE": "6130",
    }
    with pytest.raises(source.H018HistoricalIndexError, match="duplicate"):
        source.parse_official_history(
            envelope([row, row]),
            start=date(2014, 1, 1),
            end=date(2014, 1, 31),
        )


def test_missing_ohlc_fails_closed() -> None:
    with pytest.raises(source.H018HistoricalIndexError, match="missing open"):
        source.parse_official_history(
            envelope(
                [
                    {
                        "Index Name": "NIFTY 500",
                        "HistoricalDate": "02 Jan 2014",
                        "OPEN": "-",
                        "HIGH": "6150",
                        "LOW": "6080",
                        "CLOSE": "6130",
                    }
                ]
            ),
            start=date(2014, 1, 1),
            end=date(2014, 1, 31),
        )
