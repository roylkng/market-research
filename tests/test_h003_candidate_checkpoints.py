from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from marketlab.h003_candidates import (
    EXTRACTION_RULE_ID,
    EXTRACTION_RULE_SHA256,
    H003CandidateError,
    SourceExtractionRecord,
    _record_digest,
)


def _runner_module():
    path = Path("scripts/build_h003_candidates.py")
    spec = importlib.util.spec_from_file_location("build_h003_candidates", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(*, status: str) -> SourceExtractionRecord:
    provisional = SourceExtractionRecord(
        schema_version=1,
        record_id="",
        rule_id=EXTRACTION_RULE_ID,
        rule_sha256=EXTRACTION_RULE_SHA256,
        source_id="source-1",
        symbol="TEST",
        exchange_published_at_utc="2026-08-01T10:00:00Z",
        attachment_url="https://nsearchives.nseindia.com/test.pdf",
        status=status,
        failure_reason=None if status == "TEXT_READY" else "network",
        raw_sha256="a" * 64 if status == "TEXT_READY" else None,
        raw_byte_count=10 if status == "TEXT_READY" else None,
        parser_version="h003_pdf_text_v1",
        parser_library_version="6.17.0",
        page_count=1 if status == "TEXT_READY" else None,
        text_sha256="b" * 64 if status == "TEXT_READY" else None,
        text_char_count=10 if status == "TEXT_READY" else None,
        candidate_count=0,
        candidates=(),
        raw_path="raw/sha256/a.pdf" if status == "TEXT_READY" else None,
        text_path="text/sha256/b.txt" if status == "TEXT_READY" else None,
    )
    return SourceExtractionRecord(
        **{**provisional.__dict__, "record_id": _record_digest(provisional)}
    )


def test_text_ready_checkpoint_round_trips_and_resumes(tmp_path):
    module = _runner_module()
    path = tmp_path / "records" / "source-1.json"
    module._write_checkpoint(path, _record(status="TEXT_READY"))
    loaded = module._load_checkpoint(
        path,
        source_id="source-1",
        symbol="TEST",
        attachment_url="https://nsearchives.nseindia.com/test.pdf",
    )
    assert loaded is not None
    assert loaded.status == "TEXT_READY"
    assert loaded.record_id == _record(status="TEXT_READY").record_id


def test_fetch_error_checkpoint_is_retried_not_resumed(tmp_path):
    module = _runner_module()
    path = tmp_path / "records" / "source-1.json"
    module._write_checkpoint(path, _record(status="FETCH_ERROR"))
    assert (
        module._load_checkpoint(
            path,
            source_id="source-1",
            symbol="TEST",
            attachment_url="https://nsearchives.nseindia.com/test.pdf",
        )
        is None
    )


def test_checkpoint_identity_mismatch_fails_closed(tmp_path):
    module = _runner_module()
    path = tmp_path / "records" / "source-1.json"
    module._write_checkpoint(path, _record(status="TEXT_READY"))
    with pytest.raises(H003CandidateError, match="identity mismatch"):
        module._load_checkpoint(
            path,
            source_id="source-1",
            symbol="OTHER",
            attachment_url="https://nsearchives.nseindia.com/test.pdf",
        )
