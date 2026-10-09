from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import (
    CONTRACT_ID,
    FACT_FIELDS,
    build_prompt_envelope,
    extraction_template,
    validate_extraction,
)
from marketlab.ss002_text import seal_extraction_row

PILOT_ID = "SS002-P004-NATIVE-8DOC-v1"
SOURCE_CORPUS_ID = "SS002-P003-v1"
SOURCE_CORPUS_SHA = "7abbe52043b7ef3de89cb617d4fba2b181c3d8c4978df7a29ea557eab54469f7"
RUNTIME_ID = "CHATGPT_NATIVE_INTERACTIVE_MANUAL_TRANSCRIPTION"
MODEL_ID = "GPT-6"
PILOT_DOCUMENT_IDS = (
    "f4aa6bc559658aae64da1540b6683e5d46ed3c68a0be1d11948cb1fb0d4b6a24",
    "fa31ca687e2b419813879d464990117b5f8917abd1006c5dec7ecae1a8da1058",
    "f8a46405d8b7c10bc12f47c945b5cc96956600273fc5868edbd004baa4808b92",
    "432611a5ca2aafd37ae11b6435ff8eda8c6652d5be2f2888fed47cbee92d41b1",
    "541277b2c8a6d732bc77e62c6b637c98b92a5044dddeac09e34038d8d4d5d451",
    "17ff4dbc9d62243ffb7ccc3ca78a903eecb3991bf091e27030f384fe725bf891",
    "6e9ef61a11d6a47a771e6d9ec255507cd14104016a5baa682317bef3c206baf5",
    "f619d7a5473c6e34268f2aaf1440b7276ec807789c04fa6a8481ba4ab3d10659",
)

MODEL_CONFIG = {
    "runtime": RUNTIME_ID,
    "model_id": MODEL_ID,
    "interpretation_mode": "native source-reading, manually transcribed sparse L001 facts",
    "prompt_provenance": (
        "canonical envelope reconstructed for validation, not a claim that hidden "
        "interactive prompt equals an isolated API request"
    ),
}


def _canonical_sha(value: Any) -> str:
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("SS002 P004 requires finite canonical JSON") from exc
    return hashlib.sha256(raw).hexdigest()


def _validate_source(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if corpus.get("corpus_id") != SOURCE_CORPUS_ID:
        raise AlphaContractError("SS002 P004 source corpus identity mismatch")
    if corpus.get("corpus_sha256") != SOURCE_CORPUS_SHA:
        raise AlphaContractError("SS002 P004 source corpus SHA mismatch")
    if digest({k: v for k, v in corpus.items() if k != "corpus_sha256"}) != SOURCE_CORPUS_SHA:
        raise AlphaContractError("SS002 P004 source corpus contents fail SHA verification")
    if corpus.get("source_event_count") != 54 or corpus.get("current_document_event_count") != 36:
        raise AlphaContractError("SS002 P004 source event accounting mismatch")
    for field in (
        "model_inference_executed",
        "economic_relevance_verified",
        "return_outcomes_opened",
        "market_capitalization_calculated",
        "share_action_clearance_proven",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if corpus.get(field) is not False:
            raise AlphaContractError(f"SS002 P004 source requires {field}=false")
    documents = corpus.get("documents")
    if not isinstance(documents, list):
        raise TypeError("SS002 P004 source documents must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for doc in documents:
        if not isinstance(doc, dict):
            raise TypeError("SS002 P004 source document must be an object")
        doc_id = doc.get("document_id")
        if doc_id is None:
            continue
        if not isinstance(doc_id, str):
            raise TypeError("SS002 P004 document ID must be a string")
        if doc_id in indexed:
            if doc.get("raw_sha256") != indexed[doc_id].get("raw_sha256"):
                raise AlphaContractError("SS002 P004 conflicting duplicate document ID")
            continue
        indexed[doc_id] = doc
    return indexed


def _validate_text(doc_id: str, extraction: dict[str, Any]) -> dict[int, str]:
    if extraction.get("document_id") != doc_id or extraction.get("extraction_state") != "READY":
        raise AlphaContractError("SS002 P004 document extraction identity/readiness mismatch")
    original = {k: v for k, v in extraction.items() if k != "segment_manifest_sha256"}
    sealed = seal_extraction_row(original)
    if sealed["segment_manifest_sha256"] != extraction.get("segment_manifest_sha256"):
        raise AlphaContractError("SS002 P004 source text segment manifest SHA mismatch")
    pages: dict[int, str] = {}
    segments = extraction.get("segments")
    if not isinstance(segments, list) or not segments:
        raise AlphaContractError("SS002 P004 source text segments are unavailable")
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            raise TypeError("SS002 P004 source segment must be an object")
        if _canonical_text_sha(segment["text"]) != segment.get("text_sha256"):
            raise AlphaContractError("SS002 P004 segment text SHA mismatch")
        locator = segment.get("locator")
        page = locator.get("page_number") if isinstance(locator, dict) else None
        seg_id = segment.get("segment_id")
        if not isinstance(page, int) or isinstance(page, bool) or not isinstance(seg_id, str):
            raise AlphaContractError("SS002 P004 requires page-addressable text segments")
        if page in pages:
            raise AlphaContractError("SS002 P004 ambiguous page segment identity")
        pages[page] = seg_id
    return pages


def _canonical_text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def materialize_one(
    decision: dict[str, Any],
    *,
    source: dict[str, Any],
    extraction: dict[str, Any],
) -> dict[str, Any]:
    doc_id = decision.get("document_id")
    if doc_id != source.get("document_id"):
        raise AlphaContractError("SS002 P004 decision/source document identity mismatch")
    if source.get("status") != "READY" or source.get("extraction_state") != "READY":
        raise AlphaContractError("SS002 P004 selected document must be text-ready")
    if source.get("segment_manifest_sha256") != extraction.get("segment_manifest_sha256"):
        raise AlphaContractError("SS002 P004 source segment manifest mismatch")
    symbols = source.get("symbols")
    events = source.get("event_ids")
    categories = source.get("category_hints_only")
    if (
        not isinstance(symbols, list)
        or not isinstance(events, list)
        or not isinstance(categories, list)
        or symbols != [decision.get("symbol")]
    ):
        raise AlphaContractError("SS002 P004 source event/symbol identity mismatch")
    if decision.get("semantic_audit_status") != "PENDING_INDEPENDENT_SOURCE_REVIEW":
        raise AlphaContractError("SS002 P004 semantic audit must remain pending")
    page_index = _validate_text(doc_id, extraction)

    template = extraction_template(
        document_id=doc_id,
        event_ids=events,
        symbols=symbols,
    )
    for key in ("economic_relevance", "transaction_families", "transaction_stage"):
        template[key] = decision.get(key)
    for key in (
        "unresolved_questions",
        "contradictions_within_document",
        "extraction_caveats",
    ):
        template[key] = decision.get(key)

    facts = decision.get("facts")
    if not isinstance(facts, list):
        raise TypeError("SS002 P004 native facts must be a list")
    seen_facts: set[tuple[str, str]] = set()
    for row in facts:
        if not isinstance(row, list) or len(row) != 5:
            raise AlphaContractError("SS002 P004 fact must be [family,field,value,unit,pages]")
        family, field, value, unit, page_numbers = row
        if family not in FACT_FIELDS or field not in FACT_FIELDS[family]:
            raise AlphaContractError(f"SS002 P004 unsupported fact path: {family}.{field}")
        if (family, field) in seen_facts:
            raise AlphaContractError(f"SS002 P004 repeated fact: {family}.{field}")
        seen_facts.add((family, field))
        if value is None or isinstance(value, bool):
            raise AlphaContractError("SS002 P004 explicit fact requires non-bool value")
        if (
            not isinstance(page_numbers, list)
            or not page_numbers
            or len(page_numbers) != len(set(page_numbers))
        ):
            raise AlphaContractError("SS002 P004 fact must cite distinct source pages")
        try:
            segment_ids = [page_index[page] for page in page_numbers]
        except KeyError as exc:
            raise AlphaContractError("SS002 P004 fact cites unavailable page") from exc
        template["facts"][family][field] = {
            "status": "EXPLICIT",
            "value": value,
            "unit": unit,
            "evidence_segment_ids": segment_ids,
        }

    prompt = build_prompt_envelope(
        document_id=doc_id,
        source_url=source["source_url"],
        event_ids=events,
        symbols=symbols,
        category_hints=categories,
        segments=extraction["segments"],
        segment_manifest_sha256=extraction["segment_manifest_sha256"],
    )
    template["provenance"] = {
        "provider_runtime": RUNTIME_ID,
        "model_id": MODEL_ID,
        "model_config_sha256": _canonical_sha(MODEL_CONFIG),
        "prompt_contract_id": CONTRACT_ID,
        "prompt_sha256": prompt["prompt_sha256"],
        "input_document_id": doc_id,
        "input_segment_manifest_sha256": extraction["segment_manifest_sha256"],
        "raw_model_response_sha256": _canonical_sha(decision),
    }
    validated = validate_extraction(
        template,
        input_document_id=doc_id,
        allowed_event_ids=set(events),
        allowed_symbols=set(symbols),
        allowed_segment_ids=set(page_index.values()),
        expected_segment_manifest_sha256=extraction["segment_manifest_sha256"],
    )
    return {
        "symbol": symbols[0],
        "document_id": doc_id,
        "source_url": source["source_url"],
        "event_ids": events,
        "category_hints_only": categories,
        "case_assessment": decision.get("case_assessment"),
        "semantic_audit_status": decision["semantic_audit_status"],
        "explicit_fact_count": len(seen_facts),
        "validated_extraction": validated,
    }


def build_native_pilot(
    corpus: dict[str, Any],
    decisions: dict[str, Any],
    extraction_by_document: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_docs = _validate_source(corpus)
    if (
        decisions.get("pilot_id") != PILOT_ID
        or decisions.get("provider_runtime") != RUNTIME_ID
        or decisions.get("model_id") != MODEL_ID
    ):
        raise AlphaContractError("SS002 P004 frozen native decision identity mismatch")
    for field in ("return_outcomes_opened", "portfolio_eligibility_allowed", "live_capital_allowed"):
        if decisions.get(field) is not False:
            raise AlphaContractError(f"SS002 P004 decision {field} must be false")
    rows = decisions.get("document_rows")
    if not isinstance(rows, list) or len(rows) != 8:
        raise AlphaContractError("SS002 P004 requires exactly 8 decisions")
    ids = tuple(row.get("document_id") for row in rows if isinstance(row, dict))
    if ids != PILOT_DOCUMENT_IDS:
        raise AlphaContractError("SS002 P004 frozen document selection/order mismatch")

    outputs = []
    for index, decision in enumerate(rows, start=1):
        if decision.get("pilot_order") != index:
            raise AlphaContractError("SS002 P004 pilot_order is not canonical")
        doc_id = decision["document_id"]
        if doc_id not in source_docs or doc_id not in extraction_by_document:
            raise AlphaContractError("SS002 P004 selected source evidence missing")
        outputs.append(
            materialize_one(
                decision,
                source=source_docs[doc_id],
                extraction=extraction_by_document[doc_id],
            )
        )

    relevance = Counter(
        row["validated_extraction"]["economic_relevance"] for row in outputs
    )
    stages = Counter(
        row["validated_extraction"]["transaction_stage"] for row in outputs
    )
    summary = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "classification": "NATIVE_LLM_DOCUMENT_INTERPRETATION_PILOT_NOT_ALPHA",
        "source_corpus_id": SOURCE_CORPUS_ID,
        "source_corpus_sha256": SOURCE_CORPUS_SHA,
        "model_runtime": RUNTIME_ID,
        "model_id": MODEL_ID,
        "prompt_provenance_limitation": MODEL_CONFIG["prompt_provenance"],
        "selected_document_count": len(outputs),
        "structurally_validated_document_count": len(outputs),
        "independently_semantically_audited_document_count": 0,
        "explicit_fact_count": sum(row["explicit_fact_count"] for row in outputs),
        "economic_relevance_counts": dict(sorted(relevance.items())),
        "transaction_stage_counts": dict(sorted(stages.items())),
        "cases": outputs,
        "return_outcomes_opened": False,
        "market_capitalization_calculated": False,
        "share_action_clearance_proven": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    summary["pilot_sha256"] = digest(summary)
    return summary
