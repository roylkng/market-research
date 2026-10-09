from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss001_l001_batch import (
    SOURCE_QUEUE_SHA,
    SOURCE_REQUEST_COUNT,
    build_collection_status,
    validate_config,
    validate_queue,
)

AUDIT_ID = "SS001-D007-A002-v1"
EXPECTED_FRESH_DOCUMENTS = 70
EXPECTED_ISSUERS = 12
CAPITAL_TERMS = (
    "issued share capital",
    "equity share capital",
    "equity shares",
    "rights entitlement",
    "share swap",
    "capital reduction",
    "preferential allotment",
    "warrants",
    "exercise price",
)
ENTITY_TERMS = (
    "subsidiary",
    "demerged",
    "transferee",
    "resulting company",
    "associate company",
    "group company",
    "target company",
)
CLOSED_FIELDS = (
    "share_action_clearance_proven",
    "market_capitalization_calculated",
    "return_outcomes_opened",
    "portfolio_eligibility_allowed",
    "live_capital_allowed",
)


def _closed(row: dict[str, Any], label: str) -> None:
    for field in CLOSED_FIELDS:
        if row.get(field) is not False:
            raise AlphaContractError(f"A002 {label} requires {field}=false")


def _page_text(row: dict[str, Any]) -> str:
    envelope = row.get("prompt_envelope")
    request = envelope.get("request") if isinstance(envelope, dict) else None
    segments = request.get("segments") if isinstance(request, dict) else None
    if not isinstance(segments, list) or len(segments) != 1:
        raise AlphaContractError("A002 original page evidence is unavailable")
    segment = segments[0]
    if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
        raise AlphaContractError("A002 original page text is unavailable")
    return segment["text"]


def _normalized_text(row: dict[str, Any]) -> str:
    return " ".join(_page_text(row).casefold().split())


def _sample_document(requests: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Pure, result-blind sample of one document's original pages."""
    if not requests:
        raise AlphaContractError("A002 cannot sample an empty document")
    ordered = sorted(requests, key=lambda row: (row["segment_order"], row["request_id"]))
    orders = [row["segment_order"] for row in ordered]
    if any(isinstance(order, bool) or not isinstance(order, int) for order in orders):
        raise AlphaContractError("A002 segment orders must be integers")
    if len(set(orders)) != len(orders):
        raise AlphaContractError("A002 duplicate page order in document")

    reasons: dict[str, set[str]] = defaultdict(set)

    def add(row: dict[str, Any], reason: str) -> None:
        reasons[row["request_id"]].add(reason)

    add(ordered[0], "FIRST")
    add(ordered[-1], "LAST")
    add(ordered[(len(ordered) - 1) // 2], "MIDDLE")
    hash_control = min(
        ordered,
        key=lambda row: (
            hashlib.sha256(row["request_id"].encode("utf-8")).hexdigest(),
            row["request_id"],
        ),
    )
    add(hash_control, "HASH_CONTROL")

    for label, needles in (
        ("CAPITAL_LANGUAGE", CAPITAL_TERMS),
        ("MULTI_ENTITY_LANGUAGE", ENTITY_TERMS),
    ):
        for row in ordered:
            text = _normalized_text(row)
            if any(needle in text for needle in needles):
                add(row, label)
                break

    return {key: sorted(values) for key, values in reasons.items()}


def build_a002_selection(queue: dict[str, Any]) -> dict[str, Any]:
    requests = validate_queue(queue)
    frozen_docs = queue.get("fresh_documents")
    if not isinstance(frozen_docs, list) or len(frozen_docs) != EXPECTED_FRESH_DOCUMENTS:
        raise AlphaContractError("A002 requires frozen 70 fresh document descriptions")
    if queue.get("issuer_count") != EXPECTED_ISSUERS:
        raise AlphaContractError("A002 frozen issuer count changed")

    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in requests:
        by_document[row["document_id"]].append(row)
    described = {row["document_id"] for row in frozen_docs}
    if len(described) != EXPECTED_FRESH_DOCUMENTS or set(by_document) != described:
        raise AlphaContractError("A002 document IDs differ from frozen source queue")

    selected: list[dict[str, Any]] = []
    per_issuer: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for document in frozen_docs:
        document_id = document["document_id"]
        symbol = document["symbol"]
        pages = by_document[document_id]
        if len(pages) != document["d003_segment_count"]:
            raise AlphaContractError("A002 document page count differs from frozen source")
        if any(page["symbol"] != symbol for page in pages):
            raise AlphaContractError("A002 document issuer mismatch")

        sampled = _sample_document(pages)
        for page in sorted(pages, key=lambda row: (row["segment_order"], row["request_id"])):
            codes = sampled.get(page["request_id"])
            if not codes:
                continue
            envelope = page["prompt_envelope"]["request"]
            source_segment = envelope["segments"][0]
            selected.append(
                {
                    "request_id": page["request_id"],
                    "global_request_index": page["global_request_index"],
                    "issuer_packet_rank": page["issuer_packet_rank"],
                    "symbol": symbol,
                    "document_id": document_id,
                    "segment_id": page["segment_id"],
                    "segment_order": page["segment_order"],
                    "shard_id": page["shard_id"],
                    "prompt_sha256": page["prompt_sha256"],
                    "segment_text_sha256": source_segment["text_sha256"],
                    "selection_reason_codes": codes,
                }
            )
            per_issuer[symbol] += 1
            reasons.update(codes)

    if len(requests) != SOURCE_REQUEST_COUNT:
        raise AlphaContractError("A002 frozen request count changed")
    if len(per_issuer) != EXPECTED_ISSUERS:
        raise AlphaContractError("A002 selection does not cover all 12 issuers")
    if not EXPECTED_FRESH_DOCUMENTS <= len(selected) <= EXPECTED_FRESH_DOCUMENTS * 6:
        raise AlphaContractError("A002 selected page count outside frozen bound")
    if len({row["request_id"] for row in selected}) != len(selected):
        raise AlphaContractError("A002 selected request identity is duplicated")

    result = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "PRE_REGISTERED_SOURCE_ONLY_SEMANTIC_AUDIT_SAMPLE",
        "source_queue_sha256": SOURCE_QUEUE_SHA,
        "source_request_count": SOURCE_REQUEST_COUNT,
        "source_fresh_document_count": EXPECTED_FRESH_DOCUMENTS,
        "source_issuer_count": EXPECTED_ISSUERS,
        "selected_page_count": len(selected),
        "selected_document_count": len(described),
        "selected_issuer_count": len(per_issuer),
        "selected_pages_by_issuer": dict(sorted(per_issuer.items())),
        "selection_reason_counts": dict(sorted(reasons.items())),
        "selection": selected,
        "model_inference_executed": False,
        "independent_semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["selection_sha256"] = digest(result)
    return result


def read_r001_validated_receipts(
    queue: dict[str, Any],
    config: dict[str, Any],
    root: Path,
) -> list[dict[str, Any]]:
    """Read immutable R001 attempt receipts, refusing ambiguous accepted outputs."""
    requests = validate_queue(queue)
    config_sha = validate_config(config)
    config_path = root / "run-config.json"
    if not config_path.is_file():
        raise AlphaContractError("A002 pinned R001 run-config receipt is missing")
    pinned = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(pinned, dict):
        raise TypeError("A002 pinned run-config must be an object")
    if (
        pinned.get("runtime_model_config_sha256") != config_sha
        or pinned.get("model_config") != config
    ):
        raise AlphaContractError("A002 R001 configuration differs from pinned receipt")

    collected: list[dict[str, Any]] = []
    for row in requests:
        path = (
            root / "requests" / f"shard-{int(row['shard_id']):02d}"
            / str(row["request_id"])
        )
        accepted = []
        for receipt_path in sorted(path.glob("attempt-[0-9][0-9][0-9].json")):
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if not isinstance(receipt, dict):
                raise TypeError("A002 attempt receipt must be an object")
            raw = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
            if receipt.get("receipt_sha256") != digest(raw):
                raise AlphaContractError("A002 R001 attempt receipt SHA mismatch")
            if (
                receipt.get("request_id") != row["request_id"]
                or receipt.get("runtime_model_config_sha256") != config_sha
            ):
                raise AlphaContractError("A002 R001 attempt receipt identity mismatch")
            if receipt.get("status") == "VALIDATED":
                accepted.append(receipt.get("sealed"))
        if len(accepted) > 1:
            raise AlphaContractError("A002 multiple accepted R001 attempts for one request")
        if accepted:
            if not isinstance(accepted[0], dict):
                raise TypeError("A002 accepted R001 response must be an object")
            collected.append(accepted[0])
    return collected


def build_a002_review_packet(
    queue: dict[str, Any],
    selection: dict[str, Any],
    runtime_config: dict[str, Any],
    validated_receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = build_a002_selection(queue)
    if selection != expected:
        raise AlphaContractError("A002 audit selection does not match frozen source-only rule")
    collection = build_collection_status(queue, runtime_config, validated_receipts)
    receipts = {row["request_id"]: row for row in validated_receipts}
    requests = {row["request_id"]: row for row in validate_queue(queue)}

    audit_rows: list[dict[str, Any]] = []
    pending = 0
    for selected in selection["selection"]:
        source = requests[selected["request_id"]]
        receipt = receipts.get(selected["request_id"])
        if receipt is None:
            pending += 1
            state = "MISSING_INFERENCE"
            extraction = None
        else:
            state = "PENDING_INDEPENDENT_REVIEW"
            extraction = receipt["validated_extraction"]

        explicit_facts = []
        if extraction is not None:
            for family, block in extraction["facts"].items():
                for field, fact in block.items():
                    if fact["status"] == "EXPLICIT":
                        explicit_facts.append({
                            "field_path": f"{family}.{field}",
                            "value": fact["value"],
                            "unit": fact["unit"],
                            "evidence_segment_ids": fact["evidence_segment_ids"],
                        })

        audit_rows.append({
            **selected,
            "source_page_text": _page_text(source),
            "source_page_text_sha256": selected["segment_text_sha256"],
            "runtime_model_config_sha256": collection["runtime_model_config_sha256"],
            "response_status": state,
            "validated_extraction_sha256": (
                extraction["validated_structured_output_sha256"] if extraction else None
            ),
            "economic_relevance": extraction["economic_relevance"] if extraction else None,
            "transaction_families": extraction["transaction_families"] if extraction else None,
            "transaction_stage": extraction["transaction_stage"] if extraction else None,
            "explicit_facts": sorted(explicit_facts, key=lambda row: row["field_path"]),
            "unresolved_questions": extraction["unresolved_questions"] if extraction else [],
            "contradictions_within_document": (
                extraction["contradictions_within_document"] if extraction else []
            ),
            "extraction_caveats": extraction["extraction_caveats"] if extraction else [],
            "independent_review_status": "NOT_STARTED",
            "material_claims_verified": False,
        })

    packet = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "INDEPENDENT_REVIEW_WORK_PACKET_NOT_AUDIT_VERDICT",
        "source_queue_sha256": SOURCE_QUEUE_SHA,
        "selection_sha256": selection["selection_sha256"],
        "collection_sha256": collection["collection_sha256"],
        "runtime_model_config_sha256": collection["runtime_model_config_sha256"],
        "selected_page_count": len(audit_rows),
        "selected_model_response_count": len(audit_rows) - pending,
        "pending_selected_response_count": pending,
        "response_coverage_complete": pending == 0,
        "rows": audit_rows,
        "independent_semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = digest(packet)
    return packet
