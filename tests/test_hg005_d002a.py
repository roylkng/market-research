from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg005_d002a import (
    MANDATORY_SOURCE_IDS,
    build_source_corpus,
    resolve_discovery_attachment,
    source_evidence,
    validate_source_manifest,
)


MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "hg005"
    / "hg005-d002-source-manifest-v1.json"
)


def _announcement(
    *,
    symbol: str = "NPST",
    seq_id: str = "1",
    desc: str = "Monitoring Agency Report",
    attachment_text: str = "Monitoring Agency Report for Q1",
) -> dict:
    return {
        "symbol": symbol,
        "seq_id": seq_id,
        "exchdisstime": "11-Aug-2026 19:56:49",
        "desc": desc,
        "attchmntText": attachment_text,
        "attchmntFile": (
            "https://nsearchives.nseindia.com/"
            f"corporate/{symbol}_{seq_id}.pdf"
        ),
    }


def test_frozen_manifest_is_complete_and_host_restricted() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = validate_source_manifest(manifest)
    assert len(rows) == 19
    assert MANDATORY_SOURCE_IDS.issubset(
        {row["source_id"] for row in rows}
    )
    assert {row["symbol"] for row in rows} == {
        "ANANTRAJ",
        "DEVX",
        "INOXGREEN",
        "NPST",
        "SAMBHV",
    }


def test_discovery_requires_one_exact_token_match() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = next(
        row
        for row in manifest["sources"]
        if row["source_id"] == "NPST_Q1FY27_MONITORING"
    )
    result = resolve_discovery_attachment(
        source=source,
        payload=[_announcement()],
    )
    assert result["resolved_url"].endswith("NPST_1.pdf")

    with pytest.raises(AlphaContractError, match="expected one discovery match"):
        resolve_discovery_attachment(
            source=source,
            payload=[_announcement(seq_id="1"), _announcement(seq_id="2")],
        )


def test_pdf_source_evidence_gets_deterministic_text_segments() -> None:
    source = {
        "source_id": "TEST",
        "symbol": "NPST",
        "mode": "DIRECT_URL",
        "source_type": "OFFICIAL_EXCHANGE_OR_REGULATOR",
        "required_fact_groups": ["CURRENT_CAPITAL_DEPLOYMENT"],
    }
    # Minimal invalid-looking PDF bytes should fail text parsing closed, but raw
    # provenance must still remain READY_SOURCE.
    row = source_evidence(
        source=source,
        resolved_url="https://nsearchives.nseindia.com/corporate/test.pdf",
        raw=b"%PDF-1.4\nnot-a-real-pdf",
    )
    assert row["status"] == "READY_SOURCE"
    assert row["document_family"] == "PDF"
    assert row["text_state"] == "PARSE_FAILED"
    assert len(row["raw_sha256"]) == 64


def _manifest_for_corpus() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return manifest


def _evidence_row(source: dict, *, ready: bool = True) -> dict:
    if not ready:
        return {
            "source_id": source["source_id"],
            "symbol": source["symbol"],
            "mode": source["mode"],
            "source_type": source["source_type"],
            "required_fact_groups": source["required_fact_groups"],
            "status": "SOURCE_FAILED",
            "resolved_url": None,
            "raw_sha256": None,
            "raw_byte_count": None,
            "document_family": None,
            "text_state": "UNAVAILABLE",
            "segment_manifest_sha256": None,
            "segments": [],
            "discovery_raw_sha256": None,
            "discovery_match": None,
            "error": "test failure",
        }
    text = f"{source['source_id']} explicit source text"
    import hashlib

    return {
        "source_id": source["source_id"],
        "symbol": source["symbol"],
        "mode": source["mode"],
        "source_type": source["source_type"],
        "required_fact_groups": source["required_fact_groups"],
        "status": "READY_SOURCE",
        "resolved_url": (
            source.get("url")
            or f"https://nsearchives.nseindia.com/corporate/{source['source_id']}.pdf"
        ),
        "raw_sha256": "a" * 64,
        "raw_byte_count": 100,
        "document_family": "PDF",
        "text_state": "READY_TEXT",
        "segment_manifest_sha256": "b" * 64,
        "segments": [
            {
                "segment_id": f"{source['source_id']}:page:1",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        ],
        "discovery_raw_sha256": None,
        "discovery_match": None,
        "error": None,
    }


def test_corpus_passes_with_one_nonmandatory_source_failure() -> None:
    manifest = _manifest_for_corpus()
    nonmandatory = next(
        row["source_id"]
        for row in manifest["sources"]
        if row["source_id"] not in MANDATORY_SOURCE_IDS
    )
    evidence = [
        _evidence_row(
            source,
            ready=source["source_id"] != nonmandatory,
        )
        for source in manifest["sources"]
    ]
    corpus = build_source_corpus(
        manifest=manifest,
        evidence_rows=evidence,
        captured_at_utc="2026-10-05T12:00:00Z",
    )
    assert corpus["ready_source_count"] == 18
    assert corpus["mandatory_text_ready"] is True
    assert corpus["feasibility_pass"] is True
    assert corpus["portfolio_eligibility_allowed"] is False


def test_mandatory_source_failure_blocks_promotion() -> None:
    manifest = _manifest_for_corpus()
    failed = sorted(MANDATORY_SOURCE_IDS)[0]
    evidence = [
        _evidence_row(source, ready=source["source_id"] != failed)
        for source in manifest["sources"]
    ]
    corpus = build_source_corpus(
        manifest=manifest,
        evidence_rows=evidence,
        captured_at_utc="2026-10-05T12:00:00Z",
    )
    assert corpus["mandatory_text_ready"] is False
    assert corpus["feasibility_pass"] is False
    assert corpus["promotion_allowed_to_d002b"] is False
