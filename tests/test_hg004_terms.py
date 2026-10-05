from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.events import sha256_bytes
from marketlab.hg004_terms import select_hg004_detailed_terms


SYMBOLS = [
    "ANANTRAJ",
    "AXITA",
    "DATAMATICS",
    "DEVX",
    "FCL",
    "INOXGREEN",
    "NPST",
    "SAMBHV",
    "SANDESH",
    "SUVIDHAA",
    "TREL",
]


def _segment(document_id: str) -> dict:
    text = f"Terms for {document_id}"
    return {
        "segment_id": f"{document_id}:pdf:page:0001",
        "kind": "PDF_PAGE",
        "locator": {"page_number": 1},
        "text": text,
        "text_sha256": sha256_bytes(text.encode()),
        "utf8_byte_count": len(text.encode()),
        "char_count": len(text),
    }


def _sources() -> tuple[dict, dict, dict, list[dict]]:
    clusters = {
        "ANANTRAJ": [("SCHEME_REORGANISATION", "ACTIVE_FORWARD_STAGE", "SCHEME_REORGANISATION")],
        "AXITA": [("INSOLVENCY_ACQUISITION", "ACTIVE_FORWARD_STAGE", "INSOLVENCY_RESOLUTION")],
        "DATAMATICS": [("SCHEME_REORGANISATION", "ACTIVE_FORWARD_STAGE", "SCHEME_REORGANISATION")],
        "DEVX": [("PREFERENTIAL_WARRANT", "PROCEDURAL_STAGE", "PREFERENTIAL_WARRANT")],
        "FCL": [("PREFERENTIAL_WARRANT", "PROCEDURAL_STAGE", "PREFERENTIAL_WARRANT")],
        "INOXGREEN": [("INSOLVENCY_ACQUISITION", "ACTIVE_FORWARD_STAGE", "INSOLVENCY_RESOLUTION")],
        "NPST": [("FUND_RAISE_OTHER", "PROCEDURAL_STAGE", "PREFERENTIAL_WARRANT")],
        "SAMBHV": [("PREFERENTIAL_WARRANT", "ACTIVE_FORWARD_STAGE", "PREFERENTIAL_WARRANT")],
        "SANDESH": [("SCHEME_REORGANISATION", "ACTIVE_FORWARD_STAGE", "SCHEME_REORGANISATION")],
        "SUVIDHAA": [("RIGHTS_ISSUE", "ACTIVE_FORWARD_STAGE", "RIGHTS_ISSUE")],
        "TREL": [("SCHEME_REORGANISATION", "PROCEDURAL_STAGE", "SCHEME_REORGANISATION")],
    }
    state = {
        symbol: (
            "PROCEDURAL_DIRECT_REVIEW"
            if any(stage == "PROCEDURAL_STAGE" for _, stage, _ in rows)
            else "ACTIVE_DIRECT_CATALYST"
        )
        for symbol, rows in clusters.items()
    }
    l002_rows = []
    for symbol in SYMBOLS:
        company_clusters = []
        for semantic, stage, upstream in clusters[symbol]:
            company_clusters.append(
                {
                    "semantic_cluster": semantic,
                    "relevance_group": "CURRENT_ECONOMIC_RELEVANCE",
                    "stage_group": stage,
                    "latest_transaction_stage": "PROPOSAL",
                    "latest_thread_id": f"{symbol}::{upstream}",
                    "member_thread_ids": [f"{symbol}::{upstream}"],
                }
            )
        l002_rows.append(
            {
                "symbol": symbol,
                "company_catalyst_state": state[symbol],
                "clusters": company_clusters,
            }
        )
    # Add excluded clusters to prove selection obeys state/relevance rules.
    l002_rows[5]["clusters"].append(
        {
            "semantic_cluster": "SCHEME_REORGANISATION",
            "relevance_group": "CURRENT_ECONOMIC_RELEVANCE",
            "stage_group": "COMPLETED_STAGE",
            "latest_transaction_stage": "TRANSACTION_COMPLETED",
            "latest_thread_id": "INOXGREEN::SCHEME_REORGANISATION",
            "member_thread_ids": ["INOXGREEN::SCHEME_REORGANISATION"],
        }
    )
    l002_rows[-1]["clusters"].append(
        {
            "semantic_cluster": "FUND_RAISE_OTHER",
            "relevance_group": "INDIRECT_RELEVANCE",
            "stage_group": "COMPLETED_STAGE",
            "latest_transaction_stage": "ALLOTMENT_COMPLETED",
            "latest_thread_id": "TREL::PREFERENTIAL_WARRANT",
            "member_thread_ids": ["TREL::PREFERENTIAL_WARRANT"],
        }
    )
    hg003 = {
        "synthesis_id": "HG003-L002-v1",
        "synthesis_sha256": (
            "ebe3b8f666a83b18695eca69c649ab6c66d721f157ebe6ed0d61e71ef4f937ea"
        ),
        "rows": l002_rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }

    event_counts = {
        "ANANTRAJ": 2,
        "AXITA": 1,
        "DATAMATICS": 1,
        "DEVX": 3,
        "FCL": 2,
        "INOXGREEN": 3,
        "NPST": 1,
        "SAMBHV": 2,
        "SANDESH": 1,
        "SUVIDHAA": 2,
        "TREL": 2,
    }
    upstream = {
        symbol: clusters[symbol][0][2] for symbol in SYMBOLS
    }
    events = []
    manifests = []
    records = []
    doc_counter = 0
    shared_suvidhaa_doc = None
    for symbol in SYMBOLS:
        for index in range(event_counts[symbol]):
            event_id = f"{symbol}-E{index}"
            if symbol == "SUVIDHAA":
                if shared_suvidhaa_doc is None:
                    shared_suvidhaa_doc = "d" * 63 + "1"
                document_id = shared_suvidhaa_doc
            else:
                doc_counter += 1
                document_id = f"{doc_counter:064x}"[-64:]
            events.append(
                {
                    "announcement_id": event_id,
                    "symbol": symbol,
                    "mapping_state": "CURRENT_INVESTABLE_IDENTITY",
                    "special_situation_categories": [upstream[symbol]],
                    "exchange_published_at_utc": f"2026-07-{index + 1:02d}T10:00:00Z",
                }
            )
            existing = next(
                (row for row in manifests if row["document_id"] == document_id),
                None,
            )
            if existing is None:
                segment = _segment(document_id)
                manifest_sha = hashlib.sha256(
                    f"manifest-{document_id}".encode()
                ).hexdigest()
                manifest = {
                    "document_id": document_id,
                    "source_url": f"https://nsearchives.nseindia.com/{document_id}.pdf",
                    "extraction_state": "READY",
                    "event_ids": [event_id],
                    "symbols": [symbol],
                    "categories": [upstream[symbol]],
                    "segment_manifest_sha256": manifest_sha,
                }
                manifests.append(manifest)
                records.append(
                    {
                        **manifest,
                        "segments": [segment],
                    }
                )
            else:
                existing["event_ids"].append(event_id)
                rec = next(row for row in records if row["document_id"] == document_id)
                rec["event_ids"].append(event_id)

    assert len(events) == 20
    assert len(manifests) == 19

    p2 = {
        "census_id": "SS002-D001-P2-v1",
        "census_sha256": (
            "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"
        ),
        "events": events,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    d3 = {
        "corpus_id": "SS002-D003-v1",
        "corpus_sha256": (
            "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"
        ),
        "document_count": len(manifests),
        "documents": manifests,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return hg003, p2, d3, records


def test_hg004_selects_complete_active_and_procedural_threads() -> None:
    hg003, p2, d3, records = _sources()
    result = select_hg004_detailed_terms(hg003, p2, d3, records)
    assert result["symbol_count"] == 11
    assert result["semantic_cluster_count"] == 11
    assert result["event_link_count"] == 20
    assert result["unique_document_count"] == 19
    assert result["feasibility_pass"] is True
    assert len(result["prompts"]) == 19
    assert all(row["prompt_envelope"] for row in result["prompts"])


def test_shared_document_deduplicates_prompt_but_keeps_both_events() -> None:
    hg003, p2, d3, records = _sources()
    result = select_hg004_detailed_terms(hg003, p2, d3, records)
    suvidhaa = [
        row for row in result["prompts"] if row["symbols"] == ["SUVIDHAA"]
    ]
    assert len(suvidhaa) == 1
    assert len(suvidhaa[0]["event_ids"]) == 2


def test_completed_and_indirect_clusters_do_not_enter_hg004() -> None:
    hg003, p2, d3, records = _sources()
    result = select_hg004_detailed_terms(hg003, p2, d3, records)
    clusters = set(result["cluster_event_counts"])
    assert "INOXGREEN::SCHEME_REORGANISATION" not in clusters
    assert "TREL::FUND_RAISE_OTHER" not in clusters


def test_changed_frozen_company_set_fails_closed() -> None:
    hg003, p2, d3, records = _sources()
    hg003["rows"] = [
        row for row in hg003["rows"] if row["symbol"] != "ANANTRAJ"
    ]
    with pytest.raises(AlphaContractError, match="frozen 11-symbol set"):
        select_hg004_detailed_terms(hg003, p2, d3, records)
