"""Fan out one original official NSE bhavcopy into every frozen future H021 cohort.

No additional market source, re-ranking, outcome evaluation, portfolio
allocation or return calculation. Each future P005 cohort is sealed before
its entry; shared P008 daily UDiFF bytes supply observations after entry.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, date, datetime
from typing import Any

from marketlab.h021_daily_prices import validate_daily_source_observation
from marketlab.h021_entry_observation import _canonical_hash
from marketlab.h021_future_intent import (
    EXPECTED_CALENDAR_GIT_BLOB,
    EXPECTED_UNIVERSE_GIT_BLOB,
    RULE_ID,
)
from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    PF001MarketDataMissingRow,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

FANOUT_ID = "H021-P009-FUTURE-COHORT-OFFICIAL-SOURCE-v1"
REQUIRED_INTENT_CLASS = "NEXT_OPEN_OUTCOME_BLIND_RESEARCH_INTENT_NOT_PORTFOLIO"
REQUIRED_SOURCE_CLASS = "FUTURE_NSE_PRICE_SOURCE_CAPTURE_NOT_H021_OUTCOME"


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("H021 source date must be ISO timestamp string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid ISO source timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("H021 source timestamps must include timezone")
    return parsed.astimezone(UTC)


def _verify_p005_intent(intent: dict[str, Any]) -> tuple[str, str, dict[str, str]]:
    if intent.get("schema_version") != 1:
        raise ValueError("invalid P005 cohort schema")
    if intent.get("rule_id") != RULE_ID or intent.get("classification") != REQUIRED_INTENT_CLASS:
        raise ValueError("only frozen future H021 P005 cohorts are supported")
    if (
        intent.get("return_outcomes_opened") is not False
        or intent.get("trades_executed") is not False
        or intent.get("portfolio_eligibility_allowed") is not False
        or intent.get("live_capital_allowed") is not False
    ):
        raise ValueError("H021 future intent cannot contain trades/outcomes/capital")
    original_hash = intent.get("packet_sha256")
    unsigned = {k:v for k,v in intent.items() if k != "packet_sha256"}
    if not isinstance(original_hash,str) or _canonical_hash(unsigned) != original_hash:
        raise ValueError("future cohort immutable intent hash mismatch")
    src = intent.get("source")
    if not isinstance(src,dict):
        raise TypeError("H021 P005 original source anchor missing")
    if (
        src.get("universe_git_blob_sha") != EXPECTED_UNIVERSE_GIT_BLOB
        or src.get("calendar_git_blob_sha") != EXPECTED_CALENDAR_GIT_BLOB
    ):
        raise ValueError("future H021 cohort source universe/calendar mismatch")
    cohort_date = src.get("comparison_date_ist")
    if not isinstance(cohort_date,str):
        raise TypeError("H021 P005 cohort date missing")
    date.fromisoformat(cohort_date)
    if intent.get("intent_id") != f"H021-P005-{cohort_date}-PRIMARY-ENTRY-v1":
        raise ValueError("H021 P005 intent identity disagrees with source date")
    plan = intent.get("planned_entry")
    if not isinstance(plan,dict):
        raise TypeError("future H021 entry plan missing")
    entry_date = plan.get("session_date_ist")
    if not isinstance(entry_date,str):
        raise TypeError("future H021 planned entry session missing")
    date.fromisoformat(entry_date)
    if (
        plan.get("actual_execution_verified") is not False
        or plan.get("price_proxy") != "NEXT_COMPLETED_SESSION_FIRST_EXECUTABLE_OPEN"
        or intent.get("primary_horizon_completed_sessions") != 60
        or intent.get("secondary_horizon_completed_sessions") != 20
        or intent.get("benchmark_family") != "NIFTY_500"
    ):
        raise ValueError("frozen H021 entry/holding/benchmark contract changed")
    if _timestamp(intent.get("prepared_at_utc")) >= _timestamp(plan.get("open_timestamp_utc")):
        raise ValueError("P005 intent prepared after proposed next-session open")
    rows = intent.get("selected_observations")
    if not isinstance(rows,list) or not 0 <= len(rows) <= 100:
        raise ValueError("future H021 selected set invalid")
    if not rows and intent.get("eligible_count") != 0:
        raise ValueError("empty future H021 cohort requires zero eligible source rows")
    if len(rows) != intent.get("selected_count"):
        raise ValueError("future H021 selected count changed")
    ids:dict[str,str]={}
    for row in rows:
        if not isinstance(row,dict):
            raise TypeError("future H021 selected row must be object")
        symbol,isin=row.get("symbol"),row.get("isin")
        if (
            not isinstance(symbol,str) or not symbol or symbol in ids
            or not isinstance(isin,str) or len(isin)!=12
            or row.get("entry_price") is not None
            or row.get("capital_weight") is not None
            or row.get("entry_status") != "UNOBSERVED"
        ):
            raise ValueError("future cohort identity, ISIN or no-fill contract changed")
        score=row.get("eps_revision_pct")
        if type(score) not in (float,int) or not math.isfinite(score):
            raise ValueError("frozen future cohort revision is not finite")
        ids[symbol]=isin
    return cohort_date,entry_date,ids


def build_future_cohort_source(
    intent:dict[str,Any],
    daily_packet:dict[str,Any],
    *,
    raw_udiff:bytes,
    raw_index:bytes,
) -> dict[str,Any]:
    cohort_date,entry_date,ids=_verify_p005_intent(intent)
    validate_daily_source_observation(daily_packet)
    if daily_packet.get("classification") != REQUIRED_SOURCE_CLASS:
        raise ValueError("unrecognized official daily source contract")
    if daily_packet.get("capture_state") != "SOURCE_COMPLETE":
        raise ValueError("cannot fan out partial or blocked official source data")
    observed_date=daily_packet.get("session_date_ist")
    if not isinstance(observed_date,str):
        raise TypeError("market observation day missing")
    market_day=date.fromisoformat(observed_date)
    if observed_date < entry_date:
        raise ValueError("future H021 holding observation precedes frozen entry")
    if not isinstance(raw_udiff,bytes) or not isinstance(raw_index,bytes):
        raise TypeError("both exact official NSE source files are required")
    if (
        hashlib.sha256(raw_udiff).hexdigest() != daily_packet["stock_source"]["sha256"]
        or hashlib.sha256(raw_index).hexdigest() != daily_packet["index_source"]["sha256"]
    ):
        raise ValueError("original NSE raw ZIP/index SHA differs from sealed daily packet")
    if _timestamp(daily_packet["recorded_at_utc"]) < _timestamp(intent["prepared_at_utc"]):
        raise ValueError("daily source chronology precedes frozen cohort decision")

    company_rows=[]
    valid=0
    for symbol,isin in ids.items():
        open_value=None
        close_value=None
        status="OFFICIAL_ROW_MISSING"
        try:
            data=parse_pf001_udiff_equity(
                raw_udiff,symbol=symbol,session_date=market_day,expected_isin=isin
            )
        except PF001MarketDataMissingRow:
            status="OFFICIAL_EQ_ROW_MISSING_NO_BACKFILL"
        except PF001MarketDataError:
            status="INVALID_SOURCE_OR_ISIN_NO_BACKFILL"
        else:
            open_value=data.open_price
            close_value=data.close_price
            status="OFFICIAL_RAW_OPEN_CLOSE_OBSERVED"
            valid+=1
        company_rows.append({
            "symbol":symbol,
            "isin":isin,
            "observed_open_inr":open_value,
            "observed_close_inr":close_value,
            "source_sha256":daily_packet["stock_source"]["sha256"],
            "state":status,
            "corporate_action_adjusted":False,
            "trade_executed":False,
        })
    index=parse_pf001_nifty500_index(raw_index,session_date=market_day)
    total=len(ids)
    packet={
        "schema_version":1,
        "record_id":FANOUT_ID,
        "classification":"P005_COHORT_SOURCE_FANOUT_NOT_FUTURE_RETURN",
        "future_cohort_id":intent["intent_id"],
        "cohort_date_ist":cohort_date,
        "first_planned_entry_session":entry_date,
        "session_date_ist":observed_date,
        "session_role":"ENTRY_PROXY_SOURCE" if observed_date==entry_date else "HOLDING_PERIOD_SOURCE",
        "intent_sha256":intent["packet_sha256"],
        "original_daily_source_sha256":daily_packet["packet_sha256"],
        "original_udiff_sha256":daily_packet["stock_source"]["sha256"],
        "original_nifty_500_sha256":daily_packet["index_source"]["sha256"],
        "selected_symbol_count":total,
        "official_stock_row_count":valid,
        "source_state":"COMPLETE" if valid==total else "INCOMPLETE_NO_SUBSTITUTION",
        "company_rows":company_rows,
        "benchmark":{
            "index":"Nifty 500",
            "basis":"UNADJUSTED_PRICE_INDEX_NOT_TRI",
            "open":index.open_price,
            "close":index.close_price,
        },
        "calendar_special_session_resolution_unverified":True,
        "corporate_action_dividend_basis_verified":False,
        "benchmark_excess_return_calculated":False,
        "holding_period_return_calculated":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    packet["packet_sha256"]=_canonical_hash(packet)
    return packet


def validate_future_cohort_source(packet:dict[str,Any]) -> None:
    if packet.get("record_id")!=FANOUT_ID:
        raise ValueError("unrecognized future H021 cohort source packet")
    digest=packet.get("packet_sha256")
    if not isinstance(digest,str) or len(digest)!=64:
        raise ValueError("future cohort packet digest missing")
    if _canonical_hash({k:v for k,v in packet.items() if k!="packet_sha256"})!=digest:
        raise ValueError("future cohort source packet was altered")
    for field in (
        "corporate_action_dividend_basis_verified","benchmark_excess_return_calculated",
        "holding_period_return_calculated","portfolio_eligibility_allowed","live_capital_allowed",
    ):
        if packet.get(field) is not False:
            raise ValueError(f"future cohort source cannot authorize {field}")
