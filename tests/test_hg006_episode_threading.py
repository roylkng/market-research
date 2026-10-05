from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg006_episode_threading import (
    deterministic_episode_id,
    validate_episode_manifest,
)


def _extraction(event_id,anchor_value):
    return {
        "document_id":f"doc-{event_id}",
        "event_ids":[event_id],
        "symbol":"AAA",
        "family":"SCHEME_REORGANISATION",
        "transaction_anchors":[
            {
                "anchor_type":"SCHEME_OR_TRANSACTION_NAME",
                "value":anchor_value,
                "evidence_segment_ids":["s1"],
            }
        ],
    }


def test_multiple_events_can_group_only_with_shared_anchor():
    extractions=[_extraction("e1","Scheme X"),_extraction("e2","Scheme X")]
    ids=["e1","e2"]
    manifest={
        "threading_id":"HG006-D003-v1",
        "episodes":[
            {
                "episode_id":deterministic_episode_id(
                    "AAA","SCHEME_REORGANISATION",ids
                ),
                "symbol":"AAA",
                "family":"SCHEME_REORGANISATION",
                "event_ids":ids,
            }
        ],
        "ambiguous_event_ids":[],
        "document_unavailable_event_ids":[],
    }
    result=validate_episode_manifest(extractions=extractions,manifest=manifest)
    assert result["episode_count"]==1
    assert result["episode_assigned_event_count"]==2


def test_time_proximity_cannot_replace_shared_anchor():
    extractions=[_extraction("e1","Scheme X"),_extraction("e2","Scheme Y")]
    ids=["e1","e2"]
    manifest={
        "threading_id":"HG006-D003-v1",
        "episodes":[
            {
                "episode_id":deterministic_episode_id(
                    "AAA","SCHEME_REORGANISATION",ids
                ),
                "symbol":"AAA",
                "family":"SCHEME_REORGANISATION",
                "event_ids":ids,
            }
        ],
        "ambiguous_event_ids":[],
        "document_unavailable_event_ids":[],
    }
    with pytest.raises(AlphaContractError,match="lacks explicit transaction anchor"):
        validate_episode_manifest(extractions=extractions,manifest=manifest)


def test_every_source_event_must_be_accounted_once():
    extractions=[_extraction("e1","Scheme X"),_extraction("e2","Scheme Y")]
    manifest={
        "threading_id":"HG006-D003-v1",
        "episodes":[],
        "ambiguous_event_ids":["e1"],
        "document_unavailable_event_ids":[],
    }
    with pytest.raises(AlphaContractError,match="incomplete event accounting"):
        validate_episode_manifest(extractions=extractions,manifest=manifest)


def test_single_event_episode_still_requires_explicit_anchor():
    extraction=_extraction("e1","Scheme X")
    ids=["e1"]
    manifest={
        "threading_id":"HG006-D003-v1",
        "episodes":[
            {
                "episode_id":deterministic_episode_id(
                    "AAA","SCHEME_REORGANISATION",ids
                ),
                "symbol":"AAA",
                "family":"SCHEME_REORGANISATION",
                "event_ids":ids,
            }
        ],
        "ambiguous_event_ids":[],
        "document_unavailable_event_ids":[],
    }
    result=validate_episode_manifest(extractions=[extraction],manifest=manifest)
    assert result["episode_count"]==1
