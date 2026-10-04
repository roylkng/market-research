from __future__ import annotations

from marketlab.ss002_attachments import (
    AttachmentRequest,
    attachment_evidence,
    build_attachment_corpus,
    build_attachment_requests,
    detect_document_family,
)


def _census() -> dict:
    events = []
    for index in range(1666):
        ready = index < 1659
        url = (
            f"https://nsearchives.nseindia.com/corporate/ATTACH_{index % 3}.pdf"
            if ready
            else None
        )
        events.append(
            {
                "announcement_id": f"E{index:04d}",
                "symbol": f"S{index % 540:04d}",
                "mapping_state": "CURRENT_INVESTABLE_IDENTITY",
                "attachment_state": "READY" if ready else "ABSENT",
                "approved_attachment_url": url,
                "special_situation_categories": ["BUYBACK"],
            }
        )
    return {
        "census_id": "SS002-D001-P2-v1",
        "census_sha256": (
            "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"
        ),
        "current_investable_event_count": 1666,
        "current_attachment_ready_count": 1659,
        "events": events,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_requests_deduplicate_urls_and_retain_all_current_events() -> None:
    requests, states = build_attachment_requests(_census())
    assert len(requests) == 3
    assert len(states) == 1666
    assert sum(row["attachment_state"] == "APPROVED_URL" for row in states) == 1659
    assert sum(row["attachment_state"] == "NO_ATTACHMENT" for row in states) == 7
    assert sum(len(request.event_ids) for request in requests) == 1659


def test_document_family_detection_prefers_bytes() -> None:
    assert detect_document_family(b"%PDF-1.7\nbody", "https://nsearchives.nseindia.com/x.bin") == "PDF"
    assert detect_document_family(b"PK\x03\x04rest", "https://nsearchives.nseindia.com/x.pdf") == "ZIP_CONTAINER"
    assert detect_document_family(b"<html><body>x</body></html>", "https://nsearchives.nseindia.com/x") == "HTML"
    assert detect_document_family(b"<?xml version='1.0'?><x/>", "https://nsearchives.nseindia.com/x") == "XML_OR_XHTML"


def test_corpus_counts_document_dedup_and_keeps_portfolio_disabled() -> None:
    census = _census()
    requests, _ = build_attachment_requests(census)
    evidence = [
        attachment_evidence(
            request,
            raw=b"%PDF-1.7\n" + request.source_url.encode(),
            error=None,
        )
        for request in requests
    ]
    corpus = build_attachment_corpus(
        census,
        evidence,
        captured_at_utc="2026-10-04T13:00:00Z",
    )
    assert corpus["unique_approved_url_count"] == 3
    assert corpus["ready_url_count"] == 3
    assert corpus["ready_event_count"] == 1659
    assert corpus["feasibility_pass"] is True
    assert corpus["portfolio_eligibility_allowed"] is False
    assert corpus["live_capital_allowed"] is False


def test_fetch_failure_is_explicit_and_not_replaced() -> None:
    request = AttachmentRequest(
        source_url="https://nsearchives.nseindia.com/corporate/x.pdf",
        event_ids=("E1",),
        symbols=("AAA",),
        categories=("BUYBACK",),
    )
    row = attachment_evidence(request, raw=None, error="HTTP 404")
    assert row["status"] == "FETCH_FAILED"
    assert row["document_id"] is None
    assert row["error"] == "HTTP 404"
