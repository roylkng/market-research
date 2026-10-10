from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_npst_original_pages import (
    EXTRACTION_ID,
    ROOT,
    SOURCE_BOUNDARIES,
    build_npst_original_page_evidence,
    validate_npst_source_packet,
)


@pytest.fixture(scope="module")
def packet() -> dict:
    return build_npst_original_page_evidence(Path("."))


def test_25_original_pages_and_exact_two_reporting_families(packet: dict) -> None:
    validate_npst_source_packet(packet)
    assert packet["source_evidence_id"] == EXTRACTION_ID
    assert packet["original_page_count"] == 25
    assert packet["document_count"] == 2
    documents = {x["source_id"]: x for x in packet["original_documents"]}
    assert set(documents) == set(SOURCE_BOUNDARIES)
    assert len(documents["2026-08-11-investor-presentation"]["pages"]) == 22
    assert len(documents["2026-08-11-june-reg32-use-of-funds"]["pages"]) == 3
    assert all(x["reporting_period"] == "2026-06-30" for x in documents.values())
    assert all(x["original_source_sha256"] == SOURCE_BOUNDARIES[k]["sha256"] for k,x in documents.items())
    assert packet["ambiguous_march_monitoring_attachment_excluded"] is True
    assert packet["actual_quarterly_ebitda_figure_approved"] is False
    assert packet["unused_funds_balance_approved"] is False
    assert packet["live_capital_allowed"] is False


def test_original_filing_pages_are_not_explicit_broker_buy_calls(packet: dict) -> None:
    assert all(
        doc["filing_family"] in (
            "INVESTOR_PRESENTATION_Q1FY27",
            "REG32_JUNE_2026_VARIATION_AND_USE_OF_PROCEEDS",
        )
        for doc in packet["original_documents"]
    )
    for doc in packet["original_documents"]:
        for idx,page in enumerate(doc["pages"],1):
            assert page["page_number_one_based"] == idx
            assert page["financial_table_semantics_independently_verified"] is False
            assert len(page["extracted_text_sha256"]) == 64
            assert page["source_document_sha256"] == doc["original_source_sha256"]
        for excerpt in doc["search_snippet_first_occurrence_by_page_keyword"]:
            assert excerpt["excerpt_is_not_a_verified_financial_value"] is True
            assert excerpt["source_page_sha256"] in {
                p["extracted_text_sha256"] for p in doc["pages"]
            }


def test_source_page_mutation_rejected(packet: dict) -> None:
    changed = deepcopy(packet)
    changed["original_documents"][0]["pages"][0]["extracted_text"] += (
        "Invented cash proceeds 999 crores"
    )
    with pytest.raises(ValueError, match="original page SHA"):
        validate_npst_source_packet(changed)
    changed = deepcopy(packet)
    changed["unused_funds_balance_approved"] = True
    with pytest.raises(ValueError, match="cannot authorize"):
        validate_npst_source_packet(changed)


def test_original_receipt_or_pdf_byte_mutation_rejected(tmp_path: Path) -> None:
    for kind, contract in SOURCE_BOUNDARIES.items():
        base = ROOT / kind
        paths = [
            base / "original-receipt-v1.json",
            base / "raw" / "sha256" / f"{contract['sha256']}.pdf",
        ]
        for original in paths:
            dest = tmp_path / original
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(original.read_bytes())
    receipt = tmp_path / ROOT / "2026-08-11-investor-presentation" / "original-receipt-v1.json"
    receipt.write_bytes(receipt.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Git blob"):
        build_npst_original_page_evidence(tmp_path)
    receipt.write_bytes(
        (ROOT / "2026-08-11-investor-presentation" / "original-receipt-v1.json").read_bytes()
    )
    source = tmp_path / ROOT / "2026-08-11-investor-presentation" / "raw" / "sha256" / (
        SOURCE_BOUNDARIES["2026-08-11-investor-presentation"]["sha256"] + ".pdf"
    )
    source.write_bytes(source.read_bytes() + b"altered")
    with pytest.raises(ValueError, match="full PDF binary SHA"):
        build_npst_original_page_evidence(tmp_path)


def test_cli_replay_and_immutable_compare(packet: dict, tmp_path: Path) -> None:
    output = tmp_path / "npst-q1-originals.json"
    cmd = [
        sys.executable,
        "scripts/extract_hg007_npst_original_pages.py",
        "--out",
        str(output),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    result = json.loads(completed.stdout)
    assert result["source_document_count"] == 2
    assert result["source_original_page_count"] == 25
    assert result["ambiguous_monitoring_excluded"] is True
    assert json.loads(output.read_text(encoding="utf-8")) == packet
    subprocess.run(
        cmd + ["--verify-existing"], capture_output=True, text=True, check=True
    )
    output.write_text(output.read_text(encoding="utf-8") + "bogus")
    result = subprocess.run(
        cmd + ["--verify-existing"], capture_output=True, text=True, check=False
    )
    assert result.returncode != 0
    assert "content changed" in result.stderr
