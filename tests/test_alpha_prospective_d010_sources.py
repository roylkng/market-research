from __future__ import annotations

import csv
import io
import zipfile

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_prospective_d010_sources import (
    append_sc004_source_probe,
    new_sc004_source_ledger,
    session_already_eligible,
    validate_sc004_source_ledger,
)


def _udiff(day: str, *, symbol: str = "TEST", isin: str = "INE000000001") -> bytes:
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
            "ISIN": isin,
            "TckrSymb": symbol,
            "SctySrs": "EQ",
            "OpnPric": "100",
            "HghPric": "103",
            "LwPric": "99",
            "ClsPric": "102",
            "PrvsClsgPric": "100",
            "TtlTradgVol": "100000",
            "TtlTrfVal": "30000000",
            "TtlNbOfTxsExctd": "1000",
        }
    )
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("bhav.csv", text.getvalue())
    return raw.getvalue()


def _short(trade_date: str, *, symbol: str = "TEST") -> bytes:
    return (
        "Security Name,Symbol Name,Trade Date,Quantity\n"
        f"Example,{symbol},{trade_date},1000\n"
    ).encode()


def _slb(*, symbol: str = "TEST", series: str = "X1") -> bytes:
    return (
        "Sr no,Security,Series,Outstanding Quantity at the end of the day\n"
        f"1,{symbol},{series},2500\n"
    ).encode()


def _eligible_probe(*, captured="2026-10-02T12:50:00+00:00"):
    return append_sc004_source_probe(
        new_sc004_source_ledger(),
        publication_session="2026-10-02",
        previous_completed_session="2026-10-01",
        captured_at_utc=captured,
        current_market_source_url="https://nse/current.zip",
        current_market_raw=_udiff("2026-10-02"),
        previous_market_source_url="https://nse/previous.zip",
        previous_market_raw=_udiff("2026-10-01"),
        short_source_url="https://nse/short.csv",
        short_raw=_short("01-Oct-2026"),
        slb_source_url="https://nse/slb.csv",
        slb_raw=_slb(),
    )


def test_sc004_valid_identity_complete_sources_are_eligible_before_cutoff():
    ledger, attempt = _eligible_probe()
    assert attempt is not None
    assert attempt["eligible_before_cutoff"] is True
    assert attempt["short_selling"]["identity_mapping_fraction"] == pytest.approx(1.0)
    assert attempt["short_selling"][
        "publication_isin_continuity_fraction"
    ] == pytest.approx(1.0)
    assert attempt["slb_open_positions"]["identity_mapping_fraction"] == pytest.approx(
        1.0
    )
    assert session_already_eligible(ledger, "2026-10-02") is True
    validate_sc004_source_ledger(ledger)


def test_sc004_late_capture_is_recorded_but_never_eligible():
    ledger, attempt = _eligible_probe(captured="2026-10-02T13:00:01+00:00")
    assert attempt is not None
    assert attempt["captured_before_or_at_cutoff"] is False
    assert attempt["eligible_before_cutoff"] is False
    assert session_already_eligible(ledger, "2026-10-02") is False


def test_sc004_short_identity_continuity_failure_is_ineligible():
    ledger, attempt = append_sc004_source_probe(
        new_sc004_source_ledger(),
        publication_session="2026-10-02",
        previous_completed_session="2026-10-01",
        captured_at_utc="2026-10-02T12:30:00+00:00",
        current_market_source_url="current",
        current_market_raw=_udiff(
            "2026-10-02",
            symbol="NEW",
            isin="INE999999999",
        ),
        previous_market_source_url="previous",
        previous_market_raw=_udiff("2026-10-01"),
        short_source_url="short",
        short_raw=_short("01-Oct-2026"),
        slb_source_url="slb",
        slb_raw=_slb(symbol="NEW"),
    )
    assert attempt is not None
    assert attempt["short_selling"]["status"] == "IDENTITY_GATE_FAILED"
    assert attempt["short_selling"][
        "publication_isin_continuity_fraction"
    ] == pytest.approx(0.0)
    assert attempt["eligible_before_cutoff"] is False
    validate_sc004_source_ledger(ledger)


def test_sc004_slb_mapping_failure_is_ineligible():
    _, attempt = append_sc004_source_probe(
        new_sc004_source_ledger(),
        publication_session="2026-10-02",
        previous_completed_session="2026-10-01",
        captured_at_utc="2026-10-02T12:30:00+00:00",
        current_market_source_url="current",
        current_market_raw=_udiff("2026-10-02"),
        previous_market_source_url="previous",
        previous_market_raw=_udiff("2026-10-01"),
        short_source_url="short",
        short_raw=_short("01-Oct-2026"),
        slb_source_url="slb",
        slb_raw=_slb(symbol="UNMAPPED"),
    )
    assert attempt is not None
    assert attempt["slb_open_positions"]["status"] == "IDENTITY_GATE_FAILED"
    assert attempt["slb_open_positions"]["identity_mapping_fraction"] == pytest.approx(
        0.0
    )
    assert attempt["eligible_before_cutoff"] is False


def test_sc004_parser_valid_empty_reports_are_source_valid():
    empty_short = b"Security Name,Symbol Name,Trade Date,Quantity\n"
    empty_slb = (
        b"Sr no,Security,Series,Outstanding Quantity at the end of the day\n"
    )
    _, attempt = append_sc004_source_probe(
        new_sc004_source_ledger(),
        publication_session="2026-10-02",
        previous_completed_session="2026-10-01",
        captured_at_utc="2026-10-02T12:30:00+00:00",
        current_market_source_url="current",
        current_market_raw=_udiff("2026-10-02"),
        previous_market_source_url="previous",
        previous_market_raw=_udiff("2026-10-01"),
        short_source_url="short",
        short_raw=empty_short,
        slb_source_url="slb",
        slb_raw=empty_slb,
    )
    assert attempt is not None
    assert attempt["short_selling"]["status"] == "READY"
    assert attempt["slb_open_positions"]["status"] == "READY"
    assert attempt["eligible_before_cutoff"] is True


def test_sc004_success_makes_later_probe_idempotent():
    ledger, _ = _eligible_probe()
    updated, attempt = append_sc004_source_probe(
        ledger,
        publication_session="2026-10-02",
        previous_completed_session=None,
        captured_at_utc="2026-10-02T12:55:00+00:00",
        current_market_source_url="current",
        current_market_raw=None,
        previous_market_source_url=None,
        previous_market_raw=None,
        short_source_url="short",
        short_raw=None,
        slb_source_url="slb",
        slb_raw=None,
    )
    assert attempt is None
    assert updated == ledger


def test_sc004_rejects_pre_start_and_invalid_previous_session():
    with pytest.raises(AlphaContractError, match="start boundary"):
        append_sc004_source_probe(
            new_sc004_source_ledger(),
            publication_session="2026-10-01",
            previous_completed_session="2026-09-30",
            captured_at_utc="2026-10-01T12:00:00+00:00",
            current_market_source_url="x",
            current_market_raw=None,
            previous_market_source_url="y",
            previous_market_raw=None,
            short_source_url="s",
            short_raw=None,
            slb_source_url="l",
            slb_raw=None,
        )

    with pytest.raises(AlphaContractError, match="lookback"):
        append_sc004_source_probe(
            new_sc004_source_ledger(),
            publication_session="2026-10-10",
            previous_completed_session="2026-10-01",
            captured_at_utc="2026-10-10T12:00:00+00:00",
            current_market_source_url="x",
            current_market_raw=None,
            previous_market_source_url="y",
            previous_market_raw=None,
            short_source_url="s",
            short_raw=None,
            slb_source_url="l",
            slb_raw=None,
        )
