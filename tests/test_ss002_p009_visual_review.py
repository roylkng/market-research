from __future__ import annotations

import copy
import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_p009_visual_review import (
    STATUS_CORRUPTED,
    STATUS_PRESENT,
    STATUS_SPARSE,
    STATUS_UNEXTRACTED,
    build_p009_legibility_packet,
    page_legibility,
)


def _fixture() -> dict:
    cases = []
    sizes = {
        "INOXGREEN": (6, 11),
        "KOTHARIPET": (2, 5),
        "OLAELEC": (2, 12),
        "VRLLOG": (7, 7),
    }
    for sym, (count, n_claims) in sizes.items():
        docid = "a" * 64 if sym == "INOXGREEN" else (
            "b" * 64 if sym == "KOTHARIPET" else (
                "c" * 64 if sym == "OLAELEC" else "d" * 64
            )
        )
        pages = []
        for i in range(1, count + 1):
            if sym == "VRLLOG" and i in (6, 7):
                continue
            txt = (
                "\ufffd" * 64
                if sym == "VRLLOG" and i in (2, 3, 4, 5)
                else f"Official transaction paragraph page {i} contains verified wording."
            )
            pages.append({
                "page_number": i,
                "source_text": txt,
                "segment_id": f"{docid}:pdf:page:{i:04d}",
                "source_text_sha256": hashlib.sha256(txt.encode()).hexdigest(),
            })
        claims = [
            {
                "field_path": f"parties.x{i}",
                "extracted_value": str(i),
                "review_status": "PENDING_INDEPENDENT_REVIEW",
                "semantic_support_accepted": False,
            }
            for i in range(n_claims)
        ]
        cases.append({
            "symbol": sym,
            "document_id": docid,
            "original_pdf_raw_sha256": docid,
            "official_nse_url": f"https://nsearchives.nseindia.com/{sym}.pdf",
            "original_pdf_page_count": count,
            "original_pages_requiring_visual_review": [6, 7] if sym == "VRLLOG" else [],
            "pages": pages,
            "claims": claims,
        })
    return {
        "pack_id": "SS002-P008-v1",
        "pack_sha256": "94b098d24ef6c5eb3482ce4c79ec696c24a6f761a4bc0f3fe6e0e5ae7f985768",
        "case_count": 4,
        "claim_count": 35,
        "cases": cases,
        "independent_semantic_audit_complete": False,
        "original_pdf_visual_review_complete": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "return_outcomes_opened": False,
    }


def test_legibility_detects_replacement_glyphs_and_empty_pages() -> None:
    assert page_legibility("\ufffd" * 64)[0] == STATUS_CORRUPTED
    assert page_legibility(None)[0] == STATUS_UNEXTRACTED
    assert page_legibility("abc")[0] == STATUS_SPARSE
    assert page_legibility("The company approved the transaction on Tuesday.")[0] == STATUS_PRESENT


def test_exact_source_stays_unreviewed_and_flags_six_vrl_pages() -> None:
    result = build_p009_legibility_packet(_fixture())
    assert result["original_page_count"] == 17
    assert result["claim_count"] == 35
    assert result["legibility_state_counts"] == {
        STATUS_PRESENT: 11,
        STATUS_CORRUPTED: 4,
        STATUS_UNEXTRACTED: 2,
        STATUS_SPARSE: 0,
    }
    vrl = next(row for row in result["cases"] if row["symbol"] == "VRLLOG")
    assert vrl["priority_visual_pages"] == [2, 3, 4, 5, 6, 7]
    assert result["independent_semantic_audit_complete"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert all(page["visual_review_required"] for case in result["cases"] for page in case["pages"])


def test_tampered_page_sha_fails_closed() -> None:
    p = _fixture()
    p["cases"][0]["pages"][0]["source_text"] = "tampered"
    with pytest.raises(AlphaContractError, match="source text SHA changed"):
        build_p009_legibility_packet(p)


def test_changed_original_pack_is_rejected() -> None:
    p = _fixture()
    p["pack_sha256"] = "0" * 64
    with pytest.raises(AlphaContractError, match="exact frozen P008"):
        build_p009_legibility_packet(p)


def test_claims_must_remain_pending() -> None:
    p = copy.deepcopy(_fixture())
    p["cases"][1]["claims"][0]["review_status"] = "PASS"
    with pytest.raises(AlphaContractError, match="reviewer states must remain pending"):
        build_p009_legibility_packet(p)
