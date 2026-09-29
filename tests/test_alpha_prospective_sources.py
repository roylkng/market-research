from datetime import date

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_prospective_sources import (
    append_source_probe,
    new_source_ledger,
    session_already_eligible,
    validate_source_ledger,
)


def _udiff(day: str) -> bytes:
    import csv
    import io
    import zipfile

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
            "TradDt": day,
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


def _delivery(day: str, *, pct="40.00") -> bytes:
    import csv
    import io

    fields = [
        "SYMBOL",
        "SERIES",
        "DATE1",
        "AVG_PRICE",
        "TTL_TRD_QNTY",
        "TURNOVER_LACS",
        "NO_OF_TRADES",
        "DELIV_QTY",
        "DELIV_PER",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            "SYMBOL": "TEST",
            "SERIES": "EQ",
            "DATE1": day,
            "AVG_PRICE": "101",
            "TTL_TRD_QNTY": "1000",
            "TURNOVER_LACS": "1.01",
            "NO_OF_TRADES": "100",
            "DELIV_QTY": "400",
            "DELIV_PER": pct,
        }
    )
    return text.getvalue().encode()


def test_sc001_before_cutoff_valid_sources_are_eligible():
    ledger, attempt = append_source_probe(
        new_source_ledger(),
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T12:40:00+00:00",
        market_source_url="https://nsearchives.nseindia.com/market.zip",
        market_raw=_udiff("2026-09-30"),
        delivery_source_url="https://nsearchives.nseindia.com/delivery.csv",
        delivery_raw=_delivery("30-Sep-2026"),
    )
    assert attempt is not None
    assert attempt["eligible_before_cutoff"] is True
    assert session_already_eligible(ledger, "2026-09-30") is True
    validate_source_ledger(ledger)


def test_sc001_after_cutoff_never_becomes_eligible():
    ledger, attempt = append_source_probe(
        new_source_ledger(),
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T13:01:00+00:00",
        market_source_url="https://nsearchives.nseindia.com/market.zip",
        market_raw=_udiff("2026-09-30"),
        delivery_source_url="https://nsearchives.nseindia.com/delivery.csv",
        delivery_raw=_delivery("30-Sep-2026"),
    )
    assert attempt is not None
    assert attempt["captured_before_or_at_cutoff"] is False
    assert attempt["eligible_before_cutoff"] is False
    assert session_already_eligible(ledger, "2026-09-30") is False


def test_sc001_delivery_quality_failure_is_not_eligible():
    _, attempt = append_source_probe(
        new_source_ledger(),
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T12:40:00+00:00",
        market_source_url="https://nsearchives.nseindia.com/market.zip",
        market_raw=_udiff("2026-09-30"),
        delivery_source_url="https://nsearchives.nseindia.com/delivery.csv",
        delivery_raw=_delivery("30-Sep-2026", pct="60.00"),
    )
    assert attempt is not None
    assert attempt["delivery"]["status"] == "SOURCE_QUALITY_EXCLUDED"
    assert attempt["eligible_before_cutoff"] is False


def test_sc001_success_makes_later_probe_idempotent():
    ledger, _ = append_source_probe(
        new_source_ledger(),
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T12:30:00+00:00",
        market_source_url="m",
        market_raw=_udiff("2026-09-30"),
        delivery_source_url="d",
        delivery_raw=_delivery("30-Sep-2026"),
    )
    second, attempt = append_source_probe(
        ledger,
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T12:45:00+00:00",
        market_source_url="m",
        market_raw=None,
        delivery_source_url="d",
        delivery_raw=None,
    )
    assert attempt is None
    assert second == ledger


def test_sc001_rejects_probe_before_frozen_boundary():
    with pytest.raises(AlphaContractError, match="start boundary"):
        append_source_probe(
            new_source_ledger(),
            session_date=date(2026, 9, 29).isoformat(),
            captured_at_utc="2026-09-29T12:00:00+00:00",
            market_source_url="m",
            market_raw=None,
            delivery_source_url="d",
            delivery_raw=None,
        )
