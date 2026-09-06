from __future__ import annotations

import io
from datetime import UTC, datetime

import pypdf
from pypdf import PdfWriter

from marketlab.h003_candidates import (
    CANDIDATE_VERSION,
    DECISION_TIMESTAMP_UTC,
    EXPECTED_SOURCE_COUNT,
    EXTRACTION_RULE_ID,
    ExtractedPage,
    FrozenTranscriptSource,
    H003CandidateStore,
    build_report,
    deterministic_sample,
    extract_source,
    generate_candidates,
    load_and_validate_extraction_rule,
    load_frozen_transcript_sources,
)


def _source(source_id: str = "source-1") -> FrozenTranscriptSource:
    return FrozenTranscriptSource(
        source_id=source_id,
        symbol="TEST",
        seq_id="1",
        exchange_published_at_utc="2026-08-01T10:00:00Z",
        attachment_url="https://nsearchives.nseindia.com/test.pdf",
        discovery_row_sha256="a" * 64,
    )


def test_frozen_extraction_rule_validates():
    document = load_and_validate_extraction_rule("registry/h003_extraction_rule.yaml")
    assert document["id"] == EXTRACTION_RULE_ID
    assert document["candidate_rule"]["version"] == CANDIDATE_VERSION
    assert document["live_capital"] is False


def test_candidate_is_deterministic_and_keeps_page_line_locator():
    pages = (
        ExtractedPage(
            page_number=7,
            lines=(
                "Capacity expansion update",
                "We expect to commission 2 new plants by March 2027.",
                "The projects are progressing as planned.",
            ),
        ),
    )
    first = generate_candidates(_source(), raw_sha256="b" * 64, pages=pages)
    second = generate_candidates(_source(), raw_sha256="b" * 64, pages=pages)
    assert first == second
    assert len(first) >= 1
    candidate = first[0]
    assert candidate.page_number == 7
    assert candidate.line_start >= 1
    assert candidate.line_end <= 3
    assert candidate.disposition == "UNREVIEWED"
    assert candidate.candidate_id == second[0].candidate_id
    assert "we expect" in candidate.future_markers
    assert candidate.quantitative_tokens or candidate.deadline_markers


def test_safe_harbor_boilerplate_is_not_a_candidate():
    pages = (
        ExtractedPage(
            page_number=1,
            lines=(
                "Safe Harbor and forward-looking statements",
                "We expect revenue to grow 20% next year but actual results may differ materially.",
            ),
        ),
    )
    assert generate_candidates(_source(), raw_sha256="c" * 64, pages=pages) == ()


def test_blank_pdf_is_explicit_no_text_not_zero_candidate_success(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = io.BytesIO()
    writer.write(buffer)
    record = extract_source(
        _source(), buffer.getvalue(), store=H003CandidateStore(tmp_path)
    )
    assert record.status == "NO_TEXT"
    assert record.failure_reason
    assert record.candidate_count == 0
    assert record.raw_sha256
    assert record.text_sha256


def test_invalid_pdf_is_explicit_parse_error(tmp_path):
    record = extract_source(
        _source(), b"not a pdf", store=H003CandidateStore(tmp_path)
    )
    assert record.status == "PARSE_ERROR"
    assert record.failure_reason
    assert record.raw_sha256
    assert record.candidate_count == 0


def test_content_addressed_store_is_idempotent(tmp_path):
    store = H003CandidateStore(tmp_path)
    raw_path_1 = store.retain_raw_pdf(b"same-pdf-bytes")
    raw_path_2 = store.retain_raw_pdf(b"same-pdf-bytes")
    text_hash_1, text_path_1 = store.retain_text("same extracted text")
    text_hash_2, text_path_2 = store.retain_text("same extracted text")
    assert raw_path_1 == raw_path_2
    assert text_hash_1 == text_hash_2
    assert text_path_1 == text_path_2


def test_real_frozen_source_bundle_has_exact_794_pre_cutoff_sources():
    sources = load_frozen_transcript_sources(
        "research/prospective/h003/FY27-Q2-2026-09-06/source-coverage-v1.json"
    )
    assert len(sources) == EXPECTED_SOURCE_COUNT
    cutoff = datetime.fromisoformat(DECISION_TIMESTAMP_UTC).astimezone(UTC)
    assert all(
        datetime.fromisoformat(source.exchange_published_at_utc).astimezone(UTC) <= cutoff
        for source in sources
    )
    assert len({source.source_id for source in sources}) == EXPECTED_SOURCE_COUNT


def test_deterministic_sample_spans_the_frozen_source_order():
    sources = tuple(_source(f"source-{index}") for index in range(10))
    sample = deterministic_sample(sources, 4)
    assert [item.source_id for item in sample] == [
        "source-0",
        "source-3",
        "source-6",
        "source-9",
    ]


def test_partial_report_cannot_be_frozen(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = io.BytesIO()
    writer.write(buffer)
    record = extract_source(
        _source(), buffer.getvalue(), store=H003CandidateStore(tmp_path)
    )
    report = build_report([record], generated_at=datetime(2026, 9, 7, tzinfo=UTC))
    assert report.complete is False
    assert report.processed_source_count == 1
    assert report.freeze_blockers
    assert report.source_status_counts == {"NO_TEXT": 1}


def test_parser_version_is_exactly_pinned():
    assert pypdf.__version__ == "6.17.0"


def test_future_marker_in_neighbor_line_does_not_promote_current_fact():
    pages = (
        ExtractedPage(
            page_number=1,
            lines=(
                "ARPU for the quarter came in at Rs. 195.1.",
                "We expect this to taper down as well.",
            ),
        ),
    )
    assert generate_candidates(_source(), raw_sha256="d" * 64, pages=pages) == ()


def test_generic_future_without_commitment_domain_is_not_candidate():
    pages = (
        ExtractedPage(
            page_number=1,
            lines=("We expect this to improve over the next two quarters.",),
        ),
    )
    assert generate_candidates(_source(), raw_sha256="e" * 64, pages=pages) == ()


def test_one_anchor_line_yields_one_candidate_not_overlapping_duplicates():
    pages = (
        ExtractedPage(
            page_number=1,
            lines=(
                "We expect revenue growth of 15% next year.",
                "Current revenue grew 8% this quarter.",
                "Historic margin was 12%.",
            ),
        ),
    )
    candidates = generate_candidates(_source(), raw_sha256="f" * 64, pages=pages)
    assert len(candidates) == 1
    assert candidates[0].line_start == 1
    assert candidates[0].line_end == 2
    assert "revenue" in candidates[0].domain_markers
