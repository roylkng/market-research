from __future__ import annotations

import hashlib

from marketlab.ss002_l001_pilot import FAMILIES, select_pilot


def _segments(document_id: str) -> list[dict]:
    text=f"{document_id} explicit transaction text"
    return [{
        "segment_id":f"{document_id}:pdf:page:0001",
        "text":text,
        "text_sha256":hashlib.sha256(text.encode()).hexdigest(),
    }]


def _fixtures():
    events=[]; manifests=[]; records=[]
    counter=0
    for family in FAMILIES:
        for index in range(7):
            counter+=1
            doc=f"d{counter:03d}"
            url=f"https://nsearchives.nseindia.com/{doc}.pdf"
            sym=f"{family[:3]}{index}"
            event_id=f"e{counter:03d}"
            events.append({
                "announcement_id":event_id,
                "symbol":sym,
                "exchange_published_at_utc":f"2026-10-{30-index:02d}T10:00:00Z",
                "mapping_state":"CURRENT_INVESTABLE_IDENTITY",
                "special_situation_categories":[family],
                "approved_attachment_url":url,
            })
            segs=_segments(doc)
            records.append({
                "document_id":doc,
                "source_url":url,
                "event_ids":[event_id],
                "symbols":[sym],
                "categories":[family],
                "extraction_state":"READY",
                "segment_manifest_sha256":"a"*64,
                "segments":segs,
            })
            manifests.append({
                "document_id":doc,
                "source_url":url,
                "extraction_state":"READY",
            })
    p2={
        "census_id":"SS002-D001-P2-v1",
        "census_sha256":"ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071",
        "events":events,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    d3={
        "corpus_id":"SS002-D003-v1",
        "corpus_sha256":"92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce",
        "document_count":len(manifests),
        "documents":manifests,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    return p2,d3,records


def test_selection_freezes_six_per_family_without_duplicates() -> None:
    p2,d3,records=_fixtures()
    result=select_pilot(p2,d3,records)
    assert result["selected_document_count"]==30
    assert result["family_counts"]=={family:6 for family in sorted(FAMILIES)}
    assert len({row["symbol"] for row in result["rows"]})==30
    assert len({row["document_id"] for row in result["rows"]})==30
    assert result["return_outcomes_opened"] is False
    assert result["portfolio_eligibility_allowed"] is False


def test_selection_uses_latest_events_per_family() -> None:
    p2,d3,records=_fixtures()
    result=select_pilot(p2,d3,records)
    buy=[row for row in result["rows"] if row["pilot_family"]=="BUYBACK"]
    assert len(buy)==6
    assert all(row["exchange_published_at_utc"]!="2026-10-24T10:00:00Z" for row in buy)


def test_prompt_envelopes_are_hash_bound() -> None:
    p2,d3,records=_fixtures()
    result=select_pilot(p2,d3,records)
    assert all(len(row["prompt_sha256"])==64 for row in result["rows"])
    assert all(
        row["prompt_envelope"]["request"]["document_id"]==row["document_id"]
        for row in result["rows"]
    )
