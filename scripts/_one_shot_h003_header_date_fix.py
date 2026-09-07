from __future__ import annotations

from pathlib import Path


BUILD = Path("scripts/build_h003_review_package.py")
TEST = Path("tests/test_h003_review_source_header_date_redaction.py")


def patch_build_script() -> None:
    text = BUILD.read_text(encoding="utf-8")
    anchor = "def _load_company_names(path: Path) -> dict[str, str]:\n"
    helper = r'''_STANDALONE_SOURCE_DATE_PATTERNS = (
    re.compile(r"^(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}$", re.IGNORECASE),
    re.compile(r"^\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?),?\s+\d{4}$", re.IGNORECASE),
    re.compile(r"^\d{1,2}[-/.](?:\d{1,2}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-/.]\d{2,4}$", re.IGNORECASE),
    re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$"),
)
_PAGE_HEADER_MARKER = re.compile(r"^Page\s+\d+\s+of\s+\d+$", re.IGNORECASE)


def _page_header_date_redaction_terms(page_lines: tuple[str, ...]) -> tuple[str, ...]:
    """Return standalone source-date strings found in the PDF page header.

    Prefer an explicit ``Page X of Y`` boundary. When a PDF has no such marker,
    inspect only the first two non-empty lines. This keeps body/claim dates out
    of the metadata redaction set while removing transcript header dates.
    """

    nonempty = [line.strip() for line in page_lines if line.strip()]
    marker_index = next(
        (index for index, line in enumerate(nonempty[:10]) if _PAGE_HEADER_MARKER.fullmatch(line)),
        None,
    )
    header_lines = nonempty[:marker_index] if marker_index is not None else nonempty[:2]
    terms = {
        line
        for line in header_lines
        if any(pattern.fullmatch(line) for pattern in _STANDALONE_SOURCE_DATE_PATTERNS)
    }
    return tuple(sorted(terms, key=len, reverse=True))


'''
    if text.count(anchor) != 1:
        raise SystemExit(f"unexpected helper anchor count: {text.count(anchor)}")
    text = text.replace(anchor, helper + anchor)

    old = '''            payload = build_blind_review_payload(
                candidate,
                page_lines=page_lines,
                redaction_terms=redaction_terms,
                context_radius_lines=3,
            )
'''
    new = '''            candidate_redaction_terms = tuple(
                {
                    *redaction_terms,
                    *_page_header_date_redaction_terms(page_lines),
                }
            )
            payload = build_blind_review_payload(
                candidate,
                page_lines=page_lines,
                redaction_terms=candidate_redaction_terms,
                context_radius_lines=3,
            )
'''
    if text.count(old) != 1:
        raise SystemExit(f"unexpected payload anchor count: {text.count(old)}")
    BUILD.write_text(text.replace(old, new), encoding="utf-8")


def write_test() -> None:
    TEST.write_text(
        r'''from __future__ import annotations

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
        candidate_id="candidate-header-date",
        rule_id=EXTRACTION_RULE_ID,
        rule_sha256=EXTRACTION_RULE_SHA256,
        candidate_version=CANDIDATE_VERSION,
        source_id="source-header-date",
        symbol="TEST",
        exchange_published_at_utc="2026-04-17T10:00:00Z",
        attachment_url="https://nsearchives.nseindia.com/test.pdf",
        raw_sha256=raw_sha256,
        parser_version=PARSER_VERSION,
        page_number=5,
        line_start=4,
        line_end=4,
        excerpt="We expect capacity of 10 MW by April 30, 2027.",
        future_markers=("we expect",),
        deadline_markers=("by",),
        quantitative_tokens=("10 MW", "April 30, 2027"),
        domain_markers=("capacity",),
        disposition="UNREVIEWED",
        disposition_reason=None,
    )


def test_page_header_date_terms_stop_at_explicit_page_marker():
    module = _module()
    lines = (
        "Test Limited",
        "April 16, 2026",
        "Page 5 of 13",
        "We expect capacity of 10 MW by April 30, 2027.",
        "Supporting body text",
        "May 1, 2027",
        "More body text",
    )
    terms = module._page_header_date_redaction_terms(lines)
    assert terms == ("April 16, 2026",)
    assert "April 30, 2027" not in terms
    assert "May 1, 2027" not in terms


def test_header_date_fallback_only_uses_first_two_nonempty_lines():
    module = _module()
    lines = (
        "Test Limited",
        "April 16, 2026",
        "Body begins",
        "May 1, 2027",
    )
    assert module._page_header_date_redaction_terms(lines) == ("April 16, 2026",)


def test_build_package_redacts_transcript_header_date_but_preserves_target_date(monkeypatch):
    module = _module()
    raw = b"frozen transcript source-header date bytes"
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
        page_number=5,
        lines=(
            "Test Limited",
            "April 16, 2026",
            "Page 5 of 13",
            "We expect capacity of 10 MW by April 30, 2027.",
            "Supporting body text.",
        ),
    )
    monkeypatch.setattr(module, "_source_pdf_bytes", lambda **kwargs: (raw, "candidate-store:test"))
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
    assert "april 16, 2026" not in visible
    assert "april 30, 2027" in visible


def test_header_date_recognizes_numeric_and_ordinal_formats():
    module = _module()
    assert module._page_header_date_redaction_terms(("16/04/2026", "Page 1 of 2")) == ("16/04/2026",)
    assert module._page_header_date_redaction_terms(("16th April 2026", "Page 1 of 2")) == ("16th April 2026",)
    assert module._page_header_date_redaction_terms(("2026-04-16", "Page 1 of 2")) == ("2026-04-16",)
''',
        encoding="utf-8",
    )


if __name__ == "__main__":
    patch_build_script()
    write_test()
