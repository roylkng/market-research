from __future__ import annotations

import json
from typing import Any

from marketlab.alpha import AlphaContractError, digest

CONTRACT_ID="HG006-L001-v1"

STAGES=frozenset({
    "PROPOSAL",
    "BOARD_APPROVED",
    "SHAREHOLDER_APPROVED",
    "REGULATORY_OR_COURT_APPROVED",
    "PUBLIC_ANNOUNCEMENT",
    "RECORD_DATE_FIXED",
    "OFFER_OPEN",
    "OFFER_CLOSED",
    "ALLOTMENT_COMPLETED",
    "WARRANT_EXERCISE_OR_CONVERSION_COMPLETED",
    "TRANSACTION_COMPLETED",
    "CANCELLED_OR_WITHDRAWN",
    "PROCEDURAL_UPDATE",
    "UNKNOWN",
})

TERMINAL_LANGUAGE=frozenset({
    "NO_EXPLICIT_TERMINAL_LANGUAGE",
    "EXPLICIT_COMPLETION_LANGUAGE",
    "EXPLICIT_FAILURE_OR_WITHDRAWAL_LANGUAGE",
    "CONFLICTING_TERMINAL_LANGUAGE",
})

ANCHOR_TYPES=frozenset({
    "BOARD_APPROVAL_DATE",
    "SHAREHOLDER_APPROVAL_DATE",
    "RECORD_DATE",
    "OFFER_OPEN_DATE",
    "OFFER_CLOSE_DATE",
    "EFFECTIVE_DATE",
    "REGULATORY_OR_COURT_ORDER_DATE",
    "ACQUIRER_OR_OFFEROR",
    "TARGET_OR_TRANSFEROR",
    "TRANSFEREE_OR_RESULTING_ENTITY",
    "OFFER_OR_ISSUE_PRICE",
    "SECURITY_COUNT",
    "OFFER_OR_ISSUE_SIZE",
    "ENTITLEMENT_OR_EXCHANGE_RATIO",
    "SCHEME_OR_TRANSACTION_NAME",
    "CASE_ORDER_REFERENCE",
    "ALLOTTEE_OR_ALLOTTEE_GROUP",
    "SECURITY_TYPE",
    "OTHER_EXPLICIT_TRANSACTION_REFERENCE",
})

FORBIDDEN_KEYS=frozenset({
    "completion_probability",
    "expected_return",
    "target_price",
    "intrinsic_value",
    "buy",
    "sell",
    "hold",
    "portfolio_weight",
    "historical_stock_return",
    "hidden_gem_rank",
})


def _canonical(payload: Any)->bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",",":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError,ValueError) as exc:
        raise AlphaContractError("HG006 L001 output must be finite JSON") from exc


def _walk_keys(value: Any)->list[str]:
    result=[]
    if isinstance(value,dict):
        for key,child in value.items():
            result.append(str(key))
            result.extend(_walk_keys(child))
    elif isinstance(value,list):
        for child in value:
            result.extend(_walk_keys(child))
    return result


def extraction_template(
    *,
    document_id:str,
    event_ids:list[str],
    symbol:str,
    family:str,
)->dict[str,Any]:
    return {
        "schema_version":1,
        "contract_id":CONTRACT_ID,
        "document_id":document_id,
        "event_ids":sorted(event_ids),
        "symbol":symbol,
        "family":family,
        "stage_observations":[],
        "explicit_terminal_language":"NO_EXPLICIT_TERMINAL_LANGUAGE",
        "terminal_evidence_segment_ids":[],
        "transaction_anchors":[],
        "family_semantic_conflict":None,
        "unresolved_questions":[],
        "contradictions_within_document":[],
        "extraction_caveats":[],
        "provenance":{
            "provider_runtime":"",
            "model_id":"",
            "model_config_sha256":"",
            "prompt_contract_id":CONTRACT_ID,
            "prompt_sha256":"",
            "input_document_id":document_id,
            "input_segment_manifest_sha256":"",
            "raw_model_response_sha256":"",
        },
    }


def _validate_evidence(
    evidence: Any,
    *,
    allowed:set[str],
    field:str,
    require:bool,
)->list[str]:
    if not isinstance(evidence,list) or not all(isinstance(x,str) for x in evidence):
        raise AlphaContractError(f"{field}: evidence must be string list")
    if len(evidence)!=len(set(evidence)):
        raise AlphaContractError(f"{field}: duplicate evidence IDs")
    unknown=set(evidence)-allowed
    if unknown:
        raise AlphaContractError(f"{field}: unknown evidence IDs {sorted(unknown)}")
    if require and not evidence:
        raise AlphaContractError(f"{field}: explicit claim requires evidence")
    return evidence


def validate_extraction(
    output:dict[str,Any],
    *,
    document_id:str,
    event_ids:set[str],
    symbol:str,
    family:str,
    allowed_segment_ids:set[str],
    segment_manifest_sha256:str,
)->dict[str,Any]:
    _canonical(output)
    forbidden=sorted(
        key for key in _walk_keys(output) if key.casefold() in FORBIDDEN_KEYS
    )
    if forbidden:
        raise AlphaContractError(f"HG006 L001 forbidden fields: {forbidden}")

    if output.get("schema_version")!=1 or output.get("contract_id")!=CONTRACT_ID:
        raise AlphaContractError("HG006 L001 contract identity mismatch")
    if output.get("document_id")!=document_id:
        raise AlphaContractError("HG006 L001 document identity mismatch")
    if set(output.get("event_ids") or [])!=event_ids:
        raise AlphaContractError("HG006 L001 event identity mismatch")
    if output.get("symbol")!=symbol or output.get("family")!=family:
        raise AlphaContractError("HG006 L001 symbol/family identity mismatch")

    stages=output.get("stage_observations")
    if not isinstance(stages,list):
        raise AlphaContractError("HG006 L001 stage observations must be list")
    for index,row in enumerate(stages):
        if not isinstance(row,dict):
            raise TypeError("HG006 L001 stage observation must be object")
        if set(row)!={"stage","evidence_segment_ids"}:
            raise AlphaContractError("HG006 L001 stage observation keys differ")
        if row.get("stage") not in STAGES:
            raise AlphaContractError("HG006 L001 invalid stage")
        _validate_evidence(
            row.get("evidence_segment_ids"),
            allowed=allowed_segment_ids,
            field=f"stage_observations[{index}]",
            require=row.get("stage")!="UNKNOWN",
        )

    terminal=output.get("explicit_terminal_language")
    if terminal not in TERMINAL_LANGUAGE:
        raise AlphaContractError("HG006 L001 invalid terminal-language state")
    terminal_evidence=_validate_evidence(
        output.get("terminal_evidence_segment_ids"),
        allowed=allowed_segment_ids,
        field="terminal_evidence_segment_ids",
        require=terminal!="NO_EXPLICIT_TERMINAL_LANGUAGE",
    )
    if terminal=="NO_EXPLICIT_TERMINAL_LANGUAGE" and terminal_evidence:
        raise AlphaContractError("HG006 L001 non-terminal document cannot cite terminal evidence")

    anchors=output.get("transaction_anchors")
    if not isinstance(anchors,list):
        raise AlphaContractError("HG006 L001 transaction anchors must be list")
    for index,row in enumerate(anchors):
        if not isinstance(row,dict):
            raise TypeError("HG006 L001 transaction anchor must be object")
        if set(row)!={"anchor_type","value","evidence_segment_ids"}:
            raise AlphaContractError("HG006 L001 anchor keys differ from contract")
        if row.get("anchor_type") not in ANCHOR_TYPES:
            raise AlphaContractError("HG006 L001 invalid anchor type")
        if row.get("value") in (None,""):
            raise AlphaContractError("HG006 L001 explicit anchor requires value")
        _validate_evidence(
            row.get("evidence_segment_ids"),
            allowed=allowed_segment_ids,
            field=f"transaction_anchors[{index}]",
            require=True,
        )

    conflict=output.get("family_semantic_conflict")
    if conflict is not None:
        if not isinstance(conflict,dict):
            raise TypeError("HG006 L001 family conflict must be object or null")
        if set(conflict)!={"description","evidence_segment_ids"}:
            raise AlphaContractError("HG006 L001 family conflict keys differ")
        if not isinstance(conflict.get("description"),str) or not conflict["description"].strip():
            raise AlphaContractError("HG006 L001 family conflict requires description")
        _validate_evidence(
            conflict.get("evidence_segment_ids"),
            allowed=allowed_segment_ids,
            field="family_semantic_conflict",
            require=True,
        )

    for field in (
        "unresolved_questions",
        "contradictions_within_document",
        "extraction_caveats",
    ):
        value=output.get(field)
        if not isinstance(value,list) or not all(isinstance(x,str) for x in value):
            raise AlphaContractError(f"HG006 L001 {field} must be string list")

    provenance=output.get("provenance")
    required={
        "provider_runtime",
        "model_id",
        "model_config_sha256",
        "prompt_contract_id",
        "prompt_sha256",
        "input_document_id",
        "input_segment_manifest_sha256",
        "raw_model_response_sha256",
    }
    if not isinstance(provenance,dict) or set(provenance)!=required:
        raise AlphaContractError("HG006 L001 provenance keys differ")
    if any(not isinstance(provenance[key],str) or not provenance[key] for key in required):
        raise AlphaContractError("HG006 L001 provenance values must be non-empty")
    if provenance["prompt_contract_id"]!=CONTRACT_ID:
        raise AlphaContractError("HG006 L001 prompt contract mismatch")
    if provenance["input_document_id"]!=document_id:
        raise AlphaContractError("HG006 L001 provenance document mismatch")
    if provenance["input_segment_manifest_sha256"]!=segment_manifest_sha256:
        raise AlphaContractError("HG006 L001 segment manifest mismatch")

    sealed=dict(output)
    sealed["validated_structured_output_sha256"]=digest(output)
    sealed["completion_probability_assigned"]=False
    sealed["return_outcomes_opened"]=False
    sealed["portfolio_eligibility_allowed"]=False
    sealed["live_capital_allowed"]=False
    return sealed
