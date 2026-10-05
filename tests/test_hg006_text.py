from __future__ import annotations

import hashlib

from marketlab.hg006_text import (
    build_historical_text_corpus,
    document_requests,
    extraction_index_row,
)
from marketlab.ss002_text import seal_extraction_row


def _d001a() -> dict:
    return {
        "corpus_id": "HG006-D001A-P1-v1",
        "feasibility_pass": True,
        "unique_document_id_count": 2,
        "selected_families": [
            "PREFERENTIAL_WARRANT",
            "SCHEME_REORGANISATION",
        ],
        "documents": [
            {
                "status": "READY",
                "document_id": "a" * 64,
                "source_url": "https://nsearchives.nseindia.com/a.pdf",
                "shard_id": 5,
                "document_family": "PDF",
                "families": ["SCHEME_REORGANISATION"],
                "event_ids": ["E1"],
                "chronology_ids": ["C1"],
                "symbols": ["AAA"],
            },
            {
                "status": "READY",
                "document_id": "a" * 64,
                "source_url": "https://nsearchives.nseindia.com/a-copy.pdf",
                "shard_id": 2,
                "document_family": "PDF",
                "families": ["SCHEME_REORGANISATION"],
                "event_ids": ["E2"],
                "chronology_ids": ["C1"],
                "symbols": ["AAA"],
            },
            {
                "status": "READY",
                "document_id": "b" * 64,
                "source_url": "https://nsearchives.nseindia.com/b.pdf",
                "shard_id": 7,
                "document_family": "PDF",
                "families": ["PREFERENTIAL_WARRANT"],
                "event_ids": ["E3"],
                "chronology_ids": ["C2"],
                "symbols": ["BBB"],
            },
        ],
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "corpus_sha256": "source-sha",
    }


def _ready_extraction(document_id: str, segment_id: str) -> dict:
    text = "Explicit transaction text."
    row = {
        "document_id": document_id,
        "source_url": "https://nsearchives.nseindia.com/x.pdf",
        "d002_family": "PDF",
        "extraction_state": "READY",
        "details": {"page_count": 1},
        "segments": [
            {
                "segment_id": segment_id,
                "kind": "PDF_PAGE",
                "locator": {"page_number": 1},
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "utf8_byte_count": len(text.encode()),
                "char_count": len(text),
            }
        ],
        "hash_reproduced": True,
    }
    return seal_extraction_row(row)


def test_document_owner_is_minimum_source_shard() -> None:
    requests = document_requests(_d001a())
    rows = {row["document_id"]: row for row in requests}
    assert rows["a" * 64]["owner_shard"] == 2
    assert rows["a" * 64]["available_shards"] == [2, 5]
    assert rows["a" * 64]["event_ids"] == ["E1", "E2"]
    assert rows["b" * 64]["owner_shard"] == 7


def test_ready_extraction_index_and_combined_corpus_pass() -> None:
    source = _d001a()
    requests = document_requests(source)
    indexes = []
    for index, request in enumerate(requests, start=1):
        extraction = _ready_extraction(
            request["document_id"],
            f"{request['document_id']}:pdf:page:{index:04d}",
        )
        indexes.append(
            extraction_index_row(
                extraction,
                request=request,
                text_artifact_path=f"documents/{request['document_id']}.json",
            )
        )

    corpus = build_historical_text_corpus(
        d001a_corpus=source,
        index_rows=indexes,
        captured_at_utc="2026-10-05T12:00:00Z",
    )
    assert corpus["document_count"] == 2
    assert corpus["hash_reproduced_count"] == 2
    assert corpus["text_ready_document_count"] == 2
    assert corpus["segment_count"] == 2
    assert corpus["feasibility_pass"] is True
    assert corpus["llm_inference_executed"] is False


def test_nonready_text_document_fails_80pct_gate() -> None:
    source = _d001a()
    requests = document_requests(source)
    indexes = []
    for request in requests:
        if request["document_id"] == "a" * 64:
            extraction = _ready_extraction(
                request["document_id"],
                f"{request['document_id']}:pdf:page:0001",
            )
        else:
            extraction = seal_extraction_row(
                {
                    "document_id": request["document_id"],
                    "source_url": request["source_urls"][0],
                    "d002_family": "PDF",
                    "extraction_state": "NO_EXTRACTABLE_TEXT",
                    "details": {"page_count": 1},
                    "segments": [],
                    "hash_reproduced": True,
                }
            )
        indexes.append(
            extraction_index_row(
                extraction,
                request=request,
                text_artifact_path=f"documents/{request['document_id']}.json",
            )
        )

    corpus = build_historical_text_corpus(
        d001a_corpus=source,
        index_rows=indexes,
        captured_at_utc="2026-10-05T12:00:00Z",
    )
    assert corpus["text_ready_ratio_of_reproduced"] == 0.5
    assert corpus["feasibility_pass"] is False
