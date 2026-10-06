from __future__ import annotations

import hashlib

from marketlab.hg006_evidence_pack import (
    build_stage_evidence_pack,
    phrase_hits,
)


def _selection() -> dict:
    rows=[]
    for i in range(300):
        family="PREFERENTIAL_WARRANT" if i<150 else "SCHEME_REORGANISATION"
        rows.append({
            "chronology_id":f"C{i:03d}",
            "symbol":f"S{i:03d}",
            "family":family,
            "announcement_ids":[f"E{i:03d}"],
            "event_count":1,
        })
    return {
        "selection_id":"HG006-S001-v1",
        "selection_sha256":"4bc9659c1111f0694bbbec8754b6193116871367b78f126c39e09bc329c961f5",
        "selected_chronology_count":300,
        "rows":rows,
        "historical_terminal_labels_opened":False,
        "completion_probabilities_assigned":False,
        "expected_returns_calculated":False,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }


def _d001() -> dict:
    return {
        "census_id":"HG006-D001-v1",
        "census_sha256":"a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5",
        "events":[
            {
                "announcement_id":f"E{i:03d}",
                "exchange_published_at_utc":f"2024-01-{(i%28)+1:02d}T10:00:00Z",
            }
            for i in range(300)
        ],
        "completion_probabilities_assigned":False,
        "return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }


def _d001b() -> dict:
    return {
        "corpus_id":"HG006-D001B-v1",
        "corpus_sha256":"4f841df6599d4836b1a7798439f69eb889690da19942cf48f41d4752b57d4ce9",
        "historical_terminal_labels_opened":False,
        "completion_probabilities_assigned":False,
        "return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }


def _segment(doc:str,page:int,text:str)->dict:
    return {
        "segment_id":f"{doc}:pdf:page:{page:04d}",
        "kind":"PDF_PAGE",
        "locator":{"page_number":page},
        "text":text,
        "text_sha256":hashlib.sha256(text.encode()).hexdigest(),
    }


def _text_rows() -> list[dict]:
    rows=[]
    for i in range(298):
        family="PREFERENTIAL_WARRANT" if i<150 else "SCHEME_REORGANISATION"
        doc=hashlib.sha256(f"D{i}".encode()).hexdigest()
        text=(
            "Board of Directors approved preferential allotment of warrants."
            if family=="PREFERENTIAL_WARRANT"
            else "Board of Directors approved a scheme of arrangement."
        )
        rows.append({
            "document_id":doc,
            "chronology_ids":[f"C{i:03d}"],
            "event_ids":[f"E{i:03d}"],
            "symbols":[f"S{i:03d}"],
            "families":[family],
            "extraction_state":"READY",
            "segment_manifest_sha256":"a"*64,
            "segments":[
                _segment(doc,1,"Cover page"),
                _segment(doc,2,text),
                _segment(doc,3,"The transaction has become effective."),
            ],
        })
    return rows


def test_phrase_hits_identifies_terminal_and_anchor_groups() -> None:
    hits=phrase_hits(
        "The NCLT sanctioned the Scheme of Arrangement and it became effective."
    )
    assert hits["terminal_match"] is True
    assert "TERMINAL" in hits["groups"]
    assert "APPROVAL_STAGE" in hits["groups"]
    assert "SCHEME_ANCHOR" in hits["groups"]


def test_stage_evidence_pack_preserves_two_text_unavailable() -> None:
    result=build_stage_evidence_pack(
        selection=_selection(),
        d001=_d001(),
        d001b_summary=_d001b(),
        text_rows=_text_rows(),
    )
    assert result["chronology_count"]==300
    assert result["state_counts"]["EVIDENCE_READY"]==298
    assert result["state_counts"]["TEXT_UNAVAILABLE"]==2
    assert len(result["text_unavailable_chronology_ids"])==2
    assert result["feasibility_pass"] is True
    assert result["historical_terminal_labels_opened"] is False
    assert result["completion_probabilities_assigned"] is False


def test_terminal_segments_are_never_dropped() -> None:
    rows=_text_rows()
    row=rows[0]
    doc=row["document_id"]
    row["segments"]=[
        _segment(doc,1,"cover"),
        _segment(doc,2,"The Board of Directors approved the issue."),
        _segment(doc,3,"filler"),
        _segment(doc,4,"The warrants were cancelled."),
        _segment(doc,5,"The remaining allotment was completed."),
        _segment(doc,6,"last"),
    ]
    result=build_stage_evidence_pack(
        selection=_selection(),
        d001=_d001(),
        d001b_summary=_d001b(),
        text_rows=rows,
    )
    first=result["chronologies"][0]["retained_documents"][0]
    texts=[seg["text"] for seg in first["selected_segments"]]
    assert "The warrants were cancelled." in texts
    assert "The remaining allotment was completed." in texts
