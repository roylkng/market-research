from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss001_l001_batch import (
    SOURCE_QUEUE_SHA,
    SOURCE_REQUEST_COUNT,
    build_collection_status,
    validate_config,
    validate_queue,
)

LEDGER_ID = "SS001-D007-L002-v1"
P1_RUN_ID = "SS001-D007-L001-P1-GPT56SOL-NATIVE-v1"
P1_RUN_SHA = "1a3a2f73eaed8ba09c84ab7c8d60699fa895f39d25d5797bd16138b09fd620cb"
P1_MODEL_SHA = "133b5705036d1782f671d6a171fe5f24298939cf6d84314875c2e8452e7169dc"
EXPECTED_ISSUERS = (
    "JAYKAY", "INDIAGLYCO", "HEGAM", "IITL", "ORBTEXP", "PVRINOX",
    "GANDHITUBE", "RATNAVEER", "TEAMLEASE", "TRIVENI", "DUCON", "INOXGREEN",
)
EXPECTED_DOCUMENTS = 82
EXPECTED_REUSED = 12
EXPECTED_FRESH = 70
EXPECTED_ACTIONS = 12
CLOSED_FIELDS = (
    "share_action_clearance_proven",
    "market_capitalization_calculated",
    "return_outcomes_opened",
    "portfolio_eligibility_allowed",
    "live_capital_allowed",
)


def _closed(record: dict[str, Any], label: str) -> None:
    for field in CLOSED_FIELDS:
        if record.get(field) is not False:
            raise AlphaContractError(f"L002 {label} must have {field}=false")


def _strict_hash(payload: dict[str, Any], sha_field: str, label: str) -> None:
    if payload.get(sha_field) != digest({k: v for k, v in payload.items() if k != sha_field}):
        raise AlphaContractError(f"L002 {label} SHA mismatch")


def _p1_index(p1: dict[str, Any], queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if p1.get("run_id") != P1_RUN_ID or p1.get("run_sha256") != P1_RUN_SHA:
        raise AlphaContractError("L002 P1 run identity mismatch")
    _strict_hash(p1, "run_sha256", "P1 native run")
    if p1.get("model_config_sha256") != P1_MODEL_SHA:
        raise AlphaContractError("L002 P1 model config mismatch")
    _closed(p1, "P1 source")
    records = p1.get("rows")
    reused = queue.get("reused_documents")
    if not isinstance(records, list) or len(records) != EXPECTED_REUSED:
        raise AlphaContractError("L002 requires 12 P1 native extractions")
    if not isinstance(reused, list) or len(reused) != EXPECTED_REUSED:
        raise AlphaContractError("L002 requires 12 frozen reused document descriptions")
    by_doc = {row.get("document_id"): row for row in records if isinstance(row, dict)}
    if len(by_doc) != EXPECTED_REUSED:
        raise AlphaContractError("L002 P1 document identity is not unique")
    for desc in reused:
        doc_id = desc["document_id"]
        row = by_doc.get(doc_id)
        if row is None:
            raise AlphaContractError(f"L002 missing P1 extraction for {doc_id}")
        for actual, expected, field in (
            (row.get("symbol"), desc["symbol"], "symbol"),
            (row.get("issuer_packet_rank"), desc["issuer_packet_rank"], "issuer rank"),
            (row.get("prompt_sha256"), desc["p1_prompt_sha256"], "prompt SHA"),
            (row.get("model_config_sha256"), desc["p1_model_config_sha256"], "model SHA"),
            (row.get("segment_manifest_sha256"), desc["d003_segment_manifest_sha256"], "segment SHA"),
            (row.get("raw_model_response_sha256"), desc["p1_raw_model_response_sha256"], "response SHA"),
        ):
            if actual != expected:
                raise AlphaContractError(f"L002 P1 {field} mismatch: {doc_id}")
        if row.get("source_event_id") not in desc["q002_event_ids"]:
            raise AlphaContractError("L002 P1 source event identity mismatch")
        extraction = row.get("validated_extraction")
        if not isinstance(extraction, dict):
            raise AlphaContractError("L002 P1 validated extraction missing")
        if extraction.get("validated_structured_output_sha256") != desc[
            "p1_validated_structured_output_sha256"
        ]:
            raise AlphaContractError("L002 P1 validated output SHA mismatch")
        if set(extraction.get("event_ids") or []) != set(desc["q002_event_ids"]):
            raise AlphaContractError("L002 P1 event set mismatch")
        if extraction.get("document_id") != doc_id or desc["symbol"] not in (
            extraction.get("symbols") or []
        ):
            raise AlphaContractError("L002 P1 extraction identity mismatch")
        _closed(extraction, "P1 validated extraction")
        stripped = {
            k: v for k, v in extraction.items()
            if k not in {
                "validated_structured_output_sha256",
                "return_outcomes_opened",
                "portfolio_eligibility_allowed",
                "live_capital_allowed",
            }
        }
        if digest(stripped) != extraction["validated_structured_output_sha256"]:
            raise AlphaContractError("L002 P1 structured output was modified")
    return by_doc


def _claims(extraction: dict[str, Any], *, request_id: str | None) -> list[dict[str, Any]]:
    facts = extraction.get("facts")
    if not isinstance(facts, dict):
        raise AlphaContractError("L002 extraction missing fact families")
    claims: list[dict[str, Any]] = []
    for family in sorted(facts):
        block = facts[family]
        if not isinstance(block, dict):
            raise AlphaContractError("L002 extraction fact family malformed")
        for field in sorted(block):
            fact = block[field]
            if not isinstance(fact, dict):
                raise AlphaContractError("L002 extraction fact malformed")
            if fact.get("status") != "EXPLICIT":
                continue
            evidence = fact.get("evidence_segment_ids")
            if not isinstance(evidence, list) or not evidence:
                raise AlphaContractError("L002 explicit fact has no source evidence")
            claims.append(
                {
                    "field_path": f"{family}.{field}",
                    "value": fact["value"],
                    "unit": fact.get("unit"),
                    "evidence_segment_ids": evidence,
                    "request_id": request_id,
                }
            )
    return claims


def _page_record(
    extraction: dict[str, Any],
    *,
    request_id: str | None,
    segment_id: str | None,
    model_cohort: str,
) -> dict[str, Any]:
    if not isinstance(extraction, dict):
        raise TypeError("L002 validated extraction must be an object")
    return {
        "request_id": request_id,
        "segment_id": segment_id,
        "model_cohort": model_cohort,
        "economic_relevance": extraction.get("economic_relevance"),
        "transaction_families": extraction.get("transaction_families"),
        "transaction_stage": extraction.get("transaction_stage"),
        "claims": _claims(extraction, request_id=request_id),
        "unresolved_questions": extraction.get("unresolved_questions"),
        "contradictions_within_document": extraction.get("contradictions_within_document"),
        "extraction_caveats": extraction.get("extraction_caveats"),
        "validated_output_sha256": extraction.get("validated_structured_output_sha256"),
    }


def build_issuer_evidence(
    queue: dict[str, Any],
    p1_run: dict[str, Any],
    *,
    runtime_config: dict[str, Any] | None = None,
    validated_r001_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fresh_requests = validate_queue(queue)
    if tuple(queue.get("issuer_symbols") or ()) != EXPECTED_ISSUERS:
        raise AlphaContractError("L002 frozen issuer order changed")
    if queue.get("distinct_document_count") != EXPECTED_DOCUMENTS:
        raise AlphaContractError("L002 total document count mismatch")
    if queue.get("p1_reuse_document_count") != EXPECTED_REUSED:
        raise AlphaContractError("L002 P1 document count mismatch")
    if queue.get("fresh_document_count") != EXPECTED_FRESH:
        raise AlphaContractError("L002 fresh document count mismatch")
    if queue.get("corporate_action_row_count") != EXPECTED_ACTIONS:
        raise AlphaContractError("L002 frozen action evidence count mismatch")

    p1 = _p1_index(p1_run, queue)
    r001 = validated_r001_rows or []
    if r001 and runtime_config is None:
        raise AlphaContractError("L002 R001 extractions require a pinned runtime configuration")
    runtime_sha = validate_config(runtime_config) if runtime_config else None
    if r001:
        status = build_collection_status(queue, runtime_config, r001)
    else:
        status = None

    by_request = {r["request_id"]: r for r in r001}
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for request in fresh_requests:
        by_document[request["document_id"]].append(request)
    frozen_docs = queue["fresh_documents"] + queue["reused_documents"]
    if len(frozen_docs) != EXPECTED_DOCUMENTS:
        raise AlphaContractError("L002 frozen document list length mismatch")
    if len({d["document_id"] for d in frozen_docs}) != EXPECTED_DOCUMENTS:
        raise AlphaContractError("L002 frozen documents are not unique")
    if len(r001) > SOURCE_REQUEST_COUNT:
        raise AlphaContractError("L002 model output count exceeds frozen requests")
    if set(by_request) - {r["request_id"] for r in fresh_requests}:
        raise AlphaContractError("L002 unexpected R001 request")

    action_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for action in queue["corporate_action_evidence"]:
        action_by_symbol[action["symbol"]].append(action)
    if sum(map(len, action_by_symbol.values())) != EXPECTED_ACTIONS:
        raise AlphaContractError("L002 corporate-action evidence count mismatch")

    issuer_documents: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for desc in frozen_docs:
        document_id = desc["document_id"]
        symbol = desc["symbol"]
        if symbol not in EXPECTED_ISSUERS:
            raise AlphaContractError("L002 document has unregistered issuer")
        raw_requests = sorted(
            by_document.get(document_id, []),
            key=lambda row: row["segment_order"],
        )
        pages: list[dict[str, Any]] = []
        missing_count = 0
        if desc["execution_state"] == "P1_REUSE":
            extraction = p1[document_id]["validated_extraction"]
            pages.append(
                _page_record(
                    extraction,
                    request_id=None,
                    segment_id=None,
                    model_cohort="P1_NATIVE_GPT56SOL",
                )
            )
            if raw_requests:
                raise AlphaContractError("L002 reused document has fresh requests")
        elif desc["execution_state"] == "FRESH_PAGE_REQUESTS":
            if len(raw_requests) != desc["d003_segment_count"]:
                raise AlphaContractError("L002 document page accounting mismatch")
            for request in raw_requests:
                if request["symbol"] != symbol:
                    raise AlphaContractError("L002 page symbol differs from document")
                sealed = by_request.get(request["request_id"])
                if sealed is None:
                    missing_count += 1
                    continue
                if sealed["document_id"] != document_id:
                    raise AlphaContractError("L002 page document binding mismatch")
                pages.append(
                    _page_record(
                        sealed["validated_extraction"],
                        request_id=request["request_id"],
                        segment_id=request["segment_id"],
                        model_cohort="R001_API_" + str(runtime_sha),
                    )
                )
        else:
            raise AlphaContractError("L002 unknown frozen document execution state")

        issuer_documents[symbol].append(
            {
                "document_id": document_id,
                "document_order": desc["document_order"],
                "execution_state": desc["execution_state"],
                "source_url": desc["source_url"],
                "source_event_ids": desc["q002_event_ids"],
                "source_category_hints": desc["d003_categories"],
                "source_segment_manifest_sha256": desc["d003_segment_manifest_sha256"],
                "expected_page_count": desc["d003_segment_count"],
                "validated_extraction_count": len(pages),
                "missing_fresh_page_count": missing_count,
                "extractions": pages,
            }
        )

    issuer_rows: list[dict[str, Any]] = []
    for rank, symbol in enumerate(EXPECTED_ISSUERS, start=1):
        documents = sorted(
            issuer_documents[symbol],
            key=lambda doc: (doc["document_order"], doc["document_id"]),
        )
        if not documents:
            raise AlphaContractError(f"L002 issuer has no documents: {symbol}")
        claims_by_field: dict[str, set[str]] = defaultdict(set)
        relevance_states: Counter[str] = Counter()
        model_states: Counter[str] = Counter()
        contradiction_count = 0
        expected_fresh = validated_fresh = 0
        for doc in documents:
            if doc["execution_state"] == "FRESH_PAGE_REQUESTS":
                expected_fresh += doc["expected_page_count"]
                validated_fresh += len(doc["extractions"])
            for item in doc["extractions"]:
                relevance_states[str(item["economic_relevance"])] += 1
                model_states[str(item["model_cohort"])] += 1
                contradiction_count += len(item["contradictions_within_document"] or [])
                for claim in item["claims"]:
                    claims_by_field[claim["field_path"]].add(
                        json.dumps(
                            [claim["value"], claim["unit"]],
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                            allow_nan=False,
                        )
                    )
        multiple_values = sorted(
            name for name, values in claims_by_field.items() if len(values) > 1
        )
        flags = []
        if validated_fresh < expected_fresh:
            flags.append("UNRESOLVED_SOURCE_COVERAGE")
        if multiple_values:
            flags.append("MULTIPLE_EXPLICIT_VALUES_REVIEW")
        if relevance_states["DIRECT_LISTED_SECURITY"]:
            flags.append("DIRECT_SECURITY_RELEVANCE_REVIEW")
        if len(model_states) > 1:
            flags.append("MIXED_MODEL_COHORTS")
        if contradiction_count:
            flags.append("SOURCE_CONFLICT_REVIEW")

        issuer_rows.append(
            {
                "issuer_packet_rank": rank,
                "symbol": symbol,
                "document_count": len(documents),
                "expected_fresh_page_count": expected_fresh,
                "validated_fresh_page_count": validated_fresh,
                "missing_fresh_page_count": expected_fresh - validated_fresh,
                "relevance_state_counts": dict(sorted(relevance_states.items())),
                "model_cohort_counts": dict(sorted(model_states.items())),
                "multiple_explicit_value_field_paths": multiple_values,
                "extraction_self_reported_contradiction_count": contradiction_count,
                "review_flags": sorted(flags),
                "documents": documents,
                "corporate_action_evidence": action_by_symbol[symbol],
                "semantic_audit_status": "PENDING_INDEPENDENT_REVIEW",
                "share_action_clearance_proven": False,
                "market_capitalization_calculated": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    fresh_count = sum(row["validated_fresh_page_count"] for row in issuer_rows)
    if fresh_count != len(r001):
        raise AlphaContractError("L002 assembled page count differs from validated responses")
    if sum(row["document_count"] for row in issuer_rows) != EXPECTED_DOCUMENTS:
        raise AlphaContractError("L002 assembled document count mismatch")
    if sum(len(row["corporate_action_evidence"]) for row in issuer_rows) != EXPECTED_ACTIONS:
        raise AlphaContractError("L002 assembled corporate actions mismatch")

    output = {
        "schema_version": 1,
        "ledger_id": LEDGER_ID,
        "classification": "EVIDENCE_BOUND_ISSUER_REVIEW_LEDGER_NOT_SHARE_CLEARANCE",
        "source_queue_sha256": SOURCE_QUEUE_SHA,
        "source_p1_run_sha256": P1_RUN_SHA,
        "runtime_model_config_sha256": runtime_sha,
        "runtime_source_model_equivalence_claimed": False,
        "issuer_count": len(issuer_rows),
        "document_count": EXPECTED_DOCUMENTS,
        "prior_native_document_count": EXPECTED_REUSED,
        "fresh_document_count": EXPECTED_FRESH,
        "fresh_request_count": SOURCE_REQUEST_COUNT,
        "fresh_validated_response_count": fresh_count,
        "fresh_remaining_response_count": SOURCE_REQUEST_COUNT - fresh_count,
        "corporate_action_row_count": EXPECTED_ACTIONS,
        "status": (
            "COMPLETE_EVIDENCE_PENDING_SEMANTIC_AUDIT"
            if fresh_count == SOURCE_REQUEST_COUNT
            else "PARTIAL_EVIDENCE_PENDING_MODEL_OUTPUT"
        ),
        "prior_native_inference_reused": True,
        "fresh_model_inference_executed": fresh_count > 0,
        "semantic_audit_complete": False,
        "issuer_rows": issuer_rows,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["ledger_sha256"] = digest(output)
    return output
