from __future__ import annotations

import copy
import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_p006_casebook import (
    EXPECTED_SYMBOLS,
    HA001_SHA,
    HG001_SHA,
    P003_ID,
    P003_SHA,
    P004_ID,
    P004_SHA,
    P005_ID,
    P005_SHA,
    build_p006_casebook,
)


def _sources() -> dict:
    p003_docs = {}
    catalog = [{"document_id": None, "source_url": "https://nsearchives.nseindia.com/no.pdf"}]
    p004_cases = []
    p005_cases = []
    hg_rows = []
    ha_rows = []
    for i, symbol in enumerate(sorted(EXPECTED_SYMBOLS)):
        document_id = f"doc-{symbol}"
        url = f"https://nsearchives.nseindia.com/{symbol}.pdf"
        segment_id = f"{document_id}:pdf:page:0001"
        text = "Official transaction document: issue consideration and date."
        segment = {
            "segment_id": segment_id,
            "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "locator": {"page_number": 1},
            "char_count": len(text),
        }
        p003_docs[document_id] = {
            "document_id": document_id,
            "source_url": url,
            "segment_manifest_sha256": f"manifest-{symbol}",
            "segments": [segment],
            "details": {"page_count": 1, "empty_page_count": 0, "failed_page_count": 0},
        }
        catalog.append(
            {"document_id": document_id, "source_url": url, "extraction_state": "READY"}
        )
        facts = {
            "source": {
                f"fact{j}": {
                    "status": "EXPLICIT",
                    "value": j + 1,
                    "unit": "INR",
                    "evidence_segment_ids": [segment_id],
                }
                for j in range(7 if i < 4 else 6)
            }
        }
        p004_cases.append(
            {
                "symbol": symbol,
                "document_id": document_id,
                "source_url": url,
                "explicit_fact_count": len(facts["source"]),
                "validated_extraction": {
                    "document_id": document_id,
                    "facts": facts,
                    "provenance": {
                        "input_segment_manifest_sha256": f"manifest-{symbol}",
                    },
                    "economic_relevance": "DIRECT_LISTED_SECURITY",
                    "transaction_families": ["BUYBACK"],
                    "transaction_stage": "PUBLIC_ANNOUNCEMENT",
                },
            }
        )
        p005_cases.append(
            {
                "symbol": symbol,
                "document_id": document_id,
                "research_lane": "TENDER_BUYBACK_DUE_DILIGENCE",
                "active_transaction_research_lens": True,
                "unverified_evidence_requirements": ["INDEPENDENT_SOURCE_REVIEW"],
                "independent_semantic_audit": "PENDING",
                "underwriting_ready": False,
            }
        )
        hg_rows.append(
            {
                "symbol": symbol,
                "isin": f"INE{i:09d}",
                "research_route": "CONVERGENT_DEEP_DIVE",
                "active_opportunity_lanes": ["CURRENT_SPECIAL_SITUATION"],
                "liquidity_band": "L4_1_TO_2CR",
                "median_daily_turnover_inr": 12_000_000,
                "governance_caution_flags": [],
            }
        )
        ha_rows.append(
            {
                "symbol": symbol,
                "isin": f"INE{i:09d}",
                "opportunity_flags": ["CWIP_CAPACITY_INFLECTION"],
                "caution_flags": [],
            }
        )
    return {
        "p003_corpus": {
            "corpus_id": P003_ID,
            "corpus_sha256": P003_SHA,
            "documents": catalog,
            "return_outcomes_opened": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        },
        "p003_documents": p003_docs,
        "p004_pilot": {
            "pilot_id": P004_ID,
            "pilot_sha256": P004_SHA,
            "cases": p004_cases,
            "return_outcomes_opened": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        },
        "p005_gate": {
            "gate_id": P005_ID,
            "gate_sha256": P005_SHA,
            "cases": p005_cases,
            "return_outcomes_opened": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        },
        "hg001_router": {
            "router_sha256": HG001_SHA,
            "rows": hg_rows,
            "return_outcomes_opened": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        },
        "ha001_panel": {
            "panel_sha256": HA001_SHA,
            "rows": ha_rows,
            "return_outcomes_opened": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        },
    }


def test_casebook_preserves_all_52_claims_but_not_semantic_authority() -> None:
    result = build_p006_casebook(**_sources())
    assert result["case_count"] == 8
    assert result["explicit_fact_count"] == 52
    assert result["cited_segment_reference_count"] == 52
    assert result["underwriting_ready_count"] == 0
    assert result["independent_semantic_audit_complete"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["cases"][0]["claims"][0]["citation_integrity_verified"] is True
    assert result["cases"][0]["claims"][0]["independent_semantic_verification"] == "PENDING"


def test_failed_and_duplicate_document_catalog_entries_do_not_break_binding() -> None:
    inputs = _sources()
    original = inputs["p003_corpus"]["documents"][1]
    duplicate = dict(original, source_url="https://nsearchives.nseindia.com/copy.pdf")
    inputs["p003_corpus"]["documents"].append(duplicate)
    assert build_p006_casebook(**inputs)["explicit_fact_count"] == 52


def test_tampered_source_segment_fails_closed() -> None:
    inputs = _sources()
    row = next(iter(inputs["p003_documents"].values()))
    row["segments"][0]["text"] = "tampered"
    with pytest.raises(AlphaContractError, match="segment text SHA mismatch"):
        build_p006_casebook(**inputs)


def test_missing_claim_segment_fails_closed() -> None:
    inputs = _sources()
    case = inputs["p004_pilot"]["cases"][0]
    case["validated_extraction"]["facts"]["source"]["fact0"]["evidence_segment_ids"] = [
        "invented-segment"
    ]
    with pytest.raises(AlphaContractError, match="missing segment"):
        build_p006_casebook(**inputs)


def test_no_portfolio_authority_permitted_in_source() -> None:
    inputs = _sources()
    inputs["p005_gate"]["portfolio_eligibility_allowed"] = True
    with pytest.raises(AlphaContractError, match="portfolio_eligibility_allowed=false"):
        build_p006_casebook(**inputs)


def test_no_missing_or_extra_company_is_permitted() -> None:
    inputs = copy.deepcopy(_sources())
    inputs["p005_gate"]["cases"].pop()
    with pytest.raises(AlphaContractError, match="frozen eight symbols"):
        build_p006_casebook(**inputs)
