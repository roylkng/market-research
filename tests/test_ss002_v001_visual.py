from __future__ import annotations

import copy

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_p009_visual_review import (
    STATUS_CORRUPTED,
    STATUS_PRESENT,
    STATUS_UNEXTRACTED,
)
from marketlab.ss002_v001_visual import (
    QUEUE_ID,
    build_visual_fallback_queue,
    build_visual_prompt,
    validate_visual_transcription,
)


def _source() -> tuple[dict, dict]:
    cases = []
    views = []
    for symbol, count in (("INOXGREEN", 6), ("KOTHARIPET", 2), ("OLAELEC", 2), ("VRLLOG", 7)):
        docid = {"INOXGREEN": "a", "KOTHARIPET": "b", "OLAELEC": "c", "VRLLOG": "d"}[symbol] * 64
        url = f"https://nsearchives.nseindia.com/{symbol}.pdf"
        page_rows = []
        image_rows = []
        for n in range(1, count + 1):
            status = STATUS_PRESENT
            if symbol == "VRLLOG" and 2 <= n <= 5:
                status = STATUS_CORRUPTED
            if symbol == "VRLLOG" and n in (6, 7):
                status = STATUS_UNEXTRACTED
            seg = f"seg-{symbol}-{n}" if status != STATUS_UNEXTRACTED else None
            page_rows.append({"page_number": n, "legibility_status": status})
            image_rows.append({
                "page_number": n,
                "legibility_status": status,
                "source_segment_id": seg,
                "image_sha256": f"{n:064x}",
                "relative_image_path": f"visual/{symbol}/page-{n:04d}.jpg",
            })
        cases.append({
            "symbol": symbol,
            "document_id": docid,
            "official_nse_url": url,
            "original_pdf_raw_sha256": docid,
            "original_pdf_page_count": count,
            "pages": page_rows,
        })
        views.append({
            "symbol": symbol,
            "document_id": docid,
            "official_nse_url": url,
            "original_pdf_sha256": docid,
            "page_images": image_rows,
        })
    p009 = {
        "pack_id": "SS002-P009-v1",
        "pack_sha256": "750cbe9d5a3b7be7664bb4db32f2a5da899f0760ad054fda3457d805ebd6bdbc",
        "source_p008_pack_sha256": "94b098d24ef6c5eb3482ce4c79ec696c24a6f761a4bc0f3fe6e0e5ae7f985768",
        "original_page_count": 17,
        "cases": cases,
        "independent_semantic_audit_complete": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    manifest = {
        "render_id": "SS002-P009-VISUAL-v1",
        "visual_manifest_sha256": "6d7644392ccf3d5ced1dde4e6b696b802ece8f7e86932d2724d00fc075baeb44",
        "source_p009_pack_sha256": p009["pack_sha256"],
        "rendered_page_count": 17,
        "case_manifests": views,
        "independent_semantic_review_complete": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return p009, manifest


def _visual_response(request: dict) -> dict:
    return {
        "schema_version": 1,
        "contract_id": QUEUE_ID,
        "request_id": request["request_id"],
        "symbol": request["symbol"],
        "document_id": request["document_id"],
        "page_number": request["page_number"],
        "image_sha256": request["image_sha256"],
        "page_status": "TEXT_VISIBLE",
        "transcriptions": [{
            "original_text": "VRL LOGISTICS LIMITED",
            "language_code": "en",
            "english_translation": None,
            "bbox_1000": [60, 40, 860, 240],
            "uncertainty": "CLEAR",
        }],
        "uncertainties": [],
        "reviewer_questions": [],
        "provenance": {
            "provider_runtime": "TEST_ONLY",
            "model_id": "vision-test",
            "model_config_sha256": "a" * 64,
            "prompt_sha256": request["prompt_sha256"],
            "input_image_sha256": request["image_sha256"],
            "raw_model_response_sha256": "b" * 64,
        },
    }


def test_visual_queue_is_exactly_six_sha_bound_vrl_pages() -> None:
    q = build_visual_fallback_queue(*_source())
    assert q["request_count"] == 6
    assert [row["page_number"] for row in q["requests"]] == [2, 3, 4, 5, 6, 7]
    assert {row["symbol"] for row in q["requests"]} == {"VRLLOG"}
    assert q["model_inference_completed"] is False
    assert q["portfolio_eligibility_allowed"] is False
    assert q["live_capital_allowed"] is False
    prompt = build_visual_prompt(q["requests"][0])
    assert prompt["prompt_sha256"] == q["requests"][0]["prompt_sha256"]


def test_tampered_image_identity_fails_closed() -> None:
    p009, manifest = _source()
    manifest["case_manifests"][-1]["page_images"][1]["image_sha256"] = "wrong"
    with pytest.raises(AlphaContractError, match="invalid image SHA"):
        build_visual_fallback_queue(p009, manifest)


def test_vision_output_is_a_pending_source_hypothesis() -> None:
    request = build_visual_fallback_queue(*_source())["requests"][0]
    result = validate_visual_transcription(_visual_response(request), request=request)
    assert len(result["validated_output_sha256"]) == 64
    assert result["independent_semantic_audit_complete"] is False
    assert result["portfolio_eligibility_allowed"] is False


def test_vision_output_rejects_invented_investment_advice() -> None:
    request = build_visual_fallback_queue(*_source())["requests"][0]
    response = _visual_response(request)
    response["expected_return"] = 0.8
    with pytest.raises(AlphaContractError, match="forbidden investment fields"):
        validate_visual_transcription(response, request=request)


def test_invalid_visual_bbox_and_wrong_image_fail_closed() -> None:
    request = build_visual_fallback_queue(*_source())["requests"][0]
    response = _visual_response(request)
    response["transcriptions"][0]["bbox_1000"] = [900, 100, 50, 500]
    with pytest.raises(AlphaContractError, match="bounding box invalid"):
        validate_visual_transcription(response, request=request)
    response = copy.deepcopy(_visual_response(request))
    response["image_sha256"] = "0" * 64
    with pytest.raises(AlphaContractError, match="image_sha256"):
        validate_visual_transcription(response, request=request)
