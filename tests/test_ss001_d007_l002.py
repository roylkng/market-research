from __future__ import annotations

import copy

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_d007_l002 import (
    EXPECTED_ISSUERS,
    _claims,
    _closed,
    build_issuer_evidence,
)
from marketlab.ss002_llm_contract import extraction_template


def _extraction(symbol: str, document_id: str) -> dict:
    extraction = extraction_template(
        document_id=document_id,
        event_ids=[f"EVENT-{symbol}"],
        symbols=[symbol],
    )
    extraction["economic_relevance"] = "DIRECT_LISTED_SECURITY"
    extraction["transaction_families"] = ["RIGHTS_ISSUE"]
    extraction["transaction_stage"] = "PROCEDURAL_UPDATE"
    extraction["facts"]["security_economics"]["issue_price_per_share"] = {
        "status": "EXPLICIT",
        "value": 100.0,
        "unit": "INR_PER_SHARE",
        "evidence_segment_ids": ["page:1"],
    }
    extraction["validated_structured_output_sha256"] = "a" * 64
    extraction["return_outcomes_opened"] = False
    extraction["portfolio_eligibility_allowed"] = False
    extraction["live_capital_allowed"] = False
    return extraction


def _fixtures() -> tuple[dict, dict, dict, list[dict]]:
    queue = {
        "issuer_symbols": list(EXPECTED_ISSUERS),
        "announcement_reference_count": 95,
        "distinct_document_count": 82,
        "p1_reuse_document_count": 12,
        "fresh_document_count": 70,
        "corporate_action_row_count": 12,
        "corporate_action_evidence": [
            {"symbol": sym, "source_raw_sha256": "f" * 64}
            for sym in EXPECTED_ISSUERS
        ],
    }
    p1_rows = {}
    reused = []
    for i, sym in enumerate(EXPECTED_ISSUERS):
        doc_id = f"p1-doc-{i}"
        reused.append({
            "document_id": doc_id,
            "document_order": 1,
            "execution_state": "P1_REUSE",
            "symbol": sym,
            "q002_event_ids": [f"EVENT-{sym}"],
            "d003_categories": ["RIGHTS_ISSUE"],
            "d003_segment_manifest_sha256": "b" * 64,
            "d003_segment_count": 1,
            "source_url": f"https://nsearchives.nseindia.com/{doc_id}.pdf",
        })
        p1_rows[doc_id] = {"validated_extraction": _extraction(sym, doc_id)}
    fresh = []
    requests = []
    for i in range(70):
        sym = EXPECTED_ISSUERS[i % 12]
        doc_id = f"fresh-doc-{i}"
        fresh.append({
            "document_id": doc_id,
            "document_order": 2 + i // 12,
            "execution_state": "FRESH_PAGE_REQUESTS",
            "symbol": sym,
            "q002_event_ids": [f"EVENT-{sym}"],
            "d003_categories": ["RIGHTS_ISSUE"],
            "d003_segment_manifest_sha256": "c" * 64,
            "d003_segment_count": 1,
            "source_url": f"https://nsearchives.nseindia.com/{doc_id}.pdf",
        })
        requests.append({
            "document_id": doc_id,
            "symbol": sym,
            "segment_order": 1,
            "segment_id": f"{doc_id}:page:1",
            "request_id": f"req-{i}",
        })
    queue["reused_documents"] = reused
    queue["fresh_documents"] = fresh
    return queue, {"run_sha256": "p1-source"}, p1_rows, requests


def _patch(monkeypatch: pytest.MonkeyPatch, p1_rows: dict, requests: list[dict]) -> None:
    monkeypatch.setattr(
        "marketlab.ss001_d007_l002.validate_queue",
        lambda queue: requests,
    )
    monkeypatch.setattr(
        "marketlab.ss001_d007_l002._p1_index",
        lambda p1, queue: p1_rows,
    )
    monkeypatch.setattr("marketlab.ss001_d007_l002.SOURCE_REQUEST_COUNT", 70)


def test_claim_projection_keeps_explicit_evidence_not_unknowns() -> None:
    extraction = _extraction("AAA", "document")
    claims = _claims(extraction, request_id="request-1")
    assert len(claims) == 1
    assert claims[0]["field_path"] == "security_economics.issue_price_per_share"
    assert claims[0]["evidence_segment_ids"] == ["page:1"]
    assert claims[0]["request_id"] == "request-1"


def test_l002_refuses_capital_clearance_even_in_source() -> None:
    with pytest.raises(AlphaContractError, match="share_action_clearance_proven=false"):
        _closed({"share_action_clearance_proven": True}, "tampered")


def test_partial_ledger_accounts_for_every_frozen_document_and_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue, p1, p1_rows, requests = _fixtures()
    _patch(monkeypatch, p1_rows, requests)

    result = build_issuer_evidence(queue, p1)
    assert result["status"] == "PARTIAL_EVIDENCE_PENDING_MODEL_OUTPUT"
    assert result["issuer_count"] == 12
    assert result["document_count"] == 82
    assert result["fresh_validated_response_count"] == 0
    assert result["fresh_remaining_response_count"] == 70
    assert sum(
        row["missing_fresh_page_count"] for row in result["issuer_rows"]
    ) == 70
    assert all(
        "UNRESOLVED_SOURCE_COVERAGE" in row["review_flags"]
        for row in result["issuer_rows"]
    )
    assert result["semantic_audit_complete"] is False
    assert result["market_capitalization_calculated"] is False
    assert result["portfolio_eligibility_allowed"] is False


def test_partial_api_page_preserves_distinct_model_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue, p1, p1_rows, requests = _fixtures()
    _patch(monkeypatch, p1_rows, requests)
    monkeypatch.setattr(
        "marketlab.ss001_d007_l002.validate_config",
        lambda config: "runtime-sha",
    )
    monkeypatch.setattr(
        "marketlab.ss001_d007_l002.build_collection_status",
        lambda queue, config, rows: {"status": "PARTIAL_VALIDATED_EXTRACTIONS"},
    )
    request = requests[0]
    sealed = {
        "request_id": request["request_id"],
        "document_id": request["document_id"],
        "validated_extraction": _extraction(request["symbol"], request["document_id"]),
    }
    result = build_issuer_evidence(
        queue,
        p1,
        runtime_config={"dummy": True},
        validated_r001_rows=[sealed],
    )
    assert result["fresh_validated_response_count"] == 1
    assert result["fresh_remaining_response_count"] == 69
    first = result["issuer_rows"][0]
    assert "MIXED_MODEL_COHORTS" in first["review_flags"]
    assert first["validated_fresh_page_count"] == 1
    assert first["missing_fresh_page_count"] == 5
    assert result["share_action_clearance_proven"] is False


def test_malformed_frozen_document_identity_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue, p1, p1_rows, requests = _fixtures()
    _patch(monkeypatch, p1_rows, requests)
    changed = copy.deepcopy(queue)
    changed["fresh_documents"][0]["document_id"] = changed["reused_documents"][0][
        "document_id"
    ]
    with pytest.raises(AlphaContractError, match="documents are not unique"):
        build_issuer_evidence(changed, p1)


def test_model_responses_require_runtime_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue, p1, p1_rows, requests = _fixtures()
    _patch(monkeypatch, p1_rows, requests)
    with pytest.raises(AlphaContractError, match="require a pinned runtime"):
        build_issuer_evidence(
            queue,
            p1,
            validated_r001_rows=[
                {
                    "request_id": requests[0]["request_id"],
                    "document_id": requests[0]["document_id"],
                }
            ],
        )
