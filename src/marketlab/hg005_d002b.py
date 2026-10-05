from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes

RUN_ID = "HG005-D002B-GPT56SOL-NATIVE-v1"
SYNTHESIS_ID = "HG005-D002B-SYNTHESIS-v1"
EXPECTED_CORPUS_ID = "HG005-D002A-v1"
EXPECTED_CORPUS_SHA = "52405e676c1b76687bb4ea31cc27e1dc18ddc1ffe1d62c4ca5b306098270f135"
EXPECTED_SOURCE_COUNT = 19
EXPECTED_SYMBOLS = {"ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV"}
EVIDENCE_DISCIPLINE = "SS002-L001-v1"

MODEL_CONFIG = {
    "provider_runtime": "CHATGPT_NATIVE_INTERACTIVE",
    "model_id": "GPT-5.6 Sol",
    "temperature": 0.0,
    "top_p": 1.0,
    "contract_id": "HG005-D002B-v1",
    "evidence_discipline": EVIDENCE_DISCIPLINE,
    "transport": "NATIVE_CHAT_MODEL",
    "structured_output_mode": "JSON_OBJECT",
}

FORBIDDEN_KEYS = frozenset(
    {
        "target_price",
        "intrinsic_value",
        "expected_return",
        "completion_probability",
        "probability_of_completion",
        "buy",
        "sell",
        "hold",
        "portfolio_weight",
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
        raise AlphaContractError("HG005 D002B payload must be finite JSON") from exc


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


def _validate_corpus(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if corpus.get("corpus_id") != EXPECTED_CORPUS_ID:
        raise AlphaContractError("HG005 D002B requires frozen D002A corpus")
    if corpus.get("corpus_sha256") != EXPECTED_CORPUS_SHA:
        raise AlphaContractError("HG005 D002B D002A corpus SHA mismatch")
    if corpus.get("source_count") != EXPECTED_SOURCE_COUNT:
        raise AlphaContractError("HG005 D002B source count mismatch")
    if corpus.get("ready_text_count") != EXPECTED_SOURCE_COUNT:
        raise AlphaContractError("HG005 D002B requires all 19 sources text-ready")
    if corpus.get("promotion_allowed_to_d002b") is not True:
        raise AlphaContractError("HG005 D002B promotion gate is closed")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "llm_inference_executed",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if corpus.get(field) is not False:
            raise AlphaContractError(f"HG005 D002B requires source {field}=false")

    rows = corpus.get("sources")
    if not isinstance(rows, list) or len(rows) != EXPECTED_SOURCE_COUNT:
        raise AlphaContractError("HG005 D002B source rows unavailable")
    by_id: dict[str, dict[str, Any]] = {}
    symbols: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG005 D002B source rows must be objects")
        source_id = str(row.get("source_id") or "")
        symbol = str(row.get("symbol") or "").upper()
        if (
            not source_id
            or source_id in by_id
            or symbol not in EXPECTED_SYMBOLS
            or row.get("status") != "READY_SOURCE"
            or row.get("text_state") != "READY_TEXT"
        ):
            raise AlphaContractError("HG005 D002B invalid text-ready source row")
        segments = row.get("segments")
        if not isinstance(segments, list) or not segments:
            raise AlphaContractError(f"{source_id}: deterministic segments unavailable")
        seen_segments: set[str] = set()
        for segment in segments:
            if not isinstance(segment, dict):
                raise TypeError(f"{source_id}: segment must be an object")
            segment_id = str(segment.get("segment_id") or "")
            text = segment.get("text")
            text_sha = str(segment.get("text_sha256") or "")
            if (
                not segment_id
                or segment_id in seen_segments
                or not isinstance(text, str)
                or sha256_bytes(text.encode("utf-8")) != text_sha
            ):
                raise AlphaContractError(f"{source_id}: segment integrity failure")
            seen_segments.add(segment_id)
        by_id[source_id] = row
        symbols.add(symbol)
    if symbols != EXPECTED_SYMBOLS:
        raise AlphaContractError("HG005 D002B symbol set mismatch")
    return by_id


def model_config_sha256() -> str:
    return digest(MODEL_CONFIG)


def source_prompt_sha256(source: dict[str, Any]) -> str:
    payload = {
        "contract_id": "HG005-D002B-v1",
        "evidence_discipline": EVIDENCE_DISCIPLINE,
        "source_id": source["source_id"],
        "symbol": source["symbol"],
        "required_fact_groups": source["required_fact_groups"],
        "raw_sha256": source["raw_sha256"],
        "segment_manifest_sha256": source["segment_manifest_sha256"],
        "instruction": (
            "Extract only explicit payoff-enrichment facts required by the frozen "
            "HG005-D002/D002B contracts. Every explicit fact must cite supplied "
            "segment IDs. Unknown remains unknown. No valuation, expected return, "
            "completion probability or investment advice."
        ),
    }
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def validate_source_extraction(
    output: dict[str, Any],
    *,
    source: dict[str, Any],
) -> dict[str, Any]:
    _canonical_bytes(output)
    forbidden = sorted(
        key for key in _walk_keys(output) if key.casefold() in FORBIDDEN_KEYS
    )
    if forbidden:
        raise AlphaContractError(f"HG005 D002B forbidden fields: {forbidden}")

    if output.get("schema_version") != 1:
        raise AlphaContractError("HG005 D002B extraction schema_version mismatch")
    if output.get("contract_id") != "HG005-D002B-v1":
        raise AlphaContractError("HG005 D002B extraction contract mismatch")
    if output.get("source_id") != source["source_id"]:
        raise AlphaContractError("HG005 D002B source_id mismatch")
    if output.get("symbol") != source["symbol"]:
        raise AlphaContractError("HG005 D002B symbol mismatch")
    if output.get("input_raw_sha256") != source["raw_sha256"]:
        raise AlphaContractError("HG005 D002B raw SHA mismatch")
    if (
        output.get("input_segment_manifest_sha256")
        != source["segment_manifest_sha256"]
    ):
        raise AlphaContractError("HG005 D002B segment manifest mismatch")

    allowed_segments = {
        str(row["segment_id"]) for row in source["segments"]
    }
    facts = output.get("facts")
    if not isinstance(facts, list):
        raise TypeError("HG005 D002B facts must be a list")
    seen_fact_ids: set[str] = set()
    for fact in facts:
        if not isinstance(fact, dict):
            raise TypeError("HG005 D002B fact must be an object")
        if set(fact) != {
            "fact_id",
            "fact_name",
            "status",
            "value",
            "unit",
            "effective_or_reporting_date",
            "evidence_segment_ids",
        }:
            raise AlphaContractError("HG005 D002B fact keys differ from contract")
        fact_id = str(fact.get("fact_id") or "")
        fact_name = str(fact.get("fact_name") or "")
        if not fact_id or fact_id in seen_fact_ids or not fact_name:
            raise AlphaContractError("HG005 D002B fact identity is invalid")
        seen_fact_ids.add(fact_id)
        status = fact.get("status")
        evidence = fact.get("evidence_segment_ids")
        if not isinstance(evidence, list) or not all(
            isinstance(value, str) for value in evidence
        ):
            raise AlphaContractError(f"{fact_id}: evidence IDs must be string list")
        if len(evidence) != len(set(evidence)):
            raise AlphaContractError(f"{fact_id}: duplicate evidence IDs")
        unknown = set(evidence) - allowed_segments
        if unknown:
            raise AlphaContractError(
                f"{fact_id}: unknown evidence segments {sorted(unknown)}"
            )
        if status == "EXPLICIT":
            if fact.get("value") is None or not evidence:
                raise AlphaContractError(
                    f"{fact_id}: EXPLICIT fact requires value and evidence"
                )
        elif status == "UNKNOWN":
            if (
                fact.get("value") is not None
                or fact.get("unit") is not None
                or fact.get("effective_or_reporting_date") is not None
                or evidence
            ):
                raise AlphaContractError(
                    f"{fact_id}: UNKNOWN fact must remain null and uncited"
                )
        else:
            raise AlphaContractError(f"{fact_id}: unsupported fact status")

    for field in ("unresolved_questions", "conflicts", "extraction_caveats"):
        values = output.get(field)
        if not isinstance(values, list) or not all(
            isinstance(value, str) for value in values
        ):
            raise AlphaContractError(f"HG005 D002B {field} must be string list")

    provenance = output.get("provenance")
    if not isinstance(provenance, dict):
        raise AlphaContractError("HG005 D002B provenance unavailable")
    required_provenance = {
        "provider_runtime",
        "model_id",
        "model_config_sha256",
        "prompt_contract_id",
        "prompt_sha256",
        "input_source_id",
        "input_raw_sha256",
        "input_segment_manifest_sha256",
        "raw_model_response_sha256",
    }
    if set(provenance) != required_provenance:
        raise AlphaContractError("HG005 D002B provenance keys differ from contract")
    if any(
        not isinstance(provenance[key], str) or not provenance[key]
        for key in required_provenance
    ):
        raise AlphaContractError("HG005 D002B provenance values must be non-empty")
    if provenance["provider_runtime"] != MODEL_CONFIG["provider_runtime"]:
        raise AlphaContractError("HG005 D002B provider/runtime mismatch")
    if provenance["model_id"] != MODEL_CONFIG["model_id"]:
        raise AlphaContractError("HG005 D002B model mismatch")
    if provenance["model_config_sha256"] != model_config_sha256():
        raise AlphaContractError("HG005 D002B model-config SHA mismatch")
    if provenance["prompt_contract_id"] != "HG005-D002B-v1":
        raise AlphaContractError("HG005 D002B prompt contract mismatch")
    if provenance["prompt_sha256"] != source_prompt_sha256(source):
        raise AlphaContractError("HG005 D002B prompt SHA mismatch")
    if provenance["input_source_id"] != source["source_id"]:
        raise AlphaContractError("HG005 D002B provenance source mismatch")
    if provenance["input_raw_sha256"] != source["raw_sha256"]:
        raise AlphaContractError("HG005 D002B provenance raw SHA mismatch")
    if (
        provenance["input_segment_manifest_sha256"]
        != source["segment_manifest_sha256"]
    ):
        raise AlphaContractError("HG005 D002B provenance segment mismatch")

    sealed = dict(output)
    sealed["validated_extraction_sha256"] = digest(output)
    return sealed


def _explicit_fact_index(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    result: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        symbol = str(row["symbol"])
        for fact in row["facts"]:
            if fact["status"] == "EXPLICIT":
                result[symbol][str(fact["fact_name"])].append(
                    {
                        **fact,
                        "source_id": row["source_id"],
                        "input_raw_sha256": row["input_raw_sha256"],
                    }
                )
    return result


def _has(index: dict[str, dict[str, list[dict[str, Any]]]], symbol: str, name: str) -> bool:
    return bool(index.get(symbol, {}).get(name))


def _values_conflict(values: list[dict[str, Any]]) -> bool:
    if len(values) <= 1:
        return False
    canonical = {
        json.dumps(
            {"value": row["value"], "unit": row["unit"]},
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        for row in values
    }
    return len(canonical) > 1


def _lane(
    *,
    lane: str,
    ready: bool,
    required_present: list[str],
    missing: list[str],
    conflicts: list[str],
    notes: list[str],
) -> dict[str, Any]:
    if conflicts:
        state = "SOURCE_CONFLICTING"
    elif ready:
        state = "SOURCE_READY"
    else:
        state = "SOURCE_PARTIAL" if required_present else "SOURCE_NOT_FOUND"
    return {
        "lane": lane,
        "source_state": state,
        "required_present": required_present,
        "remaining_missing_inputs": missing,
        "conflicting_fact_names": conflicts,
        "notes": notes,
    }


def build_d002b_synthesis(
    *,
    corpus: dict[str, Any],
    extraction_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    source_by_id = _validate_corpus(corpus)
    if len(extraction_rows) != EXPECTED_SOURCE_COUNT:
        raise AlphaContractError("HG005 D002B requires exactly 19 extraction rows")

    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for output in extraction_rows:
        if not isinstance(output, dict):
            raise TypeError("HG005 D002B extraction row must be object")
        source_id = str(output.get("source_id") or "")
        if not source_id or source_id in seen or source_id not in source_by_id:
            raise AlphaContractError("HG005 D002B extraction accounting mismatch")
        seen.add(source_id)
        validated.append(
            validate_source_extraction(output, source=source_by_id[source_id])
        )
    if seen != set(source_by_id):
        raise AlphaContractError("HG005 D002B source coverage is incomplete")

    index = _explicit_fact_index(validated)
    conflicts_by_symbol: dict[str, list[str]] = {}
    for symbol, facts in index.items():
        conflicts_by_symbol[symbol] = sorted(
            name for name, values in facts.items() if _values_conflict(values)
        )

    companies: dict[str, Any] = {}

    an_required = [
        name
        for name in (
            "demerger_ratio_text",
            "demerged_business_fy26_revenue_inr_crore",
            "operating_data_center_capacity_mw",
        )
        if _has(index, "ANANTRAJ", name)
    ]
    an_missing = [
        name
        for name in (
            "separated_business_ebitda_inr_crore",
            "separated_business_pat_inr_crore",
            "quantified_transferred_assets_inr_crore",
            "quantified_transferred_liabilities_inr_crore",
            "demerger_effective_date",
        )
        if not _has(index, "ANANTRAJ", name)
    ]
    companies["ANANTRAJ"] = {
        "lanes": [
            _lane(
                lane="DEMERGER_ENTITLEMENT",
                ready=len(an_required) == 3,
                required_present=an_required,
                missing=an_missing,
                conflicts=conflicts_by_symbol.get("ANANTRAJ", []),
                notes=[
                    "Revenue and operating-capacity evidence support explicit EV/revenue or EV/MW sensitivity methods; profitability and quantified transferred balance-sheet values remain unavailable."
                ],
            )
        ]
    }

    devx_common = [
        name
        for name in (
            "preferential_cash_received_q1_inr_crore",
            "security_deposit_required_inr_crore",
            "security_deposit_utilized_inr_crore",
            "winston_area_sqft",
            "winston_lease_years",
            "winston_project_status_text",
        )
        if _has(index, "DEVX", name)
    ]
    devx_missing = [
        name
        for name in (
            "winston_explicit_revenue_guidance_inr_crore",
            "winston_explicit_ebitda_guidance_inr_crore",
        )
        if not _has(index, "DEVX", name)
    ]
    devx_conflicts = conflicts_by_symbol.get("DEVX", [])
    companies["DEVX"] = {
        "lanes": [
            _lane(
                lane="DILUTION_FINANCING",
                ready=len(devx_common) >= 5,
                required_present=devx_common,
                missing=devx_missing,
                conflicts=devx_conflicts,
                notes=[
                    "Financing cash receipt and the specific Winston deployment asset are explicit; no Winston-specific revenue/EBITDA forecast is assumed."
                ],
            ),
            _lane(
                lane="CAPITAL_DEPLOYMENT_MONITOR",
                ready=len(devx_common) >= 5,
                required_present=devx_common,
                missing=devx_missing,
                conflicts=devx_conflicts,
                notes=[
                    "Current deployment is measurable through the refundable deposit and 450,000 sq ft Winston lease asset."
                ],
            ),
        ]
    }

    inox_acq_present = [
        name
        for name in (
            "wwil_purchase_consideration_max_inr_crore",
            "wwil_oam_revenue_fy26_inr_crore",
            "wwil_oam_capacity_gw",
            "wwil_acquisition_stage_text",
        )
        if _has(index, "INOXGREEN", name)
    ]
    inox_acq_missing = [
        name
        for name in (
            "wwil_acquisition_funding_structure",
            "wwil_incremental_debt_inr_crore",
            "wwil_interest_rate_pct",
            "wwil_normalized_ebitda_inr_crore",
            "wwil_normalized_pat_inr_crore",
            "wwil_normalized_operating_cash_flow_inr_crore",
        )
        if not _has(index, "INOXGREEN", name)
    ]
    inox_dem_present = [
        name
        for name in (
            "irsl_order_book_gw",
            "irsl_executed_projects_gw",
        )
        if _has(index, "INOXGREEN", name)
    ]
    inox_dem_missing = [
        name
        for name in (
            "power_evacuation_revenue_inr_crore",
            "power_evacuation_ebitda_inr_crore",
            "power_evacuation_pat_inr_crore",
            "power_evacuation_cash_flow_inr_crore",
            "quantified_transferred_assets_inr_crore",
            "quantified_transferred_liabilities_inr_crore",
            "demerger_effective_date",
        )
        if not _has(index, "INOXGREEN", name)
    ]
    inox_conflicts = conflicts_by_symbol.get("INOXGREEN", [])
    companies["INOXGREEN"] = {
        "lanes": [
            _lane(
                lane="ACQUISITION_ECONOMICS",
                ready=(
                    _has(index, "INOXGREEN", "wwil_purchase_consideration_max_inr_crore")
                    and _has(index, "INOXGREEN", "wwil_acquisition_funding_structure")
                    and (
                        _has(index, "INOXGREEN", "wwil_normalized_ebitda_inr_crore")
                        or _has(index, "INOXGREEN", "wwil_normalized_operating_cash_flow_inr_crore")
                    )
                ),
                required_present=inox_acq_present,
                missing=inox_acq_missing,
                conflicts=inox_conflicts,
                notes=[
                    "Purchase price, revenue and O&M capacity are explicit, but official funding structure and normalized WWIL earnings/cash flow remain absent."
                ],
            ),
            _lane(
                lane="DEMERGER_ENTITLEMENT",
                ready=False,
                required_present=inox_dem_present,
                missing=inox_dem_missing,
                conflicts=inox_conflicts,
                notes=[
                    "Resulting EPC/power-evacuation operating context is explicit, but separated-business financial economics remain insufficient for an independent valuation method."
                ],
            ),
        ]
    }

    npst_present = [
        name
        for name in (
            "raise_amount_inr_crore",
            "cumulative_deployed_inr_crore",
            "unutilized_proceeds_inr_crore",
            "global_subsidiary_investment_inr_crore",
            "international_subsidiary_revenue_state",
            "q1fy27_revenue_inr_crore",
            "q1fy27_ebitda_inr_crore",
        )
        if _has(index, "NPST", name)
    ]
    npst_missing: list[str] = []
    companies["NPST"] = {
        "lanes": [
            _lane(
                lane="CAPITAL_DEPLOYMENT_MONITOR",
                ready=(
                    _has(index, "NPST", "cumulative_deployed_inr_crore")
                    and _has(index, "NPST", "international_subsidiary_revenue_state")
                ),
                required_present=npst_present,
                missing=npst_missing,
                conflicts=conflicts_by_symbol.get("NPST", []),
                notes=[
                    "Deployment amounts and an explicit operating consequence are both present; no causal attribution beyond management/source statements is inferred."
                ],
            )
        ]
    }

    sambhv_present = [
        name
        for name in (
            "warrant_count",
            "warrant_issue_price_inr",
            "warrant_total_consideration_inr",
            "warrant_use_of_proceeds_text",
            "finished_products_capacity_fy26_mmtpa",
            "finished_products_capacity_target_mmtpa",
            "phase1_stainless_capacity_addition_mmtpa",
            "phase1_capex_inr_crore",
            "phase1_target_commissioning_text",
            "financing_stage_text",
        )
        if _has(index, "SAMBHV", name)
    ]
    sambhv_missing = [
        name
        for name in (
            "warrant_allotment_date",
            "warrant_upfront_cash_received_inr_crore",
        )
        if not _has(index, "SAMBHV", name)
    ]
    companies["SAMBHV"] = {
        "lanes": [
            _lane(
                lane="DILUTION_FINANCING",
                ready=(
                    _has(index, "SAMBHV", "warrant_count")
                    and _has(index, "SAMBHV", "warrant_use_of_proceeds_text")
                    and _has(index, "SAMBHV", "phase1_stainless_capacity_addition_mmtpa")
                    and _has(index, "SAMBHV", "financing_stage_text")
                ),
                required_present=sambhv_present,
                missing=sambhv_missing,
                conflicts=conflicts_by_symbol.get("SAMBHV", []),
                notes=[
                    "Use-of-proceeds and capacity deployment are specific, but September evidence still describes an in-principle application rather than completed warrant allotment; cash receipt remains unknown."
                ],
            )
        ]
    }

    lane_states = Counter(
        lane["source_state"]
        for company in companies.values()
        for lane in company["lanes"]
    )
    output = {
        "schema_version": 1,
        "synthesis_id": SYNTHESIS_ID,
        "classification": "EVIDENCE_BOUND_PAYOFF_FACT_SYNTHESIS_NOT_ALPHA",
        "source_corpus_id": EXPECTED_CORPUS_ID,
        "source_corpus_sha256": EXPECTED_CORPUS_SHA,
        "run_id": RUN_ID,
        "model_config": MODEL_CONFIG,
        "model_config_sha256": model_config_sha256(),
        "source_extraction_count": len(validated),
        "symbol_count": len(companies),
        "lane_state_counts": dict(sorted(lane_states.items())),
        "companies": companies,
        "extractions": sorted(validated, key=lambda row: row["source_id"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["synthesis_sha256"] = digest(output)
    return output
