import csv
import io
import math
import zipfile
from datetime import date

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_futures import (
    FuturesContractObservation,
    augment_feature_panel_with_futures,
    futures_features,
    parse_fo_udiff_stock_futures,
)
from marketlab.alpha_market import DailyEquityObservation


def _row(
    *,
    day="2026-09-25",
    symbol="TEST",
    instrument_id="1",
    expiry="2026-09-29",
    instrument_type="STF",
    settlement="101",
    previous="100",
    open_interest="10000",
    change_oi="1000",
    volume="100",
    turnover="1010000",
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
        "SttlmPric": settlement,
        "PrvsClsgPric": previous,
        "UndrlygPric": "100",
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


def _cash(day="2026-09-25", *, symbol="TEST", isin="INE000000001"):
    return DailyEquityObservation(
        session_date=day,
        symbol=symbol,
        isin=isin,
        open_price=99.0,
        high_price=102.0,
        low_price=98.0,
        close_price=100.0,
        previous_close=99.0,
        volume=100_000.0,
        turnover_inr=10_000_000.0,
        trade_count=1_000.0,
    )


def test_fo_parser_keeps_stf_and_removes_only_malformed_symbol():
    rows = [
        _row(symbol="GOOD", instrument_id="1"),
        _row(
            symbol="BAD",
            instrument_id="2",
            lot="0",
        ),
        _row(
            symbol="IGNORED",
            instrument_id="3",
            instrument_type="STO",
        ),
    ]
    parsed, diagnostics = parse_fo_udiff_stock_futures(
        _fo_zip(rows),
        session_date=date(2026, 9, 25),
    )
    assert [row.symbol for row in parsed] == ["GOOD"]
    assert diagnostics["stock_future_row_count"] == 2
    assert diagnostics["invalid_symbols"] == ["BAD"]


def test_futures_features_match_frozen_basis_and_oi_contract():
    contracts = [
        FuturesContractObservation(
            session_date="2026-09-25",
            symbol="TEST",
            financial_instrument_id="1",
            expiry_date="2026-09-29",
            settlement_price=101.0,
            previous_close=100.0,
            underlying_price=100.0,
            open_interest=10_000.0,
            change_in_open_interest=1_000.0,
            traded_contracts=100.0,
            transferred_value_inr=1_010_000.0,
            trade_count=50.0,
            board_lot=100.0,
        ),
        FuturesContractObservation(
            session_date="2026-09-25",
            symbol="TEST",
            financial_instrument_id="2",
            expiry_date="2026-10-27",
            settlement_price=102.0,
            previous_close=101.0,
            underlying_price=100.0,
            open_interest=5_000.0,
            change_in_open_interest=-500.0,
            traded_contracts=50.0,
            transferred_value_inr=510_000.0,
            trade_count=25.0,
            board_lot=100.0,
        ),
        FuturesContractObservation(
            session_date="2026-09-25",
            symbol="TEST",
            financial_instrument_id="3",
            expiry_date="2026-11-24",
            settlement_price=103.0,
            previous_close=102.0,
            underlying_price=100.0,
            open_interest=2_500.0,
            change_in_open_interest=250.0,
            traded_contracts=25.0,
            transferred_value_inr=257_500.0,
            trade_count=12.0,
            board_lot=100.0,
        ),
    ]
    features = futures_features(contracts, market_current=_cash())
    assert features["fut_front_basis"] == pytest.approx(0.01)
    assert features["fut_front_log_basis_per_day"] == pytest.approx(
        math.log(1.01) / 4
    )
    assert features["fut_next_log_basis_per_day"] == pytest.approx(
        math.log(1.02) / 32
    )
    assert features["fut_front_oi_change_fraction"] == pytest.approx(
        1000.0 / 9000.0
    )
    assert features["fut_total_oi_change_fraction"] == pytest.approx(
        750.0 / 16750.0
    )
    assert features["fut_front_oi_share"] == pytest.approx(
        10000.0 / 17500.0
    )
    assert features["fut_total_volume_to_oi"] == pytest.approx(
        17500.0 / 17500.0
    )
    assert features["fut_notional_to_cash_turnover"] == pytest.approx(
        1_777_500.0 / 10_000_000.0
    )
    assert features["fut_front_settlement_return_1"] == pytest.approx(0.01)


def test_expiring_today_contract_is_excluded_from_front_and_totals():
    contracts = [
        FuturesContractObservation(
            session_date="2026-09-25",
            symbol="TEST",
            financial_instrument_id="0",
            expiry_date="2026-09-25",
            settlement_price=100.0,
            previous_close=100.0,
            underlying_price=100.0,
            open_interest=1_000_000.0,
            change_in_open_interest=900_000.0,
            traded_contracts=10_000.0,
            transferred_value_inr=100_000_000.0,
            trade_count=1000.0,
            board_lot=100.0,
        ),
        FuturesContractObservation(
            session_date="2026-09-25",
            symbol="TEST",
            financial_instrument_id="1",
            expiry_date="2026-10-27",
            settlement_price=101.0,
            previous_close=100.0,
            underlying_price=100.0,
            open_interest=10_000.0,
            change_in_open_interest=1_000.0,
            traded_contracts=100.0,
            transferred_value_inr=1_010_000.0,
            trade_count=50.0,
            board_lot=100.0,
        ),
        FuturesContractObservation(
            session_date="2026-09-25",
            symbol="TEST",
            financial_instrument_id="2",
            expiry_date="2026-11-24",
            settlement_price=102.0,
            previous_close=101.0,
            underlying_price=100.0,
            open_interest=5_000.0,
            change_in_open_interest=0.0,
            traded_contracts=50.0,
            transferred_value_inr=510_000.0,
            trade_count=25.0,
            board_lot=100.0,
        ),
    ]
    features = futures_features(contracts, market_current=_cash())
    assert features["fut_front_basis"] == pytest.approx(0.01)
    assert features["fut_front_oi_share"] == pytest.approx(
        10_000.0 / 15_000.0
    )
    assert features["fut_notional_to_cash_turnover"] == pytest.approx(
        1_520_000.0 / 10_000_000.0
    )


def test_duplicate_future_expiry_fails_closed_for_symbol():
    contracts = [
        FuturesContractObservation(
            session_date="2026-09-25",
            symbol="TEST",
            financial_instrument_id=str(index),
            expiry_date=expiry,
            settlement_price=101.0,
            previous_close=100.0,
            underlying_price=100.0,
            open_interest=10_000.0,
            change_in_open_interest=0.0,
            traded_contracts=10.0,
            transferred_value_inr=100_000.0,
            trade_count=10.0,
            board_lot=100.0,
        )
        for index, expiry in enumerate(
            ["2026-10-27", "2026-10-27", "2026-11-24"]
        )
    ]
    with pytest.raises(AlphaContractError, match="ambiguous"):
        futures_features(contracts, market_current=_cash())


def test_futures_augmentation_rebinds_symbol_to_same_session_cash_isin():
    day = "2026-09-25"
    market = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET",
        "sessions": [
            {
                "session_date": day,
                "equities": [_cash().__dict__],
            }
        ],
        "live_capital_allowed": False,
    }
    market["panel_sha256"] = digest(market)

    futures = {
        "schema_version": 1,
        "panel_id": "AE001-HISTORICAL-STOCK-FUTURES-v1",
        "sessions": [
            {
                "session_date": day,
                "status": "READY",
                "raw_sha256": "f" * 64,
                "rows": [
                    {
                        "session_date": day,
                        "symbol": "TEST",
                        "financial_instrument_id": "1",
                        "expiry_date": "2026-10-27",
                        "settlement_price": 101.0,
                        "previous_close": 100.0,
                        "underlying_price": 100.0,
                        "open_interest": 10_000.0,
                        "change_in_open_interest": 1_000.0,
                        "traded_contracts": 100.0,
                        "transferred_value_inr": 1_010_000.0,
                        "trade_count": 50.0,
                        "board_lot": 100.0,
                    },
                    {
                        "session_date": day,
                        "symbol": "TEST",
                        "financial_instrument_id": "2",
                        "expiry_date": "2026-11-24",
                        "settlement_price": 102.0,
                        "previous_close": 101.0,
                        "underlying_price": 100.0,
                        "open_interest": 5_000.0,
                        "change_in_open_interest": 0.0,
                        "traded_contracts": 50.0,
                        "transferred_value_inr": 510_000.0,
                        "trade_count": 25.0,
                        "board_lot": 100.0,
                    },
                ],
            }
        ],
        "live_capital_allowed": False,
    }
    futures["panel_sha256"] = digest(futures)

    base = {
        "schema_version": 1,
        "panel_id": "BASE",
        "feature_definitions": [
            {
                "name": "base_feature",
                "family": "price_trend",
                "version": "v1",
                "description": "base",
                "lookback_sessions": 1,
                "availability_lag_sessions": 0,
            }
        ],
        "rows": [
            {
                "feature_session": day,
                "symbol": "TEST",
                "isin": "INE000000001",
                "values": {"base_feature": 0.5},
            }
        ],
        "sessions": [],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    base["panel_sha256"] = digest(base)

    augmented = augment_feature_panel_with_futures(
        feature_panel=base,
        market_panel=market,
        futures_panel=futures,
    )
    assert augmented["feature_row_count"] == 1
    row = augmented["rows"][0]
    assert row["isin"] == "INE000000001"
    assert len(row["values"]) == 11
    assert row["values"]["fut_front_basis"] == pytest.approx(0.01)
