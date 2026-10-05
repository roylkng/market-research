from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

SELECTION_ID="HG006-S001-v1"
EXPECTED_D001_ID="HG006-D001-v1"
EXPECTED_D001_SHA="a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5"
TARGET_PER_FAMILY=150
FAMILIES=("PREFERENTIAL_WARRANT","SCHEME_REORGANISATION")


def selection_key(chronology_id:str)->str:
    if not chronology_id:
        raise AlphaContractError("HG006 S001 chronology_id required")
    return hashlib.sha256(
        f"{SELECTION_ID}|{chronology_id}".encode("utf-8")
    ).hexdigest()


def build_calibration_cohort(census:dict[str,Any])->dict[str,Any]:
    if census.get("census_id")!=EXPECTED_D001_ID:
        raise AlphaContractError("HG006 S001 requires frozen D001 census")
    if census.get("census_sha256")!=EXPECTED_D001_SHA:
        raise AlphaContractError("HG006 S001 D001 census SHA mismatch")
    for field in (
        "completion_probabilities_assigned",
        "expected_returns_calculated",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"HG006 S001 requires D001 {field}=false")

    chronologies=census.get("chronologies")
    if not isinstance(chronologies,list):
        raise AlphaContractError("HG006 S001 chronologies unavailable")

    by_family={family:[] for family in FAMILIES}
    for row in chronologies:
        if not isinstance(row,dict):
            raise TypeError("HG006 S001 chronology rows must be objects")
        family=str(row.get("family") or "")
        if family not in by_family:
            continue
        chronology_id=str(row.get("chronology_id") or "")
        if not chronology_id:
            raise AlphaContractError("HG006 S001 chronology missing ID")
        by_family[family].append({
            "chronology_id":chronology_id,
            "symbol":row.get("symbol"),
            "family":family,
            "first_observed_at_utc":row.get("first_observed_at_utc"),
            "last_observed_at_utc":row.get("last_observed_at_utc"),
            "first_initiation_window_at_utc":row.get("first_initiation_window_at_utc"),
            "event_count":row.get("event_count"),
            "initiation_window_event_count":row.get("initiation_window_event_count"),
            "followup_event_count":row.get("followup_event_count"),
            "has_approved_attachment":bool(row.get("has_approved_attachment")),
            "announcement_ids":[str(v) for v in row.get("announcement_ids",[])],
            "selection_key":selection_key(chronology_id),
        })

    selected=[]
    available_counts={}
    for family in FAMILIES:
        rows=by_family[family]
        available_counts[family]=len(rows)
        if len(rows)<TARGET_PER_FAMILY:
            raise AlphaContractError(
                f"HG006 S001 family {family} has only {len(rows)} chronologies"
            )
        rows=sorted(rows,key=lambda row:(row["selection_key"],row["chronology_id"]))
        selected.extend(rows[:TARGET_PER_FAMILY])

    if len(selected)!=TARGET_PER_FAMILY*len(FAMILIES):
        raise AlphaContractError("HG006 S001 selected count mismatch")
    chronology_ids=[row["chronology_id"] for row in selected]
    if len(chronology_ids)!=len(set(chronology_ids)):
        raise AlphaContractError("HG006 S001 duplicate chronology selection")

    counts=Counter(row["family"] for row in selected)
    attachment_counts=Counter(
        row["family"] for row in selected if row["has_approved_attachment"]
    )
    event_count=sum(int(row["event_count"] or 0) for row in selected)

    output={
        "schema_version":1,
        "selection_id":SELECTION_ID,
        "classification":"HISTORICAL_CALIBRATION_COHORT_NOT_PROBABILITY",
        "source_d001_census_sha256":EXPECTED_D001_SHA,
        "families":list(FAMILIES),
        "target_per_family":TARGET_PER_FAMILY,
        "available_chronology_counts":dict(sorted(available_counts.items())),
        "selected_chronology_count":len(selected),
        "selected_chronology_counts_by_family":dict(sorted(counts.items())),
        "selected_attachment_ready_counts_by_family":dict(
            sorted(attachment_counts.items())
        ),
        "selected_event_link_count":event_count,
        "rows":sorted(
            selected,
            key=lambda row:(row["family"],row["selection_key"],row["chronology_id"]),
        ),
        "historical_terminal_labels_opened":False,
        "completion_probabilities_assigned":False,
        "expected_returns_calculated":False,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    output["selection_sha256"]=digest(output)
    return output
