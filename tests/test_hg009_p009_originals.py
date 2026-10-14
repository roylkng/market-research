"""P009 protects source custody from fabricated financial certification."""

from __future__ import annotations

import copy
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p009_originals import (
    ARCHIVE_ROOT,
    original_source_receipt,
    source_specifications,
    validate_original_receipt,
)
from scripts.verify_hg009_p009_originals import verify

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 15, 0, 5, tzinfo=UTC)


def _spec(symbol: str):
    return next(
        row for row in source_specifications(ROOT)
        if row["symbol"] == symbol
    )


def test_all_five_predeclared_original_sources_are_pinned_to_research():
    docs = source_specifications(ROOT)
    assert len(docs) == 5
    assert {doc["document_id"] for doc in docs} == {
        "MAYURUNIQ-FY26_AUDITED_CONSOLIDATED",
        "PIXTRANS-Q1FY27_STANDALONE",
        "PIXTRANS-Q1FY26_STANDALONE",
        "DATAMATICS-FY26_AUDITED_CONSOLIDATED",
        "POKARNA-FY26_ORIGINAL_RESULT_PACKET",
    }
    assert {doc["symbol"] for doc in docs} == {
        "MAYURUNIQ", "PIXTRANS", "DATAMATICS", "POKARNA",
    }
    assert all(
        doc["source_url"].startswith(
            "https://nsearchives.nseindia.com/corporate/"
        )
        for doc in docs
    )
    assert all(len(doc["source_provenance_parent_sha256"]) == 64 for doc in docs)


def test_archival_retains_actual_byte_hash_but_never_certifies_financial_rows(
    tmp_path: Path,
):
    spec = _spec("MAYURUNIQ")
    raw = b"<!DOCTYPE html><html><body>original issuer data</body></html>" * 3
    receipt = original_source_receipt(
        spec=spec, fetch=lambda _url: (200, raw),
        recorded_at_utc=NOW, completed_at_utc=NOW, repo_root=tmp_path,
    )
    validate_original_receipt(receipt, root=tmp_path)
    assert receipt["state"] == (
        "RAW_ARCHIVED_NOT_YET_FINANCIALLY_OR_IDENTITY_VALIDATED"
    )
    assert receipt["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["actual_retrieved_at_utc"] == NOW.isoformat()
    assert receipt["cashflow_values_reconciled_to_original_bytes"] is False
    assert receipt["shareholder_normalized_owner_cash_verified"] is False
    assert receipt["live_capital_allowed"] is False
    assert (tmp_path / receipt["raw_repo_path"]).is_file()


def test_pdf_format_is_archived_without_claiming_audited_financial_replay(tmp_path):
    spec = _spec("DATAMATICS")
    data = b"%PDF-1.7\n" + b"test only PDF body" * 20
    receipt = original_source_receipt(
        spec=spec, fetch=lambda _url: (200, data),
        recorded_at_utc=NOW, completed_at_utc=NOW, repo_root=tmp_path,
    )
    validate_original_receipt(receipt, root=tmp_path)
    assert receipt["file_type"] == "pdf"
    assert receipt["original_issuer_publication_date"] == "2026-05-21"
    assert receipt["issuer_and_period_content_verified"] is False
    assert receipt["raw_repo_path"].endswith(".pdf.gz")


def test_http_403_and_redirects_never_appear_as_original_retrieval(tmp_path):
    spec = _spec("PIXTRANS")
    for code in (302, 403, 404, 429):
        blocked = original_source_receipt(
            spec=spec, fetch=lambda _url, status=code: (status, None),
            recorded_at_utc=NOW, completed_at_utc=NOW, repo_root=tmp_path,
        )
        validate_original_receipt(blocked, root=tmp_path)
        assert blocked["state"] == "BLOCKED_ORIGINAL_HTTP"
        assert blocked["raw_sha256"] is None
        assert blocked["raw_repo_path"] is None


def test_bad_format_tampering_and_false_promotion_rejected(tmp_path):
    spec = _spec("DATAMATICS")
    receipt = original_source_receipt(
        spec=spec, fetch=lambda _url: (200, b"<html>not official PDF</html>" * 9),
        recorded_at_utc=NOW, completed_at_utc=NOW, repo_root=tmp_path,
    )
    assert receipt["state"] == "BLOCKED_UNREADABLE_FORMAT_RAW_NOT_PROMOTED"
    assert receipt["raw_repo_path"] is None

    real = original_source_receipt(
        spec=spec,
        fetch=lambda _url: (200, b"%PDF-1.5\n" + b"synthetic only" * 20),
        recorded_at_utc=NOW,
        completed_at_utc=NOW,
        repo_root=tmp_path,
    )
    changed = copy.deepcopy(real)
    changed["issuer_equity_valuation_eligible"] = True
    changed["receipt_sha256"] = digest({
        key: value for key, value in changed.items()
        if key != "receipt_sha256"
    })
    with pytest.raises(AlphaContractError, match="incorrectly promoted"):
        validate_original_receipt(changed, root=tmp_path)

    file = tmp_path / real["raw_repo_path"]
    file.write_bytes(b"tampered archive")
    with pytest.raises((AlphaContractError, OSError)):
        validate_original_receipt(real, root=tmp_path)


def test_date_and_original_filename_are_not_backdated(tmp_path):
    spec = _spec("POKARNA")
    with pytest.raises(AlphaContractError, match="before filing"):
        original_source_receipt(
            spec=spec,
            fetch=lambda _url: (200, b"%PDF-1.7" + b"x" * 300),
            recorded_at_utc=datetime(2026, 5, 1, tzinfo=UTC),
            repo_root=tmp_path,
        )


def test_read_only_verifier_does_not_create_or_retrieve_any_issuer_file():
    output = verify(ROOT)
    assert output["predeclared_document_count"] == 5
    assert output["verified_attempt_count"] >= 0
    assert output["live_capital_allowed"] is False
    assert output["shareholder_owner_cashflow_verified"] is False
    assert output["all_issuer_financial_values_verified"] is False
    assert ARCHIVE_ROOT.parts[-1] == "p009-originals"


def test_retrieval_receipt_clock_cannot_precede_http_request_start(tmp_path: Path):
    spec = _spec("MAYURUNIQ")
    raw = b"<html>source fixture</html>" * 20
    with pytest.raises(AlphaContractError, match="before start time"):
        original_source_receipt(
            spec=spec,
            fetch=lambda _url: (200, raw),
            recorded_at_utc=NOW,
            completed_at_utc=NOW - timedelta(seconds=2),
            repo_root=tmp_path,
        )
