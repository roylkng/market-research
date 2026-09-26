import csv
import io
import zipfile
from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_market import (
    DailyEquityObservation,
    build_dynamic_universe,
    build_price_volume_features,
    parse_udiff_eq_panel,
)


def _history(symbol="TEST", isin="INE000000001", sessions=61, turnover=30_000_000.0):
    start = date(2026, 6, 1)
    rows = []
    close = 100.0
    for index in range(sessions):
        day = start + timedelta(days=index)
        previous = close
        close = previous * (1.0 + 0.001 * ((index % 5) - 1))
        open_price = previous * 1.001
        high = max(open_price, close) * 1.01
        low = min(open_price, close) * 0.99
        rows.append(
            DailyEquityObservation(
                session_date=day.isoformat(),
                symbol=symbol,
                isin=isin,
                open_price=open_price,
                high_price=high,
                low_price=low,
                close_price=close,
                previous_close=previous,
                volume=100_000.0 + index,
                turnover_inr=turnover + index * 10_000,
                trade_count=1_000.0 + index,
            )
        )
    return rows


def test_dynamic_universe_requires_60_prior_sessions_and_liquidity():
    rows = _history()
    current = rows[-1].session_date
    assert build_dynamic_universe(rows, current_session=current) == [
        ("TEST", "INE000000001")
    ]

    illiquid = _history(turnover=10_000_000.0)
    assert build_dynamic_universe(
        illiquid, current_session=illiquid[-1].session_date
    ) == []


def test_price_volume_features_build_first_baseline_pack():
    rows = _history()
    features = build_price_volume_features(
        rows,
        symbol="TEST",
        isin="INE000000001",
        current_session=rows[-1].session_date,
    )
    assert set(features) == {
        "momentum_1",
        "momentum_3",
        "momentum_5",
        "momentum_10",
        "momentum_20",
        "momentum_60",
        "realized_vol_20",
        "realized_vol_60",
        "distance_from_high_20",
        "distance_from_high_60",
        "overnight_gap",
        "open_to_close",
        "intraday_range",
        "turnover_inr",
        "turnover_surprise_20",
        "volume_surprise_20",
        "trade_count_surprise_20",
        "amihud_20_scaled",
    }
    assert features["turnover_surprise_20"] is not None
    assert features["realized_vol_20"] >= 0


def test_price_volume_features_fail_closed_on_insufficient_history():
    rows = _history(sessions=60)
    with pytest.raises(AlphaContractError, match="fewer than 60 prior sessions"):
        build_price_volume_features(
            rows,
            symbol="TEST",
            isin="INE000000001",
            current_session=rows[-1].session_date,
        )


def _udiff_zip(rows):
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
    writer.writerows(rows)
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("bhav.csv", text.getvalue())
    return raw.getvalue()


def test_parse_udiff_eq_panel_keeps_only_nse_cm_stock_eq_rows():
    day = "2026-09-25"
    base = {
        "TradDt": day,
        "Sgmt": "CM",
        "Src": "NSE",
        "FinInstrmTp": "STK",
        "ISIN": "INE000000001",
        "TckrSymb": "TEST",
        "SctySrs": "EQ",
        "OpnPric": "100",
        "HghPric": "110",
        "LwPric": "95",
        "ClsPric": "105",
        "PrvsClsgPric": "99",
        "TtlTradgVol": "1000",
        "TtlTrfVal": "103000",
        "TtlNbOfTxsExctd": "75",
    }
    excluded = dict(base, TckrSymb="NOT_EQ", ISIN="IN0000000002", SctySrs="BE")
    parsed = parse_udiff_eq_panel(
        _udiff_zip([base, excluded]),
        session_date=date(2026, 9, 25),
    )
    assert len(parsed) == 1
    assert parsed[0].symbol == "TEST"
    assert parsed[0].trade_count == 75


def test_parse_udiff_eq_panel_rejects_impossible_ohlc():
    row = {
        "TradDt": "2026-09-25",
        "Sgmt": "CM",
        "Src": "NSE",
        "FinInstrmTp": "STK",
        "ISIN": "INE000000001",
        "TckrSymb": "TEST",
        "SctySrs": "EQ",
        "OpnPric": "120",
        "HghPric": "110",
        "LwPric": "95",
        "ClsPric": "105",
        "PrvsClsgPric": "99",
        "TtlTradgVol": "1000",
        "TtlTrfVal": "103000",
        "TtlNbOfTxsExctd": "75",
    }
    with pytest.raises(AlphaContractError, match="invalid OHLC"):
        parse_udiff_eq_panel(
            _udiff_zip([row]),
            session_date=date(2026, 9, 25),
        )
