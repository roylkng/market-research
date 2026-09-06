from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from marketlab.h003_candidates import (
    CANDIDATE_VERSION,
    EXTRACTION_RULE_ID,
    EXTRACTION_RULE_SHA256,
    PARSER_VERSION,
    ClaimCandidate,
    ExtractedPage,
)
from marketlab.h003_review import CandidateCorpus


def _module():
    path = Path("scripts/build_h003_review_package.py")
    spec = importlib.util.spec_from_file_location("build_h003_review_package", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate(raw_sha256: str) -> ClaimCandidate:
    return ClaimCandidate(
        schema_version=2,
        candidate_id="candidate-1",
        rule_id=EXTRACTION_RULE_ID,
        rule_sha256=EXTRACTION_RULE_SHA256,
        candidate_version=CANDIDATE_VERSION,
        source_id="source-1",
        symbol="TEST",
        exchange_published_at_utc="2025-10-16T20:30:00Z",
        attachment_url="https://nsearchives.nseindia.com/test.pdf",
        raw_sha256=raw_sha256,
        parser_version=PARSER_VERSION,
        page_number=1,
        line_start=1,
        line_end=1,
        excerpt="October 16, 2025 Test Limited expects capacity of 10 MW next year.",
        future_markers=("expects",),
        deadline_markers=("next year",),
        quantitative_tokens=("10 MW",),
        domain_markers=("capacity",),
        disposition="UNREVIEWED",
        disposition_reason=None,
    )


def test_publication_date_terms_cover_utc_and_india_calendar_dates():
    module = _module()
    terms = module._publication_date_redaction_terms("2025-10-16T20:30:00Z")
    assert "October 16, 2025" in terms
    assert "October 17, 2025" in terms
    assert "16-Oct-2025" in terms
    assert "17/10/2025" in terms


def test_build_package_redacts_publication_date_from_excerpt_and_context(monkeypatch):
    module = _module()
    raw = b"frozen transcript bytes"
    raw_sha256 = hashlib.sha256(raw).hexdigest()
    candidate = _candidate(raw_sha256)
    corpus = CandidateCorpus(
        report_sha256="report",
        candidate_rule_id=EXTRACTION_RULE_ID,
        candidate_rule_sha256=EXTRACTION_RULE_SHA256,
        source_bundle_sha256="bundle",
        cohort_id="cohort",
        candidate_count=1,
        candidates_by_id={candidate.candidate_id: candidate},
    )
    page = ExtractedPage(
        page_number=1,
        lines=(
            "October 16, 2025 Test Limited expects capacity of 10 MW next year.",
            "October 17, 2025 is the India-local publication calendar date.",
        ),
    )
    monkeypatch.setattr(
        module,
        "_source_pdf_bytes",
        lambda **kwargs: (raw, "candidate-store:test"),
    )
    monkeypatch.setattr(module, "extract_pdf_pages", lambda value: ((page,), page.canonical_text()))

    package, payloads, _ = module.build_package(
        corpus,
        company_names={"TEST": "Test Limited"},
        client=None,
        candidate_store=Path("unused"),
        fetch_attempts=1,
    )
    assert package["blind_payload_count"] == 1
    payload = payloads[0]
    visible = " ".join((payload.redacted_excerpt, *payload.redacted_page_context)).casefold()
    assert "test limited" not in visible
    assert "october 16, 2025" not in visible
    assert "october 17, 2025" not in visible
