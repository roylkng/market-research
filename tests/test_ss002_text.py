from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_text import (
    build_text_corpus,
    document_requests,
    extract_document_text,
    normalize_text,
    seal_extraction_row,
)


def _doc_id(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_normalize_text_is_deterministic() -> None:
    assert normalize_text("  A\r\nB  \r\n\r\n") == "  A\nB"


def test_plain_text_extraction_produces_hashed_segment_manifest() -> None:
    raw = b"First line\nSecond line"
    doc = hashlib.sha256(raw).hexdigest()
    row = extract_document_text(
        document_id=doc,
        raw=raw,
        d002_family="PLAIN_TEXT",
        source_url="https://nsearchives.nseindia.com/x.txt",
    )
    assert row["extraction_state"] == "READY"
    assert len(row["segments"]) == 1
    assert len(row["segment_manifest_sha256"]) == 64
    assert row["segments"][0]["text"] == "First line\nSecond line"


def test_zip_path_traversal_fails_closed() -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("../bad.txt", "bad")
    raw = out.getvalue()
    doc = hashlib.sha256(raw).hexdigest()
    row = extract_document_text(
        document_id=doc,
        raw=raw,
        d002_family="ZIP_CONTAINER",
        source_url="https://nsearchives.nseindia.com/x.zip",
    )
    assert row["extraction_state"] == "PARSE_FAILED"
    assert "ZIP_UNSAFE_MEMBER_PATH" in row["details"]["error"]


def _synthetic_d002() -> dict:
    documents = []
    for index in range(1539):
        doc_id = _doc_id(f"doc-{index}")
        documents.append(
            {
                "status": "READY",
                "document_id": doc_id,
                "raw_sha256": doc_id,
                "source_url": f"https://nsearchives.nseindia.com/{index}.pdf",
                "document_family": "PDF",
                "event_ids": [f"E{index:04d}"],
                "symbols": [f"S{index % 540:04d}"],
                "categories": ["BUYBACK"],
            }
        )
    return {
        "corpus_id": "SS002-D002-v1",
        "corpus_sha256": (
            "eab922954ef20a12a7635107722b4e800b59cfa56ff0659da42afb3fc22218f9"
        ),
        "unique_document_id_count": 1539,
        "documents": documents,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_document_requests_deduplicate_by_document_id() -> None:
    corpus = _synthetic_d002()
    duplicate = dict(corpus["documents"][0])
    duplicate["source_url"] = "https://archives.nseindia.com/duplicate.pdf"
    corpus["documents"].append(duplicate)
    requests = document_requests(corpus)
    assert len(requests) == 1539
    first = next(row for row in requests if row["document_id"] == duplicate["document_id"])
    assert len(first["source_urls"]) == 2


def test_text_corpus_requires_all_documents_and_preserves_research_only_state() -> None:
    corpus = _synthetic_d002()
    rows = []
    for request in document_requests(corpus):
        text = "x"
        segment = {
            "segment_id": f"{request['document_id']}:pdf:page:0001",
            "kind": "PDF_PAGE",
            "locator": {"page_number": 1},
            "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "utf8_byte_count": 1,
            "char_count": 1,
        }
        rows.append(
            seal_extraction_row(
                {
                    "document_id": request["document_id"],
                    "source_url": request["source_urls"][0],
                    "d002_family": "PDF",
                    "extraction_state": "READY",
                    "details": {"page_count": 1},
                    "segments": [segment],
                    "hash_reproduced": True,
                    "attempts": [],
                    "text_artifact_path": f"documents/{request['document_id']}.json",
                }
            )
        )
    result = build_text_corpus(
        d002_corpus=corpus,
        extraction_rows=rows,
        captured_at_utc="2026-10-04T14:00:00Z",
    )
    assert result["document_count"] == 1539
    assert result["hash_reproduced_ratio"] == 1.0
    assert result["pdf_text_ready_ratio"] == 1.0
    assert result["feasibility_pass"] is True
    assert result["llm_inference_executed"] is False
    assert result["portfolio_eligibility_allowed"] is False


def test_text_corpus_rejects_tampered_segment_manifest() -> None:
    corpus = _synthetic_d002()
    requests = document_requests(corpus)
    rows = []
    for request in requests:
        row = seal_extraction_row(
            {
                "document_id": request["document_id"],
                "source_url": request["source_urls"][0],
                "d002_family": "PDF",
                "extraction_state": "NO_EXTRACTABLE_TEXT",
                "details": {},
                "segments": [],
                "hash_reproduced": True,
                "attempts": [],
            }
        )
        rows.append(row)
    rows[0]["segment_manifest_sha256"] = "0" * 64
    with pytest.raises(AlphaContractError, match="segment manifest SHA mismatch"):
        build_text_corpus(
            d002_corpus=corpus,
            extraction_rows=rows,
            captured_at_utc="2026-10-04T14:00:00Z",
        )


def test_sealed_failure_has_deterministic_manifest() -> None:
    row = seal_extraction_row(
        {
            "document_id": "a" * 64,
            "source_url": None,
            "d002_family": "PDF",
            "extraction_state": "HASH_REPRODUCTION_FAILED",
            "details": {"error": "no source reproduced"},
            "segments": [],
            "hash_reproduced": False,
            "attempts": [],
        }
    )
    encoded = json.dumps(row, sort_keys=True)
    assert "segment_manifest_sha256" in encoded
