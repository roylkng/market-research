from __future__ import annotations

import io
import zipfile
from datetime import date

import pytest

from marketlab.marketdata import (
    MarketDataError,
    audit_price_basis_actions,
    parse_index_snapshot,
    parse_udiff_equity,
)


def _udiff_zip() -> bytes:
    csv_text = (
        "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,"
        "XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,"
        "LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,"
        "ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,"
        "Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4\n"
        "2026-09-04,2026-09-04,CM,NSE,STK,500325,INE002A01018,RELIANCE,EQ,,,,,"
        "Reliance Industries,1370.00,1385.00,1360.00,1378.50,1378.00,1365.00,,"
        "1378.50,,,1000,1378000,100,F1,1,,,,,\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("BhavCopy_NSE_CM_0_0_0_20260904_F_0000.csv", csv_text)
    return buffer.getvalue()


def test_udiff_parser_extracts_exact_eq_open_close_and_isin():
    price = parse_udiff_equity(
        _udiff_zip(),
        symbol="RELIANCE",
        session_date=date(2026, 9, 4),
        expected_isin="INE002A01018",
    )
    assert price.open_price == 1370.0
    assert price.close_price == 1378.5
    assert price.isin == "INE002A01018"


def test_udiff_parser_rejects_wrong_isin():
    with pytest.raises(MarketDataError, match="ISIN mismatch"):
        parse_udiff_equity(
            _udiff_zip(),
            symbol="RELIANCE",
            session_date=date(2026, 9, 4),
            expected_isin="WRONG",
        )


def test_index_snapshot_parser_uses_exact_open_and_close():
    raw = (
        "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,"
        "Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield\n"
        "Nifty 50,04-09-2026,23910.9,24005.75,23895.85,23897.7,24.25,.1,1,2,3,4,5\n"
        "Nifty200 Momentum 30,04-09-2026,30000,30100,29900,30050,1,.1,1,2,3,4,5\n"
    ).encode()
    nifty = parse_index_snapshot(raw, benchmark_id="nifty_50", session_date=date(2026, 9, 4))
    momentum = parse_index_snapshot(
        raw, benchmark_id="nifty_200_momentum_30", session_date=date(2026, 9, 4)
    )
    assert nifty.open_price == 23910.9
    assert nifty.close_price == 23897.7
    assert momentum.close_price == 30050.0


def test_price_basis_audit_is_stable_until_share_basis_action_changes():
    empty = []
    first = audit_price_basis_actions(
        empty,
        raw_payload=b"[]",
        symbol="TEST",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 10, 1),
    )
    later = audit_price_basis_actions(
        empty,
        raw_payload=b"[]",
        symbol="TEST",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 11, 1),
    )
    assert first.status == "READY"
    assert first.version == later.version


def test_rights_action_is_fail_closed_for_raw_price_comparability():
    payload = [
        {"symbol": "TEST", "subject": "Rights 3:25 @ Premium", "exDate": "10-Oct-2026"}
    ]
    audit = audit_price_basis_actions(
        payload,
        raw_payload=b"rights",
        symbol="TEST",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 11, 1),
    )
    assert audit.status == "UNRESOLVED"
    assert audit.version is None
