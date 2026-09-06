from __future__ import annotations

from marketlab.h003_candidates import ClaimCandidate
from marketlab.h003_review import build_blind_review_payload


def _candidate(*, line_start: int = 3, line_end: int = 3) -> ClaimCandidate:
    return ClaimCandidate(
        schema_version=2,
        candidate_id="cross-line-candidate",
        rule_id="H003-E002",
        rule_sha256="5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2",
        candidate_version="h003_future_commitment_candidate_v2",
        source_id="source-cross-line",
        symbol="TEST",
        exchange_published_at_utc="2026-08-01T10:00:00Z",
        attachment_url="https://nsearchives.nseindia.com/test.pdf",
        raw_sha256="a" * 64,
        parser_version="h003_pdf_text_v1",
        page_number=1,
        line_start=line_start,
        line_end=line_end,
        excerpt="We expect revenue growth of 15% next year.",
        future_markers=("we expect",),
        deadline_markers=("next year",),
        quantitative_tokens=("15%",),
        domain_markers=("revenue", "growth"),
        disposition="UNREVIEWED",
        disposition_reason=None,
    )


def test_blind_context_redacts_company_name_split_across_adjacent_pdf_lines():
    candidate = _candidate()
    page_lines = (
        "Our portfolio includes Tata",
        "Steel Kalinganagar and other facilities.",
        "We expect revenue growth of 15% next year.",
    )
    payload = build_blind_review_payload(
        candidate,
        page_lines=page_lines,
        redaction_terms=("Tata Steel", "Tata Steel Limited"),
        context_radius_lines=3,
    )
    visible = " ".join(payload.redacted_page_context).casefold()
    assert "tata steel" not in visible
    assert payload.redacted_page_context[0].endswith("[COMPANY]")
    assert payload.redacted_page_context[1].startswith("[COMPANY]")
    assert len(payload.redacted_page_context) == len(page_lines)
    assert payload.line_start == 3
    assert payload.line_end == 3


def test_cross_line_redaction_handles_three_token_term_at_different_split_point():
    candidate = _candidate()
    page_lines = (
        "We work with Alpha Beta",
        "Gamma Holdings across the market.",
        "We expect revenue growth of 15% next year.",
    )
    payload = build_blind_review_payload(
        candidate,
        page_lines=page_lines,
        redaction_terms=("Alpha Beta Gamma",),
        context_radius_lines=3,
    )
    visible = " ".join(payload.redacted_page_context).casefold()
    assert "alpha beta gamma" not in visible
    assert payload.redacted_page_context[0].endswith("[COMPANY]")
    assert payload.redacted_page_context[1].startswith("[COMPANY]")
