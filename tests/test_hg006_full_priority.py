from __future__ import annotations

import hashlib

from marketlab import hg006_full_priority as fp


def _ready_doc(
    document_id: str,
    *,
    url: str,
    chronology_id: str = "C1",
    event_id: str = "E1",
) -> dict:
    return {
        "status": "READY",
        "document_id": document_id,
        "raw_sha256": document_id,
        "source_url": url,
        "document_family": "PDF",
        "chronology_ids": [chronology_id],
        "event_ids": [event_id],
        "symbols": ["TEST"],
        "families": ["PREFERENTIAL_WARRANT"],
    }


def test_group_ready_documents_deduplicates_same_content_across_urls() -> None:
    doc_id = "a" * 64
    rows = [
        _ready_doc(
            doc_id,
            url="https://nsearchives.nseindia.com/corporate/a.pdf",
        ),
        _ready_doc(
            doc_id,
            url="https://archives.nseindia.com/corporate/b.pdf",
        ),
    ]
    grouped = fp.group_ready_documents(rows)
    assert len(grouped) == 1
    assert grouped[0]["document_id"] == doc_id
    assert grouped[0]["source_urls"] == [
        "https://archives.nseindia.com/corporate/b.pdf",
        "https://nsearchives.nseindia.com/corporate/a.pdf",
    ]


def test_shard_is_document_identity_only() -> None:
    doc_id = hashlib.sha256(b"same document").hexdigest()
    assert fp.shard_for_document_id(doc_id) == int(doc_id[:8], 16) % fp.SHARD_COUNT


def test_full_text_corpus_preserves_no_attachment_state(monkeypatch) -> None:
    monkeypatch.setattr(fp, "EXPECTED_CHRONOLOGY_COUNT", 2)
    monkeypatch.setattr(fp, "EXPECTED_ATTACHMENT_READY_CHRONOLOGY_COUNT", 1)
    monkeypatch.setattr(fp, "EXPECTED_DOCUMENT_COUNT", 1)

    document_id = hashlib.sha256(b"document").hexdigest()
    source = {
        "corpus_id": fp.EXPECTED_SOURCE_CORPUS_ID,
        "corpus_sha256": fp.EXPECTED_SOURCE_CORPUS_SHA,
        "selected_chronology_count": 2,
        "unique_document_id_count": 1,
        "attachment_ready_chronology_count": 1,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "chronologies": [
            {
                "chronology_id": "C1",
                "source_state": "READY_DOCUMENT_EVIDENCE",
            },
            {
                "chronology_id": "C2",
                "source_state": "NO_APPROVED_ATTACHMENT",
            },
        ],
        "documents": [
            _ready_doc(
                document_id,
                url="https://nsearchives.nseindia.com/corporate/a.pdf",
                chronology_id="C1",
            )
        ],
    }
    text = "Board approved preferential allotment."
    segment = {
        "segment_id": "seg1",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
    extraction = [
        {
            **fp.group_ready_documents(source["documents"])[0],
            "hash_reproduced": True,
            "selected_source_url": (
                "https://nsearchives.nseindia.com/corporate/a.pdf"
            ),
            "extraction_state": "READY",
            "segments": [segment],
            "segment_manifest_sha256": "b" * 64,
        }
    ]

    result = fp.build_full_text_corpus(
        source_corpus=source,
        extraction_rows=extraction,
        captured_at_utc="2026-10-07T12:00:00Z",
    )
    assert result["chronology_state_counts"]["TEXT_READY"] == 1
    assert result["chronology_state_counts"]["NO_APPROVED_ATTACHMENT"] == 1
    assert result["feasibility_pass"] is True
    assert result["portfolio_eligibility_allowed"] is False
