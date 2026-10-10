from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_cohort_source import (
    build_future_cohort_source,
    validate_future_cohort_source,
)
from marketlab.h021_daily_prices import build_daily_source_observation
from marketlab.h021_entry_observation import EXPECTED_SELECTION, _canonical_hash
from marketlab.h021_future_intent import (
    EXPECTED_CALENDAR_GIT_BLOB,
    EXPECTED_UNIVERSE_GIT_BLOB,
    RULE_ID,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from scripts.collect_h021_daily_official import load_frozen_sources
from scripts.fanout_h021_future_cohorts import materialize_all

DATE="2026-10-19"
CAPTURED="2026-10-19T12:00:00Z"
RECORDED="2026-10-19T12:30:00Z"


def _future_intent(universe:dict) -> dict:
    symbols={x["symbol"]:x["isin"] for x in universe["members"]}
    intent={
        "schema_version":1,
        "rule_id":RULE_ID,
        "intent_id":"H021-P005-2026-10-16-PRIMARY-ENTRY-v1",
        "classification":"NEXT_OPEN_OUTCOME_BLIND_RESEARCH_INTENT_NOT_PORTFOLIO",
        "prepared_at_utc":"2026-10-16T13:30:00Z",
        "source":{
            "comparison_date_ist":"2026-10-16",
            "prior_capture_date_ist":"2026-09-18",
            "universe_git_blob_sha":EXPECTED_UNIVERSE_GIT_BLOB,
            "calendar_git_blob_sha":EXPECTED_CALENDAR_GIT_BLOB,
        },
        "planned_entry":{
            "session_date_ist":DATE,
            "open_timestamp_utc":"2026-10-19T03:45:00Z",
            "price_proxy":"NEXT_COMPLETED_SESSION_FIRST_EXECUTABLE_OPEN",
            "actual_execution_verified":False,
        },
        "primary_horizon_completed_sessions":60,
        "secondary_horizon_completed_sessions":20,
        "benchmark_family":"NIFTY_500",
        "selected_count":2,
        "selected_observations":[
            {"symbol":"RELIANCE","isin":symbols["RELIANCE"],"eps_revision_pct":1.5,
             "entry_price":None,"capital_weight":None,"entry_status":"UNOBSERVED"},
            {"symbol":"VEDL","isin":symbols["VEDL"],"eps_revision_pct":1.2,
             "entry_price":None,"capital_weight":None,"entry_status":"UNOBSERVED"},
        ],
        "return_outcomes_opened":False,
        "trades_executed":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    intent["packet_sha256"]=_canonical_hash(intent)
    return intent


def _original_zip(universe:dict,*,missing:str|None=None) -> bytes:
    pairs={x["symbol"]:x["isin"] for x in universe["members"]}
    writer_text=io.StringIO()
    headers=["TradDt","Sgmt","Src","FinInstrmTp","ISIN","TckrSymb","SctySrs",
             "OpnPric","HghPric","LwPric","ClsPric"]
    writer=csv.DictWriter(writer_text,fieldnames=headers)
    writer.writeheader()
    for i,symbol in enumerate([*EXPECTED_SELECTION,"RELIANCE"]):
        if symbol==missing:
            continue
        p=100+i
        writer.writerow({
            "TradDt":DATE,"Sgmt":"CM","Src":"NSE","FinInstrmTp":"STK",
            "ISIN":pairs[symbol],"TckrSymb":symbol,"SctySrs":"EQ",
            "OpnPric":p,"HghPric":p+3,"LwPric":p-2,"ClsPric":p+1,
        })
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as z:
        z.writestr("BhavCopy_NSE_CM_0_0_0_20261019_F_0000.csv",writer_text.getvalue())
    return buf.getvalue()


def _index() -> bytes:
    return (
        b"Index Name,Index Date,Open Index Value,Closing Index Value\n"
        b"Nifty 500,19-10-2026,24000,24150\n"
    )


def _source(url:str,raw:bytes) -> dict:
    return {
        "status":"OK","url":url,"http_status":200,
        "captured_at_utc":CAPTURED,"raw":raw,"error":None,
    }


def _inputs() -> tuple[dict,dict,bytes,bytes]:
    p003,universe,calendar=load_frozen_sources()
    raw_stock=_original_zip(universe)
    raw_index=_index()
    day=__import__("datetime").date(2026,10,19)
    daily=build_daily_source_observation(
        p003,universe,calendar,session_date=DATE,
        udiff_source=_source(udiff_url(day),raw_stock),
        index_source=_source(index_snapshot_url(day),raw_index),
        recorded_at_utc=RECORDED,
    )
    assert daily["capture_state"]=="SOURCE_COMPLETE"
    return _future_intent(universe),daily,raw_stock,raw_index


def test_shared_full_market_source_can_observe_new_cohort_symbols() -> None:
    intent,daily,udiff,index=_inputs()
    original=deepcopy((intent,daily))
    result=build_future_cohort_source(
        intent,daily,raw_udiff=udiff,raw_index=index
    )
    validate_future_cohort_source(result)
    assert [row["symbol"] for row in result["company_rows"]]==["RELIANCE","VEDL"]
    assert result["official_stock_row_count"]==2
    assert result["session_role"]=="ENTRY_PROXY_SOURCE"
    assert result["source_state"]=="COMPLETE"
    assert result["benchmark"]["open"]==24000.0
    assert result["company_rows"][0]["observed_open_inr"]==110.0
    assert result["holding_period_return_calculated"] is False
    assert result["benchmark_excess_return_calculated"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
    assert (intent,daily)==original


def test_missing_new_symbol_remains_missing_no_retrospective_fill() -> None:
    p003,universe,calendar=load_frozen_sources()
    udiff=_original_zip(universe,missing="RELIANCE")
    index=_index()
    day=__import__("datetime").date(2026,10,19)
    daily=build_daily_source_observation(
        p003,universe,calendar,session_date=DATE,
        udiff_source=_source(udiff_url(day),udiff),
        index_source=_source(index_snapshot_url(day),index),
        recorded_at_utc=RECORDED,
    )
    assert daily["capture_state"]=="SOURCE_COMPLETE"
    result=build_future_cohort_source(
        _future_intent(universe),daily,raw_udiff=udiff,raw_index=index
    )
    assert result["source_state"]=="INCOMPLETE_NO_SUBSTITUTION"
    assert result["company_rows"][0]["observed_open_inr"] is None
    assert result["company_rows"][0]["state"]=="OFFICIAL_EQ_ROW_MISSING_NO_BACKFILL"


def test_provenance_tampering_rejected() -> None:
    intent,daily,udiff,index=_inputs()
    with pytest.raises(ValueError,match="raw ZIP/index SHA"):
        build_future_cohort_source(
            intent,daily,raw_udiff=udiff+b"changed",raw_index=index
        )

    tampered_intent=deepcopy(intent)
    tampered_intent["selected_observations"][0]["symbol"]="FICTITIOUS"
    with pytest.raises(ValueError,match="hash mismatch"):
        build_future_cohort_source(
            tampered_intent,daily,raw_udiff=udiff,raw_index=index
        )

    corrupted_daily=deepcopy(daily)
    corrupted_daily["benchmark"]["open"]=999.0
    with pytest.raises(ValueError,match="modified after sealing"):
        build_future_cohort_source(
            intent,corrupted_daily,raw_udiff=udiff,raw_index=index
        )


def test_no_cohort_price_before_frozen_entry() -> None:
    intent,daily,udiff,index=_inputs()
    intent["planned_entry"]["session_date_ist"]="2026-10-20"
    intent["packet_sha256"]=_canonical_hash(
        {k:v for k,v in intent.items() if k!="packet_sha256"}
    )
    with pytest.raises(ValueError,match="precedes frozen entry"):
        build_future_cohort_source(
            intent,daily,raw_udiff=udiff,raw_index=index
        )


def test_materialized_cohort_source_is_immutable(tmp_path:Path) -> None:
    intent,daily,udiff,index=_inputs()
    intents=tmp_path/"intents"
    prices=tmp_path/"daily"
    out=tmp_path/"cohort"
    intents.mkdir()
    prices.mkdir()
    intent_path=intents/"2026-10-16-primary-entry-intent-v2.json"
    intent_path.write_text(json.dumps(intent))
    (prices/f"{DATE}-v1.json").write_text(json.dumps(daily))
    raw_root=prices/"raw"/"sha256"
    raw_root.mkdir(parents=True)
    (raw_root/f"{hashlib.sha256(udiff).hexdigest()}.zip").write_bytes(udiff)
    (raw_root/f"{hashlib.sha256(index).hexdigest()}.csv").write_bytes(index)
    result=materialize_all(intents,prices,out)
    assert result["new_cohort_source_packets"]==1
    assert result["outcomes_opened"] is False
    again=materialize_all(intents,prices,out)
    assert again["new_cohort_source_packets"]==0
    assert again["existing_verified_packets"]==1
    target=out/"2026-10-16"/f"{DATE}-v1.json"
    observed=json.loads(target.read_text())
    observed["company_rows"][0]["observed_open_inr"]=1.0
    target.write_text(json.dumps(observed))
    with pytest.raises(ValueError,match="altered"):
        materialize_all(intents,prices,out)



def test_zero_eligible_future_cohort_does_not_fabricate_positions(tmp_path:Path) -> None:
    _p003,universe,_calendar=load_frozen_sources()
    empty=_future_intent(universe)
    empty["selected_count"]=0
    empty["eligible_count"]=0
    empty["selected_observations"]=[]
    empty["packet_sha256"]=_canonical_hash(
        {k:v for k,v in empty.items() if k!="packet_sha256"}
    )
    intent_root=tmp_path/"intents"
    daily_root=tmp_path/"daily"
    result_root=tmp_path/"cohorts"
    intent_root.mkdir()
    daily_root.mkdir()
    (intent_root/"2026-10-16-primary-entry-intent-v2.json").write_text(
        json.dumps(empty)
    )
    response=materialize_all(intent_root,daily_root,result_root)
    assert response["zero_eligible_cohorts_with_no_source_positions"]==1
    assert response["new_cohort_source_packets"]==0
    assert response["outcomes_opened"] is False
    assert not result_root.exists()
