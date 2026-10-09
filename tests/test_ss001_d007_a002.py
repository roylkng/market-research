from __future__ import annotations

import hashlib

import pytest

from marketlab import ss001_d007_a002 as a002
from marketlab.alpha import AlphaContractError


def _page(doc: str, symbol: str, index: int, text: str) -> dict:
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "request_id": f"{doc}:request:{index:03d}",
        "document_id": doc,
        "symbol": symbol,
        "segment_order": index,
        "segment_id": f"{doc}:page:{index:03d}",
        "prompt_envelope": {
            "request": {
                "segments": [
                    {
                        "segment_id": f"{doc}:page:{index:03d}",
                        "text": text,
                        "text_sha256": sha,
                    }
                ]
            }
        },
    }


def test_document_sample_is_source_only_and_covers_capital_entity_cases() -> None:
    pages = [
        _page("D1", "ABC", 1, "Generic financial update."),
        _page("D1", "ABC", 2, "The subsidiary will acquire the undertaking."),
        _page("D1", "ABC", 3, "Equity share capital after allotment."),
        _page("D1", "ABC", 4, "Record date and other details."),
        _page("D1", "ABC", 5, "Thank you."),
    ]
    selection = a002._sample_document(pages)
    assert "FIRST" in selection[pages[0]["request_id"]]
    assert "LAST" in selection[pages[-1]["request_id"]]
    assert "MIDDLE" in selection[pages[2]["request_id"]]
    assert "MULTI_ENTITY_LANGUAGE" in selection[pages[1]["request_id"]]
    assert "CAPITAL_LANGUAGE" in selection[pages[2]["request_id"]]
    assert sum("HASH_CONTROL" in codes for codes in selection.values()) == 1


def test_single_page_document_is_one_selection_with_multiple_reasons() -> None:
    page = _page("D1", "ABC", 1, "No capital change.")
    selection = a002._sample_document([page])
    assert len(selection) == 1
    assert set(selection[page["request_id"]]) == {
        "FIRST", "LAST", "MIDDLE", "HASH_CONTROL"
    }


def test_duplicate_segment_orders_fail_closed() -> None:
    pages = [
        _page("D1", "ABC", 1, "First"),
        {**_page("D1", "ABC", 2, "Second"), "segment_order": 1},
    ]
    with pytest.raises(AlphaContractError, match="duplicate page order"):
        a002._sample_document(pages)


def _synthetic_queue_and_rows() -> tuple[dict, list[dict]]:
    records = []
    descriptions = []
    symbols = [
        "JAYKAY", "INDIAGLYCO", "HEGAM", "IITL", "ORBTEXP", "PVRINOX",
        "GANDHITUBE", "RATNAVEER", "TEAMLEASE", "TRIVENI", "DUCON",
        "INOXGREEN",
    ]
    for i in range(70):
        doc = f"document-{i:02d}"
        symbol = symbols[i % 12]
        count = 18 if i < 50 else 17
        descriptions.append({
            "document_id": doc,
            "symbol": symbol,
            "d003_segment_count": count,
        })
        for number in range(1, count + 1):
            text = (
                "A subsidiary issued shares."
                if number == 2 else "The company disclosed current facts."
            )
            record = _page(doc, symbol, number, text)
            record.update({
                "global_request_index": len(records) + 1,
                "issuer_packet_rank": i % 12 + 1,
                "shard_id": len(records) % 16,
                "prompt_sha256": hashlib.sha256(record["request_id"].encode()).hexdigest(),
            })
            records.append(record)
    assert len(records) == 1240
    return {"issuer_count": 12, "fresh_documents": descriptions}, records


def test_full_selection_covers_all_70_documents_and_12_issuers(monkeypatch) -> None:
    queue, rows = _synthetic_queue_and_rows()
    monkeypatch.setattr(a002, "validate_queue", lambda _: rows)
    selection = a002.build_a002_selection(queue)
    assert selection["source_request_count"] == 1240
    assert selection["selected_document_count"] == 70
    assert selection["selected_issuer_count"] == 12
    assert 70 <= selection["selected_page_count"] <= 420
    assert len({row["request_id"] for row in selection["selection"]}) == (
        selection["selected_page_count"]
    )
    assert selection["selection_reason_counts"]["MULTI_ENTITY_LANGUAGE"] == 70
    assert selection["model_inference_executed"] is False
    assert selection["share_action_clearance_proven"] is False
    assert selection["live_capital_allowed"] is False


def test_review_packet_rejects_source_sample_tampering(monkeypatch) -> None:
    queue, rows = _synthetic_queue_and_rows()
    monkeypatch.setattr(a002, "validate_queue", lambda _: rows)
    selection = a002.build_a002_selection(queue)
    selection["selection"][0]["segment_text_sha256"] = "faked"
    with pytest.raises(AlphaContractError, match="audit selection"):
        a002.build_a002_review_packet(queue, selection, {}, [])


def test_review_packet_never_auto_approves_missing_model_outputs(monkeypatch) -> None:
    queue, rows = _synthetic_queue_and_rows()
    monkeypatch.setattr(a002, "validate_queue", lambda _: rows)
    monkeypatch.setattr(
        a002,
        "build_collection_status",
        lambda _q, _c, _r: {
            "collection_sha256": "a" * 64,
            "runtime_model_config_sha256": "b" * 64,
        },
    )
    selection = a002.build_a002_selection(queue)
    packet = a002.build_a002_review_packet(queue, selection, {}, [])
    assert packet["pending_selected_response_count"] == (
        selection["selected_page_count"]
    )
    assert packet["response_coverage_complete"] is False
    assert all(row["response_status"] == "MISSING_INFERENCE" for row in packet["rows"])
    assert all(row["independent_review_status"] == "NOT_STARTED" for row in packet["rows"])
    assert packet["independent_semantic_audit_complete"] is False
    assert packet["market_capitalization_calculated"] is False
