from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest

THREADING_ID="HG006-D003-v1"


def _anchor_key(anchor:dict[str,Any])->tuple[str,str]:
    anchor_type=str(anchor.get("anchor_type") or "")
    value=anchor.get("value")
    if not anchor_type or value in (None,""):
        raise AlphaContractError("HG006 D003 anchor is incomplete")
    try:
        canonical=json.dumps(
            value,
            sort_keys=True,
            separators=(",",":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError,ValueError) as exc:
        raise AlphaContractError("HG006 D003 anchor value must be finite JSON") from exc
    return anchor_type,canonical


def build_event_anchor_index(
    extractions:list[dict[str,Any]],
)->dict[str,dict[str,Any]]:
    events:dict[str,dict[str,Any]]={}
    for extraction in extractions:
        if not isinstance(extraction,dict):
            raise TypeError("HG006 D003 extraction rows must be objects")
        symbol=str(extraction.get("symbol") or "")
        family=str(extraction.get("family") or "")
        event_ids=extraction.get("event_ids")
        anchors=extraction.get("transaction_anchors")
        if not symbol or not family:
            raise AlphaContractError("HG006 D003 extraction identity missing")
        if not isinstance(event_ids,list) or not event_ids:
            raise AlphaContractError("HG006 D003 extraction event IDs unavailable")
        if not isinstance(anchors,list):
            raise AlphaContractError("HG006 D003 extraction anchors unavailable")
        anchor_keys={_anchor_key(anchor) for anchor in anchors}

        for event_id_raw in event_ids:
            event_id=str(event_id_raw)
            if not event_id:
                raise AlphaContractError("HG006 D003 empty event ID")
            row=events.setdefault(
                event_id,
                {
                    "symbol":symbol,
                    "family":family,
                    "anchor_keys":set(),
                    "document_ids":set(),
                },
            )
            if row["symbol"]!=symbol or row["family"]!=family:
                raise AlphaContractError(
                    f"HG006 D003 event identity conflict: {event_id}"
                )
            row["anchor_keys"].update(anchor_keys)
            document_id=str(extraction.get("document_id") or "")
            if document_id:
                row["document_ids"].add(document_id)
    return events


def deterministic_episode_id(symbol:str,family:str,event_ids:list[str])->str:
    return digest(
        {
            "threading_id":THREADING_ID,
            "symbol":symbol,
            "family":family,
            "event_ids":sorted(event_ids),
        }
    )


def _shared_anchor_support(
    event_ids:list[str],
    event_index:dict[str,dict[str,Any]],
)->list[dict[str,Any]]:
    support:dict[tuple[str,str],set[str]]=defaultdict(set)
    for event_id in event_ids:
        for key in event_index[event_id]["anchor_keys"]:
            support[key].add(event_id)
    rows=[]
    required_count=1 if len(event_ids)==1 else 2
    for (anchor_type,value_json),ids in sorted(support.items()):
        if len(ids)>=required_count:
            rows.append(
                {
                    "anchor_type":anchor_type,
                    "canonical_value_json":value_json,
                    "supporting_event_ids":sorted(ids),
                }
            )
    return rows


def validate_episode_manifest(
    *,
    extractions:list[dict[str,Any]],
    manifest:dict[str,Any],
)->dict[str,Any]:
    event_index=build_event_anchor_index(extractions)
    source_ids=set(event_index)

    if manifest.get("threading_id")!=THREADING_ID:
        raise AlphaContractError("HG006 D003 threading identity mismatch")
    episodes=manifest.get("episodes")
    ambiguous=manifest.get("ambiguous_event_ids")
    unavailable=manifest.get("document_unavailable_event_ids")
    if not isinstance(episodes,list):
        raise TypeError("HG006 D003 episodes must be list")
    if not isinstance(ambiguous,list) or not all(isinstance(x,str) for x in ambiguous):
        raise TypeError("HG006 D003 ambiguous_event_ids must be string list")
    if not isinstance(unavailable,list) or not all(isinstance(x,str) for x in unavailable):
        raise TypeError("HG006 D003 document_unavailable_event_ids must be string list")

    assigned_ids:set[str]=set()
    sealed_episodes=[]
    for episode in episodes:
        if not isinstance(episode,dict):
            raise TypeError("HG006 D003 episode must be object")
        symbol=str(episode.get("symbol") or "")
        family=str(episode.get("family") or "")
        event_ids=episode.get("event_ids")
        if not symbol or not family or not isinstance(event_ids,list) or not event_ids:
            raise AlphaContractError("HG006 D003 episode identity incomplete")
        ids=[str(value) for value in event_ids]
        if len(ids)!=len(set(ids)):
            raise AlphaContractError("HG006 D003 duplicate event inside episode")
        if any(event_id not in source_ids for event_id in ids):
            raise AlphaContractError("HG006 D003 episode contains unknown event")
        if assigned_ids.intersection(ids):
            raise AlphaContractError("HG006 D003 event assigned to multiple episodes")
        for event_id in ids:
            source=event_index[event_id]
            if source["symbol"]!=symbol or source["family"]!=family:
                raise AlphaContractError("HG006 D003 episode crosses symbol/family")
        shared=_shared_anchor_support(ids,event_index)
        if not shared:
            raise AlphaContractError(
                f"HG006 D003 episode lacks explicit transaction anchor support: {symbol}/{family}"
            )
        expected=deterministic_episode_id(symbol,family,ids)
        supplied=str(episode.get("episode_id") or "")
        if supplied!=expected:
            raise AlphaContractError("HG006 D003 episode_id is not deterministic")
        assigned_ids.update(ids)
        sealed_episodes.append(
            {
                "episode_id":expected,
                "symbol":symbol,
                "family":family,
                "event_ids":sorted(ids),
                "shared_anchor_support":shared,
            }
        )

    ambiguous_set=set(ambiguous)
    unavailable_set=set(unavailable)
    if len(ambiguous)!=len(ambiguous_set) or len(unavailable)!=len(unavailable_set):
        raise AlphaContractError("HG006 D003 duplicate excluded event ID")
    if assigned_ids&ambiguous_set or assigned_ids&unavailable_set or ambiguous_set&unavailable_set:
        raise AlphaContractError("HG006 D003 event states overlap")
    accounted=assigned_ids|ambiguous_set|unavailable_set
    if accounted!=source_ids:
        missing=sorted(source_ids-accounted)
        extra=sorted(accounted-source_ids)
        raise AlphaContractError(
            f"HG006 D003 incomplete event accounting missing={missing} extra={extra}"
        )

    output={
        "schema_version":1,
        "threading_id":THREADING_ID,
        "episode_count":len(sealed_episodes),
        "episode_assigned_event_count":len(assigned_ids),
        "ambiguous_event_count":len(ambiguous_set),
        "document_unavailable_event_count":len(unavailable_set),
        "episodes":sorted(sealed_episodes,key=lambda row:row["episode_id"]),
        "ambiguous_event_ids":sorted(ambiguous_set),
        "document_unavailable_event_ids":sorted(unavailable_set),
        "completion_probabilities_assigned":False,
        "return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    output["threading_sha256"]=digest(output)
    return output
