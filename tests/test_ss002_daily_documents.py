from __future__ import annotations

import copy
import hashlib
from datetime import UTC, datetime

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab import ss002_daily_documents as p003

NOW = "2026-10-10T01:00:00Z"
SAMPLE_URL = "https://nsearchives.nseindia.com/corporate/test.html"
SAMPLE_URL_2 = "https://nsearchives.nseindia.com/corporate/test-copy.html"


def _event(
    event_id: str,
    *,
    symbol: str,
    isin: str | None,
    source_url: str | None,
    archive: bool = False,
) -> dict:
    return {
        "announcement_id": event_id,
        "symbol": symbol,
        "isin_at_capture": isin,
        "source_day_ist": "2026-10-05",
        "exchange_published_at_utc": "2026-10-05T12:00:00Z",
        "source_lag_state": "HISTORICAL_BACKFILL_CAPTURED_LATER",
        "mapping_state": (
            "ARCHIVAL_OR_UNMATCHED_AT_CAPTURE" if archive
            else "SYMBOL_IN_EQ_MASTER_AT_CAPTURE"
        ),
        "category_hints_only": ["BUYBACK"],
        "research_attention_state": (
            "ARCHIVAL_OR_UNMATCHED" if archive
            else "CONVERGENT_PRIOR_RESEARCH"
        ),
        "document_intake_state": (
            "NO_APPROVED_CURRENT_ATTACHMENT" if archive or source_url is None
            else "DOCUMENT_INTAKE_READY"
        ),
        "approved_attachment_url": source_url,
        "exact_historical_identity_match": not archive,
    }


def _inbox(monkeypatch: pytest.MonkeyPatch) -> dict:
    events = [
        _event("E1", symbol="A", isin="INE000A01001", source_url=SAMPLE_URL),
        _event("E2", symbol="B", isin="INE000B01001", source_url=SAMPLE_URL_2),
        _event("E3", symbol="ARCHIVE", isin=None, source_url=None, archive=True),
        _event("E4", symbol="NOFILE", isin="INE000C01001", source_url=None),
    ]
    value = {
        "inbox_id": "SS002-P002-v1",
        "source_event_count": 4,
        "document_intake_ready_count": 2,
        "events": events,
        "model_inference_executed": False,
        "economic_relevance_verified": False,
        "return_outcomes_opened": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    value["inbox_sha256"] = digest(value)
    monkeypatch.setattr(p003, "INBOX_SHA256", value["inbox_sha256"])
    monkeypatch.setattr(p003, "EXPECTED_EVENTS", 4)
    monkeypatch.setattr(p003, "EXPECTED_DOCUMENT_EVENTS", 2)
    monkeypatch.setattr(p003, "EXPECTED_CURRENT_SYMBOLS", 2)
    return value


def test_source_identities_and_absent_files_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _inbox(monkeypatch)
    requests, event_states = p003.prepare_document_requests(source)
    assert len(requests) == 2
    assert len(event_states) == 4
    assert set(row["announcement_id"] for row in event_states) == {
        "E1", "E2", "E3", "E4"
    }
    assert sum(row["source_document_state"] == "DOCUMENT_INTAKE_READY" for row in event_states) == 2


def test_html_document_creates_content_addressed_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _inbox(monkeypatch)
    requests, _ = p003.prepare_document_requests(source)
    text = b"<html><body><p>Company announces a buyback.</p></body></html>"
    evidence, extraction = p003.extract_official_attachment(
        requests[0], raw=text, fetched_at_utc=NOW
    )
    assert extraction is not None
    assert evidence["document_id"] == hashlib.sha256(text).hexdigest()
    assert evidence["document_family"] == "HTML"
    assert evidence["extraction_state"] == "READY"
    assert evidence["text_segment_count"] == 1
    assert extraction["segments"][0]["text_sha256"] == hashlib.sha256(
        extraction["segments"][0]["text"].encode()
    ).hexdigest()
    assert extraction["segment_manifest_sha256"] == evidence["segment_manifest_sha256"]


def test_corpus_deduplicates_matching_bytes_without_changing_segment_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _inbox(monkeypatch)
    requests, _ = p003.prepare_document_requests(source)
    raw = b"<html><body>A single official document</body></html>"
    first, extraction = p003.extract_official_attachment(
        requests[0], raw=raw, fetched_at_utc=NOW
    )
    assert extraction is not None
    second, _ = p003.extract_official_attachment(
        requests[1],
        raw=raw,
        fetched_at_utc=NOW,
        canonical_extraction=extraction,
    )
    assert first["document_id"] == second["document_id"]
    assert first["segment_manifest_sha256"] == second["segment_manifest_sha256"]

    corpus = p003.build_daily_document_corpus(source, [first, second])
    assert corpus["source_event_count"] == 4
    assert corpus["current_document_event_count"] == 2
    assert corpus["unique_document_id_count"] == 1
    assert corpus["fetched_url_count"] == 2
    assert corpus["text_ready_url_count"] == 2
    assert corpus["feasibility_pass"] is True
    assert corpus["model_inference_executed"] is False
    assert corpus["market_capitalization_calculated"] is False
    assert corpus["live_capital_allowed"] is False


def test_missing_document_is_a_failure_not_an_invented_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _inbox(monkeypatch)
    requests, _ = p003.prepare_document_requests(source)
    success, _ = p003.extract_official_attachment(
        requests[0], raw=b"<html><body>Readable</body></html>", fetched_at_utc=NOW
    )
    failed, extraction = p003.extract_official_attachment(
        requests[1], raw=None, fetched_at_utc=NOW, error="HTTP 404"
    )
    assert extraction is None
    assert failed["status"] == "FETCH_FAILED"
    corpus = p003.build_daily_document_corpus(source, [success, failed])
    assert corpus["feasibility_pass"] is False
    assert corpus["threshold_passes"]["minimum_official_url_fetch_95pct"] is False


def test_unapproved_host_and_tampered_inbox_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _inbox(monkeypatch)
    tampered = copy.deepcopy(source)
    tampered["events"][0]["approved_attachment_url"] = "https://example.com/offer.pdf"
    with pytest.raises(AlphaContractError, match="contents fail SHA"):
        p003.prepare_document_requests(tampered)

    tampered["inbox_sha256"] = digest(
        {k: v for k, v in tampered.items() if k != "inbox_sha256"}
    )
    monkeypatch.setattr(p003, "INBOX_SHA256", tampered["inbox_sha256"])
    with pytest.raises(AlphaContractError, match="official URL"):
        p003.prepare_document_requests(tampered)


def test_invalid_duplicate_canonical_document_reuse_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _inbox(monkeypatch)
    requests, _ = p003.prepare_document_requests(source)
    raw = b"<html><body>Source A</body></html>"
    first, extracted = p003.extract_official_attachment(
        requests[0], raw=raw, fetched_at_utc=NOW
    )
    assert extracted is not None
    with pytest.raises(AlphaContractError, match="different document"):
        p003.extract_official_attachment(
            requests[1],
            raw=b"<html><body>Source B</body></html>",
            fetched_at_utc=NOW,
            canonical_extraction=extracted,
        )


def test_non_timezone_fetch_timestamp_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _inbox(monkeypatch)
    requests, _ = p003.prepare_document_requests(source)
    with pytest.raises(AlphaContractError, match="timezone aware"):
        p003.extract_official_attachment(
            requests[0],
            raw=b"<html>x</html>",
            fetched_at_utc=datetime.now(UTC).replace(tzinfo=None).isoformat(),
        )
