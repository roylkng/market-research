from __future__ import annotations

import hashlib
import json
from typing import Any

from marketlab.alpha import AlphaContractError, digest

CONTRACT_ID = "SS002-L001-v1"

RELEVANCE_STATES = frozenset(
    {
        "DIRECT_LISTED_SECURITY",
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        "SUBSIDIARY_OR_INVESTEE_ONLY",
        "PROCEDURAL_OR_NEWSPAPER_UPDATE",
        "OTHER_CORPORATE_CONTEXT",
        "UNKNOWN",
    }
)

TRANSACTION_FAMILIES = frozenset(
    {
        "BUYBACK",
        "OPEN_OFFER_CONTROL",
        "DELISTING",
        "SCHEME_REORGANISATION",
        "RIGHTS_ISSUE",
        "PREFERENTIAL_WARRANT",
        "ASSET_SALE_DIVESTMENT",
        "INSOLVENCY_RESOLUTION",
        "CAPITAL_REDUCTION",
        "OFFER_FOR_SALE",
        "TENDER_OFFER",
        "ACQUISITION_INVESTMENT",
        "FUND_RAISE_OTHER",
        "OTHER",
        "UNKNOWN",
    }
)

STAGES = frozenset(
    {
        "PROPOSAL",
        "BOARD_APPROVED",
        "SHAREHOLDER_APPROVED",
        "REGULATORY_OR_COURT_APPROVED",
        "PUBLIC_ANNOUNCEMENT",
        "OFFER_OPEN",
        "OFFER_CLOSED",
        "RECORD_DATE_FIXED",
        "ALLOTMENT_COMPLETED",
        "TRANSACTION_COMPLETED",
        "CANCELLED_OR_WITHDRAWN",
        "PROCEDURAL_UPDATE",
        "UNKNOWN",
    }
)

FACT_FIELDS = {
    "parties": (
        "issuer_name",
        "target_name",
        "acquirer_name",
        "seller_name",
        "promoter_or_promoter_group",
        "other_named_counterparties",
    ),
    "security_economics": (
        "offer_price_per_share",
        "issue_price_per_share",
        "exercise_price_per_share",
        "floor_price_per_share",
        "number_of_securities",
        "maximum_securities",
        "offer_size_percentage",
        "stake_before_percentage",
        "stake_after_percentage",
        "face_value_per_share",
    ),
    "consideration": (
        "total_consideration",
        "cash_consideration",
        "non_cash_consideration_description",
        "debt_assumed",
        "enterprise_value_stated",
        "asset_or_business_value_stated",
    ),
    "ratios_entitlement": (
        "rights_entitlement_numerator",
        "rights_entitlement_denominator",
        "bonus_ratio_numerator",
        "bonus_ratio_denominator",
        "exchange_ratio_text",
        "tender_or_acceptance_ratio_stated",
    ),
    "dates": (
        "announcement_date",
        "board_approval_date",
        "shareholder_approval_date",
        "record_date",
        "ex_date",
        "offer_open_date",
        "offer_close_date",
        "expected_completion_date",
        "effective_date",
        "court_or_regulatory_order_date",
    ),
    "conditions_approvals": (
        "approvals_required",
        "conditions_precedent",
        "regulatory_bodies",
        "voting_or_tender_thresholds",
        "financing_conditions",
    ),
    "business_economics": (
        "stated_transaction_rationale",
        "stated_use_of_proceeds",
        "asset_or_business_description",
        "capacity_or_operating_metric_disclosed",
        "debt_reduction_or_financing_use",
        "dilution_or_new_share_count_description",
    ),
}

FORBIDDEN_KEYS = frozenset(
    {
        "target_price",
        "intrinsic_value",
        "expected_return",
        "completion_probability",
        "probability_of_completion",
        "bullish",
        "bearish",
        "buy",
        "sell",
        "hold",
        "portfolio_weight",
        "quality_score",
        "governance_score",
        "catalyst_score",
    }
)


def _canonical_bytes(payload: Any) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("SS002 L001 output must be finite JSON") from exc


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def empty_fact() -> dict[str, Any]:
    return {
        "status": "UNKNOWN",
        "value": None,
        "unit": None,
        "evidence_segment_ids": [],
    }


def empty_fact_tree() -> dict[str, Any]:
    return {
        family: {field: empty_fact() for field in fields}
        for family, fields in FACT_FIELDS.items()
    }


def extraction_template(
    *,
    document_id: str,
    event_ids: list[str],
    symbols: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "document_id": document_id,
        "event_ids": sorted(event_ids),
        "symbols": sorted(symbols),
        "economic_relevance": "UNKNOWN",
        "transaction_families": ["UNKNOWN"],
        "transaction_stage": "UNKNOWN",
        "facts": empty_fact_tree(),
        "unresolved_questions": [],
        "contradictions_within_document": [],
        "extraction_caveats": [],
        "provenance": {
            "provider_runtime": "",
            "model_id": "",
            "model_config_sha256": "",
            "prompt_contract_id": CONTRACT_ID,
            "prompt_sha256": "",
            "input_document_id": document_id,
            "input_segment_manifest_sha256": "",
            "raw_model_response_sha256": "",
        },
    }


def build_prompt_envelope(
    *,
    document_id: str,
    source_url: str,
    event_ids: list[str],
    symbols: list[str],
    category_hints: list[str],
    segments: list[dict[str, Any]],
    segment_manifest_sha256: str,
) -> dict[str, Any]:
    if not document_id or not source_url:
        raise AlphaContractError("SS002 L001 prompt requires document identity")
    if not event_ids or not all(isinstance(value, str) and value for value in event_ids):
        raise AlphaContractError("SS002 L001 prompt requires non-empty event IDs")
    if not symbols or not all(isinstance(value, str) and value for value in symbols):
        raise AlphaContractError("SS002 L001 prompt requires non-empty symbols")
    if len(event_ids) != len(set(event_ids)) or len(symbols) != len(set(symbols)):
        raise AlphaContractError("SS002 L001 prompt identities must be unique")
    segment_ids = []
    for row in segments:
        if not isinstance(row, dict):
            raise TypeError("SS002 L001 prompt segments must be objects")
        segment_id = str(row.get("segment_id") or "")
        text = row.get("text")
        text_sha = str(row.get("text_sha256") or "")
        if not segment_id or not isinstance(text, str) or not text_sha:
            raise AlphaContractError("SS002 L001 prompt segment is incomplete")
        if _sha256_bytes(text.encode("utf-8")) != text_sha:
            raise AlphaContractError("SS002 L001 prompt segment text SHA mismatch")
        segment_ids.append(segment_id)
    if len(segment_ids) != len(set(segment_ids)):
        raise AlphaContractError("SS002 L001 prompt segment IDs must be unique")

    system = (
        "You extract explicit corporate-transaction facts from the supplied official "
        "document segments. Use no outside knowledge. Every EXPLICIT fact must cite one "
        "or more supplied segment_id values. If a term is not explicit, return UNKNOWN. "
        "Do not estimate valuation, returns, completion probability, attractiveness, "
        "portfolio weight, or investment advice. Do not perform arithmetic to fill "
        "missing terms. Preserve contradictions and uncertainty."
    )
    request = {
        "contract_id": CONTRACT_ID,
        "document_id": document_id,
        "source_url": source_url,
        "event_ids": sorted(event_ids),
        "symbols": sorted(symbols),
        "category_hints": sorted(category_hints),
        "segment_manifest_sha256": segment_manifest_sha256,
        "segments": segments,
        "required_output_template": extraction_template(
            document_id=document_id,
            event_ids=event_ids,
            symbols=symbols,
        ),
    }
    prompt_payload = {
        "system": system,
        "request": request,
    }
    prompt_payload["prompt_sha256"] = _sha256_bytes(_canonical_bytes(prompt_payload))
    return prompt_payload


def _walk_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_walk_keys(child))
    return keys


def _validate_fact(
    fact: Any,
    *,
    allowed_segment_ids: set[str],
    path: str,
) -> None:
    if not isinstance(fact, dict):
        raise AlphaContractError(f"{path}: fact must be an object")
    if set(fact) != {"status", "value", "unit", "evidence_segment_ids"}:
        raise AlphaContractError(f"{path}: fact keys differ from frozen contract")
    status = fact.get("status")
    evidence = fact.get("evidence_segment_ids")
    if not isinstance(evidence, list) or not all(isinstance(x, str) for x in evidence):
        raise AlphaContractError(f"{path}: evidence_segment_ids must be string list")
    if len(evidence) != len(set(evidence)):
        raise AlphaContractError(f"{path}: duplicate evidence segment IDs")
    unknown = set(evidence) - allowed_segment_ids
    if unknown:
        raise AlphaContractError(f"{path}: unknown evidence segments {sorted(unknown)}")
    if status == "EXPLICIT":
        if fact.get("value") is None:
            raise AlphaContractError(f"{path}: EXPLICIT fact requires value")
        if not evidence:
            raise AlphaContractError(f"{path}: EXPLICIT fact requires evidence")
    elif status == "UNKNOWN":
        if fact.get("value") is not None:
            raise AlphaContractError(f"{path}: UNKNOWN fact must have null value")
        if evidence:
            raise AlphaContractError(f"{path}: UNKNOWN fact must not cite evidence")
        if fact.get("unit") is not None:
            raise AlphaContractError(f"{path}: UNKNOWN fact must have null unit")
    else:
        raise AlphaContractError(f"{path}: invalid fact status")


def validate_extraction(
    output: dict[str, Any],
    *,
    input_document_id: str,
    allowed_event_ids: set[str],
    allowed_symbols: set[str],
    allowed_segment_ids: set[str],
    expected_segment_manifest_sha256: str,
) -> dict[str, Any]:
    _canonical_bytes(output)

    forbidden = sorted(
        key for key in _walk_keys(output) if key.casefold() in FORBIDDEN_KEYS
    )
    if forbidden:
        raise AlphaContractError(f"SS002 L001 forbidden output fields: {forbidden}")

    if output.get("schema_version") != 1 or output.get("contract_id") != CONTRACT_ID:
        raise AlphaContractError("SS002 L001 output contract identity mismatch")
    if output.get("document_id") != input_document_id:
        raise AlphaContractError("SS002 L001 output document_id mismatch")

    if not allowed_event_ids:
        raise AlphaContractError("SS002 L001 allowed event IDs must be non-empty")
    if not allowed_symbols:
        raise AlphaContractError("SS002 L001 allowed symbols must be non-empty")
    event_ids = output.get("event_ids")
    symbols = output.get("symbols")
    if not isinstance(event_ids, list) or set(event_ids) != allowed_event_ids:
        raise AlphaContractError("SS002 L001 output event IDs differ from input")
    if not isinstance(symbols, list) or set(symbols) != allowed_symbols:
        raise AlphaContractError("SS002 L001 output symbols differ from input")

    if output.get("economic_relevance") not in RELEVANCE_STATES:
        raise AlphaContractError("SS002 L001 invalid economic relevance")
    families = output.get("transaction_families")
    if (
        not isinstance(families, list)
        or not families
        or not set(families).issubset(TRANSACTION_FAMILIES)
    ):
        raise AlphaContractError("SS002 L001 invalid transaction families")
    if output.get("transaction_stage") not in STAGES:
        raise AlphaContractError("SS002 L001 invalid transaction stage")

    facts = output.get("facts")
    if not isinstance(facts, dict) or set(facts) != set(FACT_FIELDS):
        raise AlphaContractError("SS002 L001 fact families differ from contract")
    for family, fields in FACT_FIELDS.items():
        block = facts.get(family)
        if not isinstance(block, dict) or set(block) != set(fields):
            raise AlphaContractError(f"SS002 L001 {family} fields differ from contract")
        for field in fields:
            _validate_fact(
                block[field],
                allowed_segment_ids=allowed_segment_ids,
                path=f"facts.{family}.{field}",
            )

    for field in (
        "unresolved_questions",
        "contradictions_within_document",
        "extraction_caveats",
    ):
        values = output.get(field)
        if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
            raise AlphaContractError(f"SS002 L001 {field} must be a string list")

    provenance = output.get("provenance")
    if not isinstance(provenance, dict):
        raise AlphaContractError("SS002 L001 provenance unavailable")
    required_provenance = {
        "provider_runtime",
        "model_id",
        "model_config_sha256",
        "prompt_contract_id",
        "prompt_sha256",
        "input_document_id",
        "input_segment_manifest_sha256",
        "raw_model_response_sha256",
    }
    if set(provenance) != required_provenance:
        raise AlphaContractError("SS002 L001 provenance keys differ from contract")
    if any(not isinstance(provenance[key], str) or not provenance[key] for key in required_provenance):
        raise AlphaContractError("SS002 L001 provenance values must be non-empty strings")
    if provenance["prompt_contract_id"] != CONTRACT_ID:
        raise AlphaContractError("SS002 L001 prompt contract mismatch")
    if provenance["input_document_id"] != input_document_id:
        raise AlphaContractError("SS002 L001 provenance document mismatch")
    if provenance["input_segment_manifest_sha256"] != expected_segment_manifest_sha256:
        raise AlphaContractError("SS002 L001 segment manifest mismatch")

    sealed = dict(output)
    sealed["validated_structured_output_sha256"] = digest(output)
    sealed["return_outcomes_opened"] = False
    sealed["portfolio_eligibility_allowed"] = False
    sealed["live_capital_allowed"] = False
    return sealed
