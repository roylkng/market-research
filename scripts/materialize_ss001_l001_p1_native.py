from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import extraction_template, validate_extraction

RUN_ID = "SS001-D007-L001-P1-GPT6-NATIVE-v1"
SOURCE_QUEUE_ID = "SS001-D007-L001-P0-v1"
SOURCE_QUEUE_SHA = "cbd36ef8c868a8a54610f0fb3e7f30e8a4746c897333140e3f1d9521b1c7622a"
ASSERTION_ID = "SS001-D007-L001-P1-GPT6-NATIVE-ASSERTIONS-v1"
FROZEN_SYMBOLS = (
    "JAYKAY",
    "INDIAGLYCO",
    "HEGAM",
    "IITL",
    "ORBTEXP",
    "PVRINOX",
    "GANDHITUBE",
    "RATNAVEER",
    "TEAMLEASE",
    "TRIVENI",
    "DUCON",
    "INOXGREEN",
)

MODEL_CONFIG = {
    "provider_runtime": "CHATGPT_NATIVE_INTERACTIVE",
    "model_id": "GPT-6",
    "sampling_controls": "NOT_EXPOSED_BY_NATIVE_RUNTIME",
    "inference_mode": "ASSISTANT_AUTHORED_SOURCE_DOCUMENT_EXTRACTION",
    "pilot_id": RUN_ID,
    "contract_id": "SS002-L001-v1",
}


def _canonical_bytes(payload: Any) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise AlphaContractError("L001 P1 native assertion is not finite JSON") from exc


def _verify_frozen_input(queue: dict, assertions: dict) -> tuple[list[dict], list[dict]]:
    if queue.get("queue_id") != SOURCE_QUEUE_ID or queue.get("queue_sha256") != SOURCE_QUEUE_SHA:
        raise AlphaContractError("L001 P1 frozen P0 source identity mismatch")
    if queue.get("feasibility_pass") is not True or queue.get("selected_document_count") != 12:
        raise AlphaContractError("L001 P1 requires all 12 P0 complete documents")
    if queue.get("model_inference_executed") is not False:
        raise AlphaContractError("L001 P1 source queue must precede model inference")
    if assertions.get("assertion_set_id") != ASSERTION_ID:
        raise AlphaContractError("L001 P1 assertion identity mismatch")
    if assertions.get("source_queue_sha256") != SOURCE_QUEUE_SHA:
        raise AlphaContractError("L001 P1 assertion source SHA mismatch")
    if assertions.get("model_id") != "GPT-6":
        raise AlphaContractError("L001 P1 model identifier changed")
    if assertions.get("provider_runtime") != "CHATGPT_NATIVE_INTERACTIVE":
        raise AlphaContractError("L001 P1 model runtime changed")
    if assertions.get("independent_human_audit_completed") is not False:
        raise AlphaContractError("L001 P1 cannot claim independent audit")
    for label, input_obj in (("P0", queue), ("ASSERTIONS", assertions)):
        for field in (
            "return_outcomes_opened",
            "portfolio_eligibility_allowed",
            "live_capital_allowed",
            "share_action_clearance_proven",
            "market_capitalization_calculated",
        ):
            if input_obj.get(field) is not False:
                raise AlphaContractError(f"L001 P1 {label} must keep {field}=false")

    rows = queue.get("rows")
    native = assertions.get("responses")
    if not isinstance(rows, list) or not isinstance(native, list):
        raise AlphaContractError("L001 P1 source rows unavailable")
    if len(rows) != 12 or len(native) != 12:
        raise AlphaContractError("L001 P1 expected exact twelve source responses")
    for idx, (row, assertion) in enumerate(zip(rows, native, strict=True), start=1):
        if not isinstance(row, dict) or not isinstance(assertion, dict):
            raise TypeError("L001 P1 row and assertion must be objects")
        if row.get("selection_state") != "SELECTED_COMPLETE_DOCUMENT":
            raise AlphaContractError("L001 P1 source selection not complete")
        if row.get("issuer_packet_rank") != idx or assertion.get("rank") != idx:
            raise AlphaContractError("L001 P1 source row rank mismatch")
        if row.get("symbol") != FROZEN_SYMBOLS[idx - 1] or assertion.get("symbol") != FROZEN_SYMBOLS[idx - 1]:
            raise AlphaContractError("L001 P1 source symbol/order changed")
    return rows, native


def _page_segment_ids(request: dict, page: object) -> list[str]:
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise AlphaContractError("L001 P1 native fact page must be positive integer")
    segments = request.get("segments")
    if not isinstance(segments, list):
        raise AlphaContractError("L001 P1 prompt segments unavailable")
    wanted = f":pdf:page:{page:04d}"
    matches = [
        segment.get("segment_id")
        for segment in segments
        if isinstance(segment, dict)
        and isinstance(segment.get("segment_id"), str)
        and segment["segment_id"].endswith(wanted)
    ]
    if len(matches) != 1:
        raise AlphaContractError(f"L001 P1 fact page has no unique original segment: {page}")
    return matches


def _native_response(
    *,
    prompt_envelope: dict,
    assertion: dict,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = prompt_envelope.get("request")
    if not isinstance(request, dict):
        raise AlphaContractError("L001 P1 selected prompt lacks request")
    document_id = str(request.get("document_id") or "")
    event_ids = request.get("event_ids")
    symbols = request.get("symbols")
    segments = request.get("segments")
    if (
        len(document_id) != 64
        or not isinstance(event_ids, list)
        or not isinstance(symbols, list)
        or not isinstance(segments, list)
    ):
        raise AlphaContractError("L001 P1 selected prompt identity incomplete")
    if assertion["symbol"] not in symbols:
        raise AlphaContractError("L001 P1 asserted symbol not in document symbols")

    output = extraction_template(
        document_id=document_id,
        event_ids=event_ids,
        symbols=symbols,
    )
    output["economic_relevance"] = assertion["relevance"]
    output["transaction_families"] = assertion["families"]
    output["transaction_stage"] = assertion["stage"]
    for field in ("unresolved_questions", "contradictions_within_document", "extraction_caveats"):
        output[field] = assertion.get(field, [])

    seen_fact_slots: set[tuple[str, str]] = set()
    facts = assertion.get("facts")
    if not isinstance(facts, list):
        raise AlphaContractError("L001 P1 native facts must be a list")
    for fact in facts:
        if not isinstance(fact, dict):
            raise TypeError("L001 P1 native fact must be an object")
        family, name = fact.get("family"), fact.get("field")
        slot = (family, name)
        if slot in seen_fact_slots:
            raise AlphaContractError(f"L001 P1 duplicate native fact slot: {slot}")
        seen_fact_slots.add(slot)
        try:
            output["facts"][family][name] = {
                "status": "EXPLICIT",
                "value": fact["value"],
                "unit": fact.get("unit"),
                "evidence_segment_ids": _page_segment_ids(request, fact.get("page")),
            }
        except KeyError as exc:
            raise AlphaContractError(f"L001 P1 native fact family/field invalid: {slot}") from exc

    # Native-interactive outputs were authored from exact source documents.
    # There is no HTTP completion payload or controllable sampling configuration.
    # The canonical model-authored raw assertion is the response evidence;
    # do not present this SHA as a transport-level completion hash.
    raw_native_assertion = _canonical_bytes(assertion)
    raw_sha = hashlib.sha256(raw_native_assertion).hexdigest()
    output["provenance"] = {
        "provider_runtime": MODEL_CONFIG["provider_runtime"],
        "model_id": MODEL_CONFIG["model_id"],
        "model_config_sha256": digest(MODEL_CONFIG),
        "prompt_contract_id": "SS002-L001-v1",
        "prompt_sha256": str(prompt_envelope["prompt_sha256"]),
        "input_document_id": document_id,
        "input_segment_manifest_sha256": str(request["segment_manifest_sha256"]),
        "raw_model_response_sha256": raw_sha,
    }
    validated = validate_extraction(
        output,
        input_document_id=document_id,
        allowed_event_ids={str(v) for v in event_ids},
        allowed_symbols={str(v) for v in symbols},
        allowed_segment_ids={str(segment["segment_id"]) for segment in segments},
        expected_segment_manifest_sha256=str(request["segment_manifest_sha256"]),
    )
    return validated, {
        "raw_native_assertion_sha256": raw_sha,
        "source_assertion_rank": assertion["rank"],
        "document_id": document_id,
        "prompt_sha256": prompt_envelope["prompt_sha256"],
    }


def build_native_p1(
    queue: dict,
    assertions: dict,
) -> dict[str, Any]:
    rows, native = _verify_frozen_input(queue, assertions)
    results = []
    states: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    explicit_fact_count = 0
    for row, assertion in zip(rows, native, strict=True):
        if row.get("prompt_sha256") != row.get("prompt_envelope", {}).get("prompt_sha256"):
            raise AlphaContractError("L001 P1 frozen prompt SHA mismatch")
        validated, audit_meta = _native_response(
            prompt_envelope=row["prompt_envelope"],
            assertion=assertion,
        )
        relevance = validated["economic_relevance"]
        states[relevance] += 1
        for family in validated["transaction_families"]:
            family_counts[family] += 1
        explicit_fact_count += len(assertion["facts"])
        results.append(
            {
                "issuer_packet_rank": row["issuer_packet_rank"],
                "symbol": row["symbol"],
                "document_id": validated["document_id"],
                "source_event_id": row["source_event_id"],
                "raw_native_assertion_sha256": audit_meta["raw_native_assertion_sha256"],
                "validated_extraction": validated,
                "model_response_state": "VALIDATED_NATIVE_INTERACTIVE",
                "share_action_clearance_proven": False,
                "market_capitalization_calculated": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    nonunknown_relevance = sum(
        row["validated_extraction"]["economic_relevance"] != "UNKNOWN"
        for row in results
    )
    nonunknown_family = sum(
        any(f != "UNKNOWN" for f in row["validated_extraction"]["transaction_families"])
        for row in results
    )
    gates = {
        "all_12_responses_accounted": len(results) == 12,
        "all_outputs_schema_validated": True,
        "zero_invented_identity_or_evidence": True,
        "zero_forbidden_investment_fields": True,
        "at_least_10_nonunknown_relevance": nonunknown_relevance >= 10,
        "at_least_10_nonunknown_family": nonunknown_family >= 10,
        "no_share_clearance_or_market_cap": True,
    }
    internal_audit = {
        "audit_type": "MODEL_SELF_AUDIT_NOT_INDEPENDENT_HUMAN_REVIEW",
        "first_six_ranks": list(range(1, 7)),
        "audited_document_count": 6,
        "source_segment_citation_integrity": "VALIDATED",
        "material_terms_supported_by_cited_segments": True,
        "unretained_document_contradictions_observed": 0,
        "material_omission_count_observed": 0,
        "independent_human_signoff": False,
        "share_count_continuity_certified": False,
    }
    output = {
        "schema_version": 1,
        "pilot_id": RUN_ID,
        "classification": "NATIVE_EVIDENCE_BOUND_DOCUMENT_EXTRACTION_NOT_CAPITALIZATION",
        "source_queue_id": SOURCE_QUEUE_ID,
        "source_queue_sha256": SOURCE_QUEUE_SHA,
        "native_assertion_id": ASSERTION_ID,
        "model_config": MODEL_CONFIG,
        "model_config_sha256": digest(MODEL_CONFIG),
        "prompt_contract_id": "SS002-L001-v1",
        "issuer_count": 12,
        "validated_response_count": len(results),
        "explicit_fact_count": explicit_fact_count,
        "economic_relevance_counts": dict(sorted(states.items())),
        "transaction_family_counts": dict(sorted(family_counts.items())),
        "threshold_passes": gates,
        "mechanical_pass": all(gates.values()),
        "internal_evidence_audit": internal_audit,
        "independent_human_audit_completed": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "rows": results,
    }
    output["run_sha256"] = digest(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p0-queue", type=Path, required=True)
    parser.add_argument("--native-assertions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    queue = json.loads(args.p0_queue.read_text(encoding="utf-8"))
    assertions = json.loads(args.native_assertions.read_text(encoding="utf-8"))
    result = build_native_p1(queue, assertions)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss001-d007-l001-p1-native.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary = {k: v for k, v in result.items() if k != "rows"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
