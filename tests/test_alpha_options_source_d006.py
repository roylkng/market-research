import csv
import io
import zipfile
from datetime import date

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_options_source import classify_front_option_surface
from marketlab.alpha_options_source_d006 import (
    parse_fo_udiff_stock_options_d006,
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


def _cash():
    return DailyEquityObservation(
        session_date="2026-09-25",
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


def _paired_rows(strikes):
    rows = []
    counter = 1
    for strike in strikes:
        for option_type in ("CE", "PE"):
            rows.append(
                _row(
                    instrument_id=str(counter),
                    strike=str(strike),
                    option_type=option_type,
                )
            )
            counter += 1
    return rows


def test_d006_malformed_row_does_not_invalidate_valid_sibling_contracts():
    rows = _paired_rows((90, 100, 110))
    rows.append(
        _row(
            instrument_id="bad",
            strike="120",
            option_type="CE",
            settlement="0",
        )
    )
    parsed, diagnostics = parse_fo_udiff_stock_options_d006(
        _fo_zip(rows),
        session_date=date(2026, 9, 25),
    )
    assert len(parsed) == 6
    assert diagnostics.row_exclusion_counts == {
        "INVALID_SETTLEMENT_PRICE": 1
    }
    assert diagnostics.accepted_symbol_count == 1
    surface = classify_front_option_surface(
        parsed,
        market_current=_cash(),
    )
    assert surface["status"] == "USABLE"
    assert surface["paired_strike_count"] == 3


def test_d006_duplicate_logical_contract_drops_key_not_symbol():
    rows = _paired_rows((80, 90, 100, 110))
    # Duplicate the 80 CE logical option under a second instrument ID.
    rows.append(
        _row(
            instrument_id="999",
            strike="80",
            option_type="CE",
        )
    )
    parsed, diagnostics = parse_fo_udiff_stock_options_d006(
        _fo_zip(rows),
        session_date=date(2026, 9, 25),
    )
    assert diagnostics.ambiguous_logical_contract_count == 1
    assert diagnostics.ambiguous_logical_contract_symbols == 1
    assert diagnostics.row_exclusion_counts[
        "AMBIGUOUS_LOGICAL_CONTRACT"
    ] == 2
    # 80 CE pair is lost, but 90/100/110 remain paired.
    surface = classify_front_option_surface(
        parsed,
        market_current=_cash(),
    )
    assert surface["status"] == "USABLE"
    assert surface["paired_strike_count"] == 3


def test_d006_invalid_row_reasons_are_localized():
    rows = _paired_rows((90, 100, 110))
    rows.extend(
        [
            _row(
                instrument_id="bad-expiry",
                strike="120",
                option_type="CE",
                expiry="bad-date",
            ),
            _row(
                instrument_id="bad-lot",
                strike="130",
                option_type="PE",
                lot="0",
            ),
            _row(
                instrument_id="bad-type",
                strike="140",
                option_type="XX",
            ),
        ]
    )
    parsed, diagnostics = parse_fo_udiff_stock_options_d006(
        _fo_zip(rows),
        session_date=date(2026, 9, 25),
    )
    assert len(parsed) == 6
    assert diagnostics.row_exclusion_counts["INVALID_EXPIRY"] == 1
    assert diagnostics.row_exclusion_counts["INVALID_BOARD_LOT"] == 1
    assert diagnostics.row_exclusion_counts["INVALID_OPTION_TYPE"] == 1
    assert classify_front_option_surface(
        parsed,
        market_current=_cash(),
    )["status"] == "USABLE"


def test_d006_still_rejects_structural_session_contract_change():
    with pytest.raises(AlphaContractError, match="trade-date/segment/source"):
        parse_fo_udiff_stock_options_d006(
            _fo_zip([_row(day="2026-09-24")]),
            session_date=date(2026, 9, 25),
        )
