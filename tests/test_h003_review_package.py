from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from marketlab.h003_candidates import ClaimCandidate, ExtractedPage
from marketlab.h003_review import CandidateCorpus


def _module():
    path = Path("scripts/build_h003_review_package.py")
    spec = importlib.util.spec_from_file_location("build_h003_review_package", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate(
    *,
    candidate_id: str,
    source_id: str,
    raw: bytes,
    excerpt: str,
    line_start: int,
) -> ClaimCandidate:
    return ClaimCandidate(
        schema_version=2,
        candidate_id=candidate_id,
        rule_id="H003-E002",
        rule_sha256="5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2",
        candidate_version="h003_future_commitment_candidate_v2",
        source_id=source_id,
        symbol="TEST",
        exchange_published_at_utc="2026-08-01T10:00:00Z",
        attachment_url="https://nsearchives.nseindia.com/test.pdf",
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        parser_version="h003_pdf_text_v1",
        page_number=1,
        line_start=line_start,
        line_end=line_start,
        excerpt=excerpt,
        future_markers=("we expect",),
        deadline_markers=("next year",),
        quantitative_tokens=("15%",),
        domain_markers=("revenue",),
        disposition="UNREVIEWED",
        disposition_reason=None,
    )


class _Client:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.calls = 0

    def archive_bytes(self, url: str) -> bytes:
        assert url == "https://nsearchives.nseindia.com/test.pdf"
        self.calls += 1
        return self.raw


def test_package_fetches_once_per_source_redacts_identity_and_only_auto_rejects_question(
    monkeypatch,
):
    module = _module()
    raw = b"frozen-pdf-bytes"
    answer = "We expect TEST revenue growth of 15% next year."
    question = "Why do we expect TEST revenue growth of 15% next year?"
    answer_candidate = _candidate(
        candidate_id="answer",
        source_id="source-1",
        raw=raw,
        excerpt=answer,
        line_start=1,
    )
    question_candidate = _candidate(
        candidate_id="question",
        source_id="source-1",
        raw=raw,
        excerpt=question,
        line_start=2,
    )
    corpus = CandidateCorpus(
        report_sha256="c" * 64,
        candidate_rule_id="H003-E002",
        candidate_rule_sha256=answer_candidate.rule_sha256,
        source_bundle_sha256="583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee",
        cohort_id="FY27-Q2-2026-09-06",
        candidate_count=2,
        candidates_by_id={"answer": answer_candidate, "question": question_candidate},
    )
    monkeypatch.setattr(
        module,
        "extract_pdf_pages",
        lambda _: (
            (ExtractedPage(page_number=1, lines=(answer, question, "Test Limited discussion")),),
            answer + "\n" + question,
        ),
    )
    client = _Client(raw)
    package, payloads, decisions = module.build_package(
        corpus,
        company_names={"TEST": "Test Limited"},
        client=client,
        fetch_attempts=1,
    )
    assert client.calls == 1
    assert package["blind_payload_count"] == 2
    assert package["mechanical_rejected_count"] == 1
    assert package["semantic_review_count"] == 1
    assert [decision.candidate_id for decision in decisions] == ["question"]
    assert decisions[0].reason_code == "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    for payload in payloads:
        text = payload.redacted_excerpt + " " + " ".join(payload.redacted_page_context)
        assert "TEST" not in text
        assert "Test Limited" not in text
    assert len(package["package_sha256"]) == 64


def test_changed_pdf_bytes_fail_closed_before_blind_review(monkeypatch):
    module = _module()
    frozen_raw = b"original"
    changed_raw = b"changed"
    excerpt = "We expect TEST revenue growth of 15% next year."
    candidate = _candidate(
        candidate_id="candidate",
        source_id="source-1",
        raw=frozen_raw,
        excerpt=excerpt,
        line_start=1,
    )
    corpus = CandidateCorpus(
        report_sha256="c" * 64,
        candidate_rule_id="H003-E002",
        candidate_rule_sha256=candidate.rule_sha256,
        source_bundle_sha256="583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee",
        cohort_id="FY27-Q2-2026-09-06",
        candidate_count=1,
        candidates_by_id={candidate.candidate_id: candidate},
    )
    monkeypatch.setattr(
        module,
        "extract_pdf_pages",
        lambda _: ((ExtractedPage(page_number=1, lines=(excerpt,)),), excerpt),
    )
    try:
        module.build_package(
            corpus,
            company_names={"TEST": "Test Limited"},
            client=_Client(changed_raw),
            fetch_attempts=1,
        )
    except module.ReviewPackageError as exc:
        assert "source bytes changed" in str(exc)
    else:
        raise AssertionError("changed PDF bytes must fail closed")
