import csv
import io
import zipfile
from datetime import date

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_options_source import (
    classify_front_option_surface,
    parse_fo_udiff_stock_options,
)


def _row(
    *,
    day="2026-09-25",
    symbol="TEST",
    instrument_id="1",
    expiry="2026-10-27",
    strike="100",
    option_type="CE",
    instrument_type="STO",
    settlement="5",
    previous="4",
    underlying="100",
    open_interest="10000",
    change_oi="1000",
    volume="100",
    turnover="500000",
    trades="50",
    lot="100",
):
    return {
        "TradDt": day,
        "Sgmt": "FO",
        "Src": "NSE",
        "FinInstrmTp": instrument_type,
        "FinInstrmId": instrument_id,
        "TckrSymb": symbol,
        "XpryDt": expiry,
        "FininstrmActlXpryDt": expiry,
        "StrkPric": strike,
        "OptnTp": option_type,
        "SttlmPric": settlement,
        "PrvsClsgPric": previous,
        "UndrlygPric": underlying,
        "OpnIntrst": open_interest,
        "ChngInOpnIntrst": change_oi,
        "TtlTradgVol": volume,
        "TtlTrfVal": turnover,
        "TtlNbOfTxsExctd": trades,
        "NewBrdLotQty": lot,
    }


def _fo_zip(rows):
    fields = list(_row().keys())
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr(
            "BhavCopy_NSE_FO_0_0_0_20260925_F_0000.csv",
            text.getvalue(),
        )
    return raw.getvalue()


def _cash(day="2026-09-25"):
    return DailyEquityObservation(
        session_date=day,
        symbol="TEST",
        isin="INE000000001",
        open_price=99.0,
        high_price=102.0,
        low_price=98.0,
        close_price=100.0,
        previous_close=99.0,
        volume=100_000.0,
        turnover_inr=10_000_000.0,
        trade_count=1_000.0,
    )


def test_d005_parser_keeps_stock_options_only():
    rows = [
        _row(instrument_id="1", option_type="CE"),
        _row(instrument_id="2", option_type="PE"),
        _row(
            instrument_id="3",
            instrument_type="STF",
            option_type="",
            strike="",
        ),
    ]
    parsed, diagnostics = parse_fo_udiff_stock_options(
        _fo_zip(rows),
        session_date=date(2026, 9, 25),
    )
    assert len(parsed) == 2
    assert {row.option_type for row in parsed} == {"CE", "PE"}
    assert diagnostics["stock_option_row_count"] == 2


def test_d005_parser_fails_symbol_on_duplicate_logical_option():
    rows = [
        _row(instrument_id="1", option_type="CE"),
        _row(instrument_id="2", option_type="CE"),
        _row(instrument_id="3", option_type="PE"),
    ]
    parsed, diagnostics = parse_fo_udiff_stock_options(
        _fo_zip(rows),
        session_date=date(2026, 9, 25),
    )
    assert parsed == []
    assert diagnostics["invalid_symbols"] == ["TEST"]


def test_d005_surface_requires_three_paired_strikes_and_near_atm_pair():
    rows = []
    for strike in (90.0, 100.0, 110.0):
        for option_type in ("CE", "PE"):
            rows.append(
                _row(
                    instrument_id=f"{int(strike)}-{option_type}",
                    strike=str(strike),
                    option_type=option_type,
                )
            )
    parsed, _ = parse_fo_udiff_stock_options(
        _fo_zip(rows),
        session_date=date(2026, 9, 25),
    )
    surface = classify_front_option_surface(
        parsed,
        market_current=_cash(),
    )
    assert surface["status"] == "USABLE"
    assert surface["paired_strike_count"] == 3
    assert surface["nearest_paired_strike"] == pytest.approx(100.0)
    assert surface["nearest_abs_moneyness"] == pytest.approx(0.0)


def test_d005_surface_rejects_too_few_paired_strikes():
    rows = []
    for strike in (90.0, 100.0):
        for option_type in ("CE", "PE"):
            rows.append(
                _row(
                    instrument_id=f"{int(strike)}-{option_type}",
                    strike=str(strike),
                    option_type=option_type,
                )
            )
    parsed, _ = parse_fo_udiff_stock_options(
        _fo_zip(rows),
        session_date=date(2026, 9, 25),
    )
    surface = classify_front_option_surface(
        parsed,
        market_current=_cash(),
    )
    assert surface["status"] == "INSUFFICIENT_PAIRED_STRIKES"


def test_d005_surface_rejects_paired_strikes_far_from_cash():
    rows = []
    for strike in (130.0, 140.0, 150.0):
        for option_type in ("CE", "PE"):
            rows.append(
                _row(
                    instrument_id=f"{int(strike)}-{option_type}",
                    strike=str(strike),
                    option_type=option_type,
                )
            )
    parsed, _ = parse_fo_udiff_stock_options(
        _fo_zip(rows),
        session_date=date(2026, 9, 25),
    )
    surface = classify_front_option_surface(
        parsed,
        market_current=_cash(),
    )
    assert surface["status"] == "NO_NEAR_ATM_PAIRED_STRIKE"


def test_d005_parser_rejects_structural_trade_date_change():
    with pytest.raises(AlphaContractError, match="trade-date/segment/source"):
        parse_fo_udiff_stock_options(
            _fo_zip([_row(day="2026-09-24")]),
            session_date=date(2026, 9, 25),
        )
