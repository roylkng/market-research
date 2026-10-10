from __future__ import annotations

import csv
import io
import json
import zipfile
from copy import deepcopy
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from marketlab.h021_daily_prices import (
    build_daily_source_observation,
    validate_daily_source_observation,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from scripts.collect_h021_daily_official import load_frozen_sources, save_attempt

SESSION = "2026-10-13"
CAPTURED = "2026-10-13T12:00:00Z"
RECORDED = "2026-10-13T12:01:00Z"


def _stock_zip(universe: dict, *, missing: str | None = None, mismatched: str | None = None) -> bytes:
    symbols = [
        "VEDL","ETERNAL","DMART","IDEA","ADANIENSOL",
        "JSWSTEEL","COALINDIA","INFY","GAIL","POWERGRID",
    ]
    isin={x["symbol"]:x["isin"] for x in universe["members"]}
    stream=io.StringIO()
    fields=["TradDt","Sgmt","Src","FinInstrmTp","ISIN","TckrSymb","SctySrs",
            "OpnPric","HghPric","LwPric","ClsPric"]
    writer=csv.DictWriter(stream,fieldnames=fields)
    writer.writeheader()
    for i,symbol in enumerate(symbols):
        if symbol==missing:
            continue
        price=100+i
        writer.writerow({
            "TradDt":SESSION,"Sgmt":"CM","Src":"NSE","FinInstrmTp":"STK",
            "ISIN":"INEBADBADBAD" if symbol==mismatched else isin[symbol],
            "TckrSymb":symbol,"SctySrs":"EQ","OpnPric":price,
            "HghPric":price+2,"LwPric":price-1,"ClsPric":price+1,
        })
    output=io.BytesIO()
    with zipfile.ZipFile(output,"w") as z:
        z.writestr("BhavCopy_NSE_CM_0_0_0_20261013_F_0000.csv",stream.getvalue())
    return output.getvalue()


def _index_csv() -> bytes:
    return (
        b"Index Name,Index Date,Open Index Value,Closing Index Value\n"
        b"Nifty 500,13-10-2026,23000,23050\n"
        b"Nifty 50,13-10-2026,25100,25200\n"
    )


def _source(name: str, body: bytes | None) -> dict:
    url = udiff_url(date(2026,10,13)) if name=="udiff" else index_snapshot_url(date(2026,10,13))
    return {
        "url":url,"captured_at_utc":CAPTURED,
        "status":"OK" if body is not None else "NOT_PUBLISHED",
        "http_status":200 if body is not None else 404,
        "raw":body,"error":None if body is not None else "OFFICIAL_FILE_NOT_PUBLISHED",
    }


def _produce(*, missing: str | None=None, mismatch: str | None=None,
             no_index: bool=False) -> dict:
    intent,universe,calendar=load_frozen_sources()
    return build_daily_source_observation(
        intent,universe,calendar,session_date=SESSION,
        udiff_source=_source("udiff",_stock_zip(universe,missing=missing,mismatched=mismatch)),
        index_source=_source("index",None if no_index else _index_csv()),
        recorded_at_utc=RECORDED,
    )


def test_full_official_daily_observation_is_not_a_return() -> None:
    payload=_produce()
    validate_daily_source_observation(payload)
    assert payload["capture_state"]=="SOURCE_COMPLETE"
    assert payload["observed_stock_count"]==10
    assert payload["selected_company_count"]==10
    assert payload["stock_rows"][0]["symbol"]=="VEDL"
    assert payload["stock_rows"][0]["ohlc"]["open_inr"]==100.0
    assert payload["benchmark"]["open"]==23000.0
    assert payload["benchmark"]["basis"]=="PRICE_INDEX_NOT_TRI"
    assert payload["packet_sha256"]
    for field in (
        "horizon_return_calculated","benchmark_excess_calculated",
        "corporate_actions_resolved","dividends_adjusted","trades_filled",
        "portfolio_eligibility_allowed","live_capital_allowed",
    ):
        assert payload[field] is False
    assert all(not r["trade_filled"] for r in payload["stock_rows"])


def test_missing_or_wrong_isin_never_fills_unknown_price() -> None:
    payload=_produce(missing="VEDL",mismatch="GAIL")
    indexed={r["symbol"]:r for r in payload["stock_rows"]}
    assert indexed["VEDL"]["status"]=="OFFICIAL_EQ_ROW_MISSING"
    assert indexed["VEDL"]["ohlc"]["open_inr"] is None
    assert indexed["GAIL"]["status"]=="INVALID_OFFICIAL_EQ_SOURCE"
    assert indexed["GAIL"]["ohlc"]["open_inr"] is None
    assert payload["observed_stock_count"]==8
    assert payload["capture_state"]=="SOURCE_INCOMPLETE"


def test_missing_index_retains_stocks_but_not_source_complete() -> None:
    payload=_produce(no_index=True)
    assert payload["observed_stock_count"]==10
    assert payload["benchmark"]["status"]=="SOURCE_MISSING"
    assert payload["capture_state"]=="SOURCE_INCOMPLETE"


def test_requires_completed_official_session_and_original_calendar() -> None:
    intent,universe,calendar=load_frozen_sources()
    kw=dict(udiff_source=_source("udiff",_stock_zip(universe)),
            index_source=_source("index",_index_csv()),recorded_at_utc=RECORDED)
    with pytest.raises(ValueError,match="post-entry"):
        build_daily_source_observation(
            intent,universe,calendar,session_date="2026-10-12",**kw
        )
    with pytest.raises(ValueError,match="post-entry"):
        build_daily_source_observation(
            intent,universe,calendar,session_date="2027-01-04",**kw
        )
    corrupted_calendar=replace(calendar,unresolved_special_dates=())
    with pytest.raises(ValueError,match="calendar source was modified"):
        build_daily_source_observation(
            intent,universe,corrupted_calendar,session_date=SESSION,**kw
        )


def test_source_must_be_official_and_observed_after_close() -> None:
    intent,universe,calendar=load_frozen_sources()
    udiff=_source("udiff",_stock_zip(universe))
    index=_source("index",_index_csv())
    udiff["captured_at_utc"]="2026-10-13T09:59:59Z"
    with pytest.raises(ValueError,match="before official session close"):
        build_daily_source_observation(
            intent,universe,calendar,session_date=SESSION,udiff_source=udiff,
            index_source=index,recorded_at_utc=RECORDED
        )
    udiff=_source("udiff",_stock_zip(universe))
    udiff["url"]="https://other.example.com/udiff"
    with pytest.raises(ValueError,match="unexpected NSE source URL"):
        build_daily_source_observation(
            intent,universe,calendar,session_date=SESSION,udiff_source=udiff,
            index_source=index,recorded_at_utc=RECORDED
        )


def test_source_ledger_is_provenance_but_never_execution(tmp_path: Path) -> None:
    intent,universe,calendar=load_frozen_sources()
    packet=save_attempt(
        output_dir=tmp_path,session_date=SESSION,intent=intent,universe=universe,
        calendar=calendar,udiff=_source("udiff",_stock_zip(universe)),
        index=_source("index",_index_csv()),recorded_at_utc=RECORDED
    )
    assert packet["capture_state"]=="SOURCE_COMPLETE"
    assert packet["live_capital_allowed"] is False
    assert len(packet["originals_retained"])==2
    assert all((tmp_path/r["path"]).exists() for r in packet["originals_retained"])
    source=json.loads((tmp_path/"observation.json").read_text(encoding="utf-8"))
    validate_daily_source_observation(source)
    assert packet["packet_sha256"]==source["packet_sha256"]


def test_output_tamper_detection_and_intent_copy_not_mutated() -> None:
    intent,universe,calendar=load_frozen_sources()
    frozen=deepcopy(intent)
    packet=build_daily_source_observation(
        intent,universe,calendar,session_date=SESSION,
        udiff_source=_source("udiff",_stock_zip(universe)),
        index_source=_source("index",_index_csv()),
        recorded_at_utc=RECORDED
    )
    assert intent==frozen
    packet["stock_rows"][0]["ohlc"]["open_inr"]=999.0
    with pytest.raises(ValueError,match="modified after sealing"):
        validate_daily_source_observation(packet)



def test_resolver_never_acquires_before_market_close_or_unverified_2027(tmp_path: Path) -> None:
    from datetime import UTC, datetime
    from scripts.resolve_h021_daily_session import resolve_session

    _intent, _universe, calendar = load_frozen_sources()
    before = resolve_session(
        calendar, tmp_path, as_of_utc=datetime(2026,10,13,9,0,tzinfo=UTC)
    )
    assert before["state"] == "NO_COMPLETED_PENDING_SESSION"

    after = resolve_session(
        calendar, tmp_path, as_of_utc=datetime(2026,10,13,11,0,tzinfo=UTC)
    )
    assert after["state"] == "CAPTURE"
    assert after["session_date"] == "2026-10-13"
    assert after["outcomes_opened"] is False
    assert after["live_capital_allowed"] is False


def test_resolver_bounds_source_failures_and_proceeds_with_missing_record(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime
    from scripts.resolve_h021_daily_session import resolve_session

    _intent, _universe, calendar = load_frozen_sources()
    root = tmp_path
    attempts = root / "attempts"
    attempts.mkdir()
    asof = datetime(2026, 10, 14, 13, 0, tzinfo=UTC)
    for i in range(3):
        (attempts / f"2026-10-13-run{i}.json").write_text('{"missing":true}')
    resolved = resolve_session(calendar, root, as_of_utc=asof)
    assert resolved["state"] == "CAPTURE"
    assert resolved["session_date"] == "2026-10-14"
    assert resolved["unresolved_past_sessions"] == [
        {
            "session_date": "2026-10-13",
            "state": "SOURCE_UNRESOLVED_AFTER_BOUNDED_RETRIES",
            "attempts": 3,
        }
    ]


def test_resolver_validates_old_immutable_packet_before_skipping(tmp_path: Path) -> None:
    from datetime import UTC, datetime
    from scripts.resolve_h021_daily_session import resolve_session

    _intent, _universe, calendar = load_frozen_sources()
    payload = _produce()
    (tmp_path / "2026-10-13-v1.json").write_text(
        json.dumps(payload,sort_keys=True)
    )
    resolved=resolve_session(
        calendar,tmp_path,as_of_utc=datetime(2026,10,14,12,0,tzinfo=UTC)
    )
    assert resolved["state"]=="CAPTURE"
    assert resolved["session_date"]=="2026-10-14"
    assert resolved["previous_complete_sessions"]==1

    (tmp_path / "2026-10-13-v1.json").write_text(json.dumps({"bad":"packet"}))
    with pytest.raises(ValueError,match="digest"):
        resolve_session(
            calendar,tmp_path,as_of_utc=datetime(2026,10,14,12,0,tzinfo=UTC)
        )
