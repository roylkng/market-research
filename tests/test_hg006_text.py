from __future__ import annotations

import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg006_text import (
    build_selected_text_corpus,
    extract_verified_document,
    selected_document_requests,
    shard_for_document_id,
)


def _selection() -> dict:
    rows=[]
    for family in ("PREFERENTIAL_WARRANT","SCHEME_REORGANISATION"):
        for i in range(150):
            cid=f"{family}-{i:03d}"
            rows.append({
                "chronology_id":cid,
                "symbol":f"S{i:03d}",
                "family":family,
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


def _source() -> dict:
    documents=[]
    for family in ("PREFERENTIAL_WARRANT","SCHEME_REORGANISATION"):
        for i in range(150):
            cid=f"{family}-{i:03d}"
            raw=f"doc-{cid}".encode()
            doc=hashlib.sha256(raw).hexdigest()
            documents.append({
                "status":"READY",
                "document_id":doc,
                "raw_sha256":doc,
                "source_url":f"https://nsearchives.nseindia.com/{doc}.pdf",
                "document_family":"PDF",
                "event_ids":[f"E-{cid}"],
                "chronology_ids":[cid],
                "symbols":[f"S{i:03d}"],
                "families":[family],
            })
    return {
        "corpus_id":"HG006-D001A-P1-v1",
        "corpus_sha256":"3d47f24a5cbd4f551eae577ad0ed32fde7f5f15567ce775f60c0bb51ee9989dd",
        "documents":documents,
        "historical_terminal_labels_opened":False,
        "completion_probabilities_assigned":False,
        "expected_returns_calculated":False,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }


def test_selected_requests_cover_exact_frozen_cohort() -> None:
    requests=selected_document_requests(_selection(),_source())
    assert len(requests)==300
    chron={cid for row in requests for cid in row["chronology_ids"]}
    assert len(chron)==300
    assert all(0<=row["shard_id"]<8 for row in requests)


def test_shard_requires_sha256_hex() -> None:
    assert 0<=shard_for_document_id("a"*64)<8
    with pytest.raises(AlphaContractError):
        shard_for_document_id("not-a-hash")


def test_verified_document_fails_closed_when_no_hash_match() -> None:
    request=selected_document_requests(_selection(),_source())[0]
    row=extract_verified_document(
        request,
        raw=None,
        source_url=None,
        attempts=[{"source_url":request["source_urls"][0],"status":"HASH_MISMATCH"}],
    )
    assert row["hash_reproduced"] is False
    assert row["extraction_state"]=="HASH_REPRODUCTION_FAILED"
    assert row["segments"]==[]


def test_selected_text_corpus_passes_with_deterministic_segments(monkeypatch) -> None:
    selection=_selection()
    source=_source()
    requests=selected_document_requests(selection,source)

    def fake_extract(*,document_id,raw,d002_family,source_url):
        text="explicit historical evidence"
        segment={
            "segment_id":f"{document_id}:pdf:page:0001",
            "kind":"PDF_PAGE",
            "locator":{"page_number":1},
            "text":text,
            "text_sha256":hashlib.sha256(text.encode()).hexdigest(),
            "utf8_byte_count":len(text.encode()),
            "char_count":len(text),
        }
        return {
            "document_id":document_id,
            "source_url":source_url,
            "d002_family":d002_family,
            "extraction_state":"READY",
            "details":{"page_count":1},
            "segments":[segment],
            "segment_manifest_sha256":"f"*64,
        }

    monkeypatch.setattr("marketlab.hg006_text.extract_document_text",fake_extract)
    rows=[]
    by_doc={row["document_id"]:row for row in source["documents"]}
    for request in requests:
        raw=next(
            f"doc-{cid}".encode()
            for cid in request["chronology_ids"]
            if hashlib.sha256(f"doc-{cid}".encode()).hexdigest()==request["document_id"]
        )
        rows.append(extract_verified_document(
            request,
            raw=raw,
            source_url=by_doc[request["document_id"]]["source_url"],
            attempts=[],
        ))
    result=build_selected_text_corpus(
        selection=selection,
        source_corpus=source,
        extraction_rows=rows,
        captured_at_utc="2026-10-06T04:00:00Z",
    )
    assert result["selected_chronology_count"]==300
    assert result["selected_document_count"]==300
    assert result["chronology_text_ready_ratio"]==1.0
    assert result["feasibility_pass"] is True
    assert result["historical_terminal_labels_opened"] is False
