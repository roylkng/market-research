from __future__ import annotations

import csv
import io
from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_market import DailyEquityObservation
from marketlab.ss001_census import (
    build_full_market_census,
    classify_action_subject,
    parse_equity_security_master,
)


def _master() -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "SYMBOL",
            "NAME OF COMPANY",
            " SERIES",
            " DATE OF LISTING",
            " PAID UP VALUE",
            " MARKET LOT",
            " ISIN NUMBER",
            " FACE VALUE",
        ]
    )
    writer.writerow(
        ["AAA", "AAA LIMITED", "EQ", "01-Jan-2020", "10", "1", "INE000A01001", "10"]
    )
    writer.writerow(
        ["BBB", "BBB LIMITED", "EQ", "02-Feb-2021", "5", "1", "INE000B01001", "5"]
    )
    writer.writerow(
        ["ZZZ", "ZZZ LIMITED", "BE", "03-Mar-2022", "10", "1", "INE000Z01001", "10"]
    )
    return stream.getvalue().encode()


def _observation(symbol: str, isin: str, day: date, close: float) -> DailyEquityObservation:
    return DailyEquityObservation(
        session_date=day.isoformat(),
        symbol=symbol,
        isin=isin,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        previous_close=close,
        volume=1000.0,
        turnover_inr=1_000_000.0,
        trade_count=100.0,
    )


def test_security_master_keeps_only_eq_and_exact_identities() -> None:
    rows = parse_equity_security_master(_master())
    assert [row.symbol for row in rows] == ["AAA", "BBB"]
    assert rows[0].isin == "INE000A01001"
    assert rows[0].listing_date == "2020-01-01"


def test_action_subject_classes_are_deterministic() -> None:
    assert classify_action_subject("Dividend - Rs 5 per share") == "dividend"
    assert classify_action_subject("Bonus 1:1") == "bonus"
    assert classify_action_subject("Sub-division of equity shares") == "split_or_consolidation"
    assert classify_action_subject("Rights issue 1:5") == "rights"
    assert classify_action_subject("Scheme of Arrangement / Demerger") == "scheme_or_reorganisation"
    assert classify_action_subject("Buy Back of Shares") == "buyback"
    assert classify_action_subject("Voluntary Delisting") == "delisting"


def test_full_market_census_joins_market_financial_and_action_context() -> None:
    start = date(2026, 9, 4)
    dates = []
    cursor = start
    while len(dates) < 19:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor += timedelta(days=1)
    dates.append(date(2026, 10, 1))
    dates = sorted(set(dates))
    assert len(dates) == 20

    sessions = []
    for idx, day in enumerate(dates):
        sessions.append(
            {
                "session_date": day.isoformat(),
                "equities": [
                    _observation("AAA", "INE000A01001", day, 100.0 + idx),
                    _observation("BBB", "INE000B01001", day, 200.0 + idx),
                ],
            }
        )

    financial = [
        {
            "data": [
                {
                    "type": "Integrated Filing- Financials",
                    "symbol": "AAA",
                    "qe_Date": "30-Jun-2026",
                    "broadcast_Date": "20-Jul-2026 18:00:00",
                }
            ]
        }
    ]
    actions = [
        [
            {
                "symbol": "AAA",
                "series": "EQ",
                "subject": "Bonus 1:1",
                "exDate": "20-Aug-2026",
            }
        ]
    ]

    result = build_full_market_census(
        security_master_raw=_master(),
        market_sessions=sessions,
        integrated_payloads=financial,
        corporate_action_payloads=actions,
        existing_u001_symbols={"AAA"},
        source_metadata={"all_corporate_action_chunks_acquired": True},
    )

    rows = {row["symbol"]: row for row in result["rows"]}
    assert result["eq_identity_count"] == 2
    assert rows["AAA"]["market"]["observed_session_count"] == 20
    assert rows["AAA"]["financial_source"]["has_integrated_financial_filing"] is True
    assert rows["AAA"]["corporate_actions_1y"]["bonus"] == 1
    assert rows["AAA"]["in_existing_u001"] is True
    assert rows["BBB"]["in_existing_u001"] is False
    assert result["return_outcomes_opened"] is False
    assert result["portfolio_eligibility_allowed"] is False


def test_market_window_must_end_on_frozen_current_session() -> None:
    day = date(2026, 9, 1)
    sessions = [
        {
            "session_date": (day + timedelta(days=i)).isoformat(),
            "equities": [],
        }
        for i in range(20)
    ]
    with pytest.raises(AlphaContractError, match="must end on 2026-10-01"):
        build_full_market_census(
            security_master_raw=_master(),
            market_sessions=sessions,
            integrated_payloads=[],
            corporate_action_payloads=[],
            existing_u001_symbols=set(),
            source_metadata={"all_corporate_action_chunks_acquired": True},
        )
