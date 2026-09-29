from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.po001_i003 import _execution_inputs


def _market_sessions():
    start = date(2026, 8, 12)
    sessions = []
    for index in range(20):
        day = (start + timedelta(days=index)).isoformat()
        sessions.append(
            {
                "session_date": day,
                "equities": [
                    {
                        "session_date": day,
                        "symbol": "TEST",
                        "isin": "INE000000001",
                        "open_price": 100.0,
                        "high_price": 102.0,
                        "low_price": 99.0,
                        "close_price": 101.0,
                        "previous_close": 100.0,
                        "volume": 1000.0,
                        "turnover_inr": float(10_000_000 + index * 1_000_000),
                        "trade_count": 100.0,
                    }
                ],
            }
        )
    return sessions


def _feature_panel():
    return {
        "rows": [
            {
                "feature_session": "2026-08-31",
                "symbol": "TEST",
                "isin": "INE000000001",
                "values": {
                    "realized_vol_20": 0.025,
                },
            }
        ]
    }


def test_i003_execution_inputs_use_exact_identity_and_trailing_20_median():
    result = _execution_inputs(
        market_panel={"sessions": _market_sessions()},
        delivery_feature_panel=_feature_panel(),
        identities=[("TEST", "INE000000001")],
    )
    row = result[("TEST", "INE000000001")]
    assert row["adv20_inr"] == pytest.approx(19_500_000.0)
    assert row["daily_volatility_decimal"] == pytest.approx(0.025)


def test_i003_execution_inputs_fail_on_identity_gap():
    sessions = _market_sessions()
    sessions[10]["equities"] = []
    with pytest.raises(AlphaContractError, match="20 contiguous turnover"):
        _execution_inputs(
            market_panel={"sessions": sessions},
            delivery_feature_panel=_feature_panel(),
            identities=[("TEST", "INE000000001")],
        )
