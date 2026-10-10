"""Re-use exact official P008 daily bytes for all independently frozen P005 cohorts.

No downloads, future return calculations or posterior stock-selection changes.
Outputs are immutable, source-hashed, research-only cohort observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from marketlab.h021_cohort_source import (
    _verify_p005_intent,
    build_future_cohort_source,
    validate_future_cohort_source,
)
from marketlab.h021_daily_prices import validate_daily_source_observation


def _json(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"source must contain a JSON object: {path}")
    return payload


def _raw(directory: Path, sha: str, suffix: str) -> bytes:
    if not isinstance(sha,str) or len(sha)!=64:
        raise ValueError("original raw NSE source SHA-256 missing")
    path=directory/"raw"/"sha256"/f"{sha}{suffix}"
    payload=path.read_bytes()
    if not payload or hashlib.sha256(payload).hexdigest()!=sha:
        raise ValueError("retained original NSE source bytes do not match SHA-256")
    return payload


def materialize_all(
    intent_dir:Path,
    daily_dir:Path,
    output_dir:Path,
) -> dict:
    intents=sorted(intent_dir.glob("*-primary-entry-intent-v2.json"))
    daily_files=sorted(daily_dir.glob("????-??-??-v1.json"))
    made=0
    existing=0
    eligible_days=0
    zero_signal_cohorts=0
    for intent_file in intents:
        intent=_json(intent_file)
        source=intent.get("source") or {}
        cohort_date=source.get("comparison_date_ist")
        if not isinstance(cohort_date,str) or intent_file.name!=f"{cohort_date}-primary-entry-intent-v2.json":
            raise ValueError("H021 P005 cohort filename does not match source date")
        planned=intent.get("planned_entry")
        if not isinstance(planned,dict):
            raise TypeError("P005 intent missing original entry plan")
        first_date=planned.get("session_date_ist")
        if not isinstance(first_date,str):
            raise TypeError("P005 planned entry date missing")
        _verify_p005_intent(intent)
        if intent.get("selected_count") == 0:
            zero_signal_cohorts+=1
            continue
        for daily_path in daily_files:
            day=daily_path.name[:-len("-v1.json")]
            if day<first_date:
                continue
            daily=_json(daily_path)
            validate_daily_source_observation(daily)
            if daily.get("session_date_ist")!=day:
                raise ValueError("daily official source filename/date disagreement")
            if daily.get("capture_state")!="SOURCE_COMPLETE":
                raise ValueError("sealed H021 P008 record is not source complete")
            stock_raw=_raw(daily_dir,daily["stock_source"]["sha256"],".zip")
            index_raw=_raw(daily_dir,daily["index_source"]["sha256"],".csv")
            out=build_future_cohort_source(
                intent,daily,raw_udiff=stock_raw,raw_index=index_raw
            )
            validate_future_cohort_source(out)
            destination=output_dir/cohort_date/f"{day}-v1.json"
            eligible_days+=1
            if destination.exists():
                previous=_json(destination)
                validate_future_cohort_source(previous)
                if previous!=out:
                    raise ValueError("existing future H021 source packet differs: "+str(destination))
                existing+=1
                continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open("x",encoding="utf-8") as handle:
                json.dump(out,handle,indent=2,sort_keys=True,allow_nan=False)
                handle.write("\n")
            made+=1
    return {
        "schema_version":1,
        "workflow_id":"H021-P009-COHORT-SOURCE-FANOUT-v1",
        "frozen_future_intent_count":len(intents),
        "sealed_daily_source_count":len(daily_files),
        "eligible_cohort_day_pairs":eligible_days,
        "zero_eligible_cohorts_with_no_source_positions":zero_signal_cohorts,
        "new_cohort_source_packets":made,
        "existing_verified_packets":existing,
        "outcomes_opened":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intent-dir",required=True,type=Path)
    parser.add_argument("--daily-dir",required=True,type=Path)
    parser.add_argument("--output-dir",required=True,type=Path)
    args=parser.parse_args()
    result=materialize_all(args.intent_dir,args.daily_dir,args.output_dir)
    print(json.dumps(result,sort_keys=True,allow_nan=False))


if __name__=="__main__":
    main()
