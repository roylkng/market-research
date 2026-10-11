from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_anantraj_scheme_pages import (
    INDEX_ID,
    PAGE_COUNT,
    PDF_SHA256,
    RECEIPT_PATH,
    build_page_text_evidence,
    load_original_scheme_source,
    write_or_verify_page_evidence,
)


@pytest.fixture(scope="module")
def original_page_packet() -> tuple[dict, dict[str, bytes]]:
    raw, receipts = load_original_scheme_source(Path("."))
    return build_page_text_evidence(raw, receipts)


def test_exact_official_pdf_all_48_pages_reproduce_p024_hashes(
    original_page_packet: tuple[dict, dict[str, bytes]],
) -> None:
    index, files = original_page_packet
    assert index["index_id"] == INDEX_ID
    assert index["pdf_original_sha256"] == PDF_SHA256
    assert index["page_count"] == PAGE_COUNT == 48
    assert index["pdf_byte_count"] == 10_044_735
    assert len(index["pages"]) == 48
    assert len(files) == 48
    assert [row["page_number"] for row in index["pages"]] == list(range(1, 49))
    assert all(
        row["source_page_text_sha256"] == hashlib.sha256(
            files[row["file_name"]]
        ).hexdigest()
        for row in index["pages"]
    )
    assert index["page_text_fully_extracted_and_sha_verified"] is True
    assert index["actual_legal_scheme_effective_date_verified"] is False
    assert index["transferred_liability_values_verified"] is False
    assert index["parent_subsidiary_double_counting_resolved"] is False
    assert index["live_capital_allowed"] is False


def test_source_routing_labels_are_not_financial_approval(
    original_page_packet: tuple[dict, dict[str, bytes]],
) -> None:
    index, _files = original_page_packet
    counts = index["label_counts_search_only"]
    assert counts["liability_allocation_mention"] >= 10
    assert counts["asset_allocation_mention"] >= 10
    assert counts["transfer_date_mention"] >= 1
    assert counts["shareholder_issuance_mention"] >= 1
    for row in index["pages"]:
        assert row["transferred_asset_liability_values_independently_verified"] is False
        assert row["page_layout_or_signatures_visually_audited"] is False
        assert row["issuer_proposed_terms_are_legal_approval"] is False


def test_original_pdf_source_bytes_mutation_fails_before_parsing(tmp_path: Path) -> None:
    from marketlab.hg007_anantraj_scheme_pages import PDF_PATH

    for path in (RECEIPT_PATH, PDF_PATH):
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    raw, _ = load_original_scheme_source(tmp_path)
    assert hashlib.sha256(raw).hexdigest() == PDF_SHA256
    corrupt = tmp_path / PDF_PATH
    corrupt.write_bytes(corrupt.read_bytes() + b"appended")
    with pytest.raises(ValueError, match="differ from official SHA"):
        load_original_scheme_source(tmp_path)


def test_original_receipt_page_sha_mutation_is_rejected(
    original_page_packet: tuple[dict, dict[str, bytes]],
) -> None:
    raw, receipt_rows = load_original_scheme_source(Path("."))
    wrong = deepcopy(receipt_rows)
    wrong[5]["text_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="page 6 text differs"):
        build_page_text_evidence(raw, wrong)


def test_written_index_and_pages_are_append_only(
    original_page_packet: tuple[dict, dict[str, bytes]],
    tmp_path: Path,
) -> None:
    index, pages = original_page_packet
    dest = tmp_path / "source"
    write_or_verify_page_evidence(dest, index, pages)
    assert len(list(dest.glob("original-page-*.txt"))) == PAGE_COUNT
    stored = json.loads((dest / "page-index-v1.json").read_text(encoding="utf-8"))
    assert stored == index
    write_or_verify_page_evidence(dest, index, pages, verify_existing=True)
    (dest / "original-page-06.txt").write_bytes(
        (dest / "original-page-06.txt").read_bytes() + b"\nfake deal terms"
    )
    with pytest.raises(ValueError, match="original issuer page source changed"):
        write_or_verify_page_evidence(dest, index, pages, verify_existing=True)


def test_nonempty_page_text_has_real_issuer_identity(
    original_page_packet: tuple[dict, dict[str, bytes]],
) -> None:
    _index, pages = original_page_packet
    first = "\n".join(
        pages[f"original-page-{number:02d}.txt"].decode("utf-8")
        for number in (1, 2, 3, 4, 5, 6)
    ).casefold()
    assert "anant raj limited" in first
    assert "ashok cloud private limited" in first
    assert "composite scheme" in first


def test_source_cli_materializes_original_pages_without_alpha(tmp_path: Path) -> None:
    out = tmp_path / "issuer-pages"
    command = [
        sys.executable, "scripts/materialize_hg007_anantraj_scheme_pages.py",
        "--output-dir", str(out),
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    summary = json.loads(first.stdout)
    assert summary["page_count"] == 48
    assert summary["all_pages_verifiable"] is True
    assert summary["live_capital_allowed"] is False
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    (out / "original-page-48.txt").write_text("modified", encoding="utf-8")
    failed = subprocess.run(
        command + ["--verify-existing"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed.returncode != 0
    assert "original issuer page source changed" in failed.stderr
