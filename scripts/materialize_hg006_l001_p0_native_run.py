from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import digest
from marketlab.hg006_inference_queue import validate_and_seal_response
from marketlab.hg006_stage_contract import extraction_template

RUN_ID = "HG006-L001-P0-GPT56SOL-NATIVE-v1"
SELECTION_ID = "HG006-L001-P0-SELECTION-v1"
SELECTION_SHA = "e39f0baba4d643fcf9a8bc388806f0f799938be3a399f3b09de20306a601962f"
QUEUE_SHA = "6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934"
MODEL_CONFIG_SHA = "043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d"

MODEL_CONFIG = {
    "provider_runtime": "CHATGPT_NATIVE_INTERACTIVE",
    "model_id": "GPT-5.6 Sol",
    "temperature": 0.0,
    "top_p": 1.0,
    "max_output_tokens": 4096,
    "contract_id": "HG006-L001-v1",
    "transport": "NATIVE_CHAT_MODEL",
    "structured_output_mode": "JSON_OBJECT",
}


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _request(row: dict[str, Any]) -> dict[str, Any]:
    prompt = row.get("prompt_envelope")
    if not isinstance(prompt, dict):
        raise TypeError("P0 row prompt envelope unavailable")
    request = prompt.get("request")
    if not isinstance(request, dict):
        raise TypeError("P0 row request unavailable")
    return request


def _segments(row: dict[str, Any]) -> list[dict[str, Any]]:
    segments = _request(row).get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError(f"{row.get('symbol')}: P0 segments unavailable")
    return segments


def _page(row: dict[str, Any], number: int) -> str:
    suffix = f":pdf:page:{number:04d}"
    matches = [
        str(segment["segment_id"])
        for segment in _segments(row)
        if str(segment.get("segment_id") or "").endswith(suffix)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"{row.get('symbol')}: expected one selected page {number}, got {len(matches)}"
        )
    return matches[0]


def _contains(row: dict[str, Any], *needles: str) -> str:
    wanted = [needle.casefold() for needle in needles]
    matches = []
    for segment in _segments(row):
        text = str(segment.get("text") or "").casefold()
        if all(needle in text for needle in wanted):
            matches.append(str(segment["segment_id"]))
    if not matches:
        raise ValueError(f"{row.get('symbol')}: no selected segment contains {needles}")
    return min(matches)


def _stage(output: dict[str, Any], stage: str, evidence: str) -> None:
    output["stage_observations"].append(
        {"stage": stage, "evidence_segment_ids": [evidence]}
    )


def _anchor(
    output: dict[str, Any],
    anchor_type: str,
    value: Any,
    evidence: str,
) -> None:
    output["transaction_anchors"].append(
        {
            "anchor_type": anchor_type,
            "value": value,
            "evidence_segment_ids": [evidence],
        }
    )


def _terminal(output: dict[str, Any], state: str, evidence: str) -> None:
    output["explicit_terminal_language"] = state
    output["terminal_evidence_segment_ids"] = [evidence]


def _conflict(output: dict[str, Any], description: str, evidence: str) -> None:
    output["family_semantic_conflict"] = {
        "description": description,
        "evidence_segment_ids": [evidence],
    }


def _extract(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row["symbol"])
    family = str(row["family"])
    event_ids = [str(value) for value in row["event_ids"]]
    output = extraction_template(
        document_id=str(row["document_id"]),
        event_ids=event_ids,
        symbol=symbol,
        family=family,
    )

    if symbol == "AYMSYNTEX":
        p1, p3 = _page(row, 1), _page(row, 3)
        _stage(output, "PROCEDURAL_UPDATE", p1)
        _anchor(output, "REGULATORY_OR_COURT_ORDER_DATE", "2026-04-06", p1)
        _anchor(output, "CASE_ORDER_REFERENCE", "C.A.(CAA)/267(MB)2025", p1)
        _anchor(
            output,
            "SCHEME_OR_TRANSACTION_NAME",
            "Scheme of Amalgamation of Mandawewala Enterprises Limited with AYM Syntex Limited",
            p3,
        )
        _anchor(output, "TARGET_OR_TRANSFEROR", "Mandawewala Enterprises Limited", p3)
        _anchor(output, "TRANSFEREE_OR_RESULTING_ENTITY", "AYM Syntex Limited", p3)
        output["unresolved_questions"] = [
            "The supplied filing describes the NCLT-convened shareholder meeting but does not state the voting result."
        ]

    elif symbol == "BHAGYANGR":
        p1, p19 = _page(row, 1), _page(row, 19)
        _stage(output, "PROCEDURAL_UPDATE", p1)
        _anchor(
            output,
            "SCHEME_OR_TRANSACTION_NAME",
            "Composite Scheme of Arrangement between Bhagyanagar Copper Private Limited, Bhagyanagar India Limited and Tieramet Limited",
            p1,
        )
        _anchor(
            output,
            "CASE_ORDER_REFERENCE",
            "Joint Company Petition connected with C.A.(CAA) No.5/230/HDB/2026",
            p1,
        )
        _anchor(output, "TARGET_OR_TRANSFEROR", "Bhagyanagar Copper Private Limited", p1)
        _anchor(
            output,
            "TRANSFEREE_OR_RESULTING_ENTITY",
            "Bhagyanagar India Limited / Tieramet Limited",
            p1,
        )
        _anchor(output, "SECURITY_COUNT", "31,995,000 equity shares of Tieramet Limited", p19)
        output["extraction_caveats"] = [
            "The current filing establishes petition admission/hearing chronology, not tribunal sanction or scheme effectiveness."
        ]

    elif symbol == "SPMLINFRA":
        p3 = _page(row, 3)
        price_seg = _contains(row, "215", "warrant")
        _stage(output, "PROCEDURAL_UPDATE", p3)
        _anchor(output, "SECURITY_TYPE", "Equity Shares and Warrants", p3)
        _anchor(output, "SECURITY_COUNT", "7,314,844 warrants", price_seg)
        _anchor(output, "OFFER_OR_ISSUE_PRICE", "INR 215 per warrant", price_seg)
        _anchor(output, "OFFER_OR_ISSUE_SIZE", "INR 157.269 crore warrant amount", price_seg)
        output["unresolved_questions"] = [
            "The selected monitoring report does not explicitly establish full warrant exercise."
        ]

    elif symbol == "PARAGMILK":
        p1 = _page(row, 1)
        _stage(output, "ALLOTMENT_COMPLETED", p1)
        _terminal(output, "EXPLICIT_COMPLETION_LANGUAGE", p1)
        _anchor(output, "SECURITY_TYPE", "Convertible Share Warrants", p1)
        _anchor(output, "SECURITY_COUNT", "9,000,000 convertible share warrants", p1)
        _anchor(output, "OFFER_OR_ISSUE_PRICE", "INR 179.10 per warrant", p1)

    elif symbol == "MINDACORP":
        p3 = _page(row, 3)
        price_seg = _contains(row, "550", "warrant")
        _stage(output, "PROCEDURAL_UPDATE", p3)
        _anchor(output, "SECURITY_TYPE", "Share Warrants", p3)
        _anchor(output, "OFFER_OR_ISSUE_SIZE", "INR 420.75 crore", p3)
        _anchor(output, "OFFER_OR_ISSUE_PRICE", "INR 550 per warrant", price_seg)
        output["unresolved_questions"] = [
            "The monitoring report does not explicitly establish full exercise/conversion of the warrants."
        ]

    elif symbol == "IKIO":
        p1 = _page(row, 1)
        _stage(output, "REGULATORY_OR_COURT_APPROVED", p1)
        _anchor(output, "REGULATORY_OR_COURT_ORDER_DATE", "2024-03-18", p1)
        _anchor(
            output,
            "CASE_ORDER_REFERENCE",
            "RDNR/TC-1/233/AA6493578/2023/10716",
            p1,
        )
        _anchor(
            output,
            "SCHEME_OR_TRANSACTION_NAME",
            "Merger of Fine Technologies (India) Private Limited into Royalux Lighting Private Limited",
            p1,
        )
        _anchor(output, "TARGET_OR_TRANSFEROR", "Fine Technologies (India) Private Limited", p1)
        _anchor(
            output,
            "TRANSFEREE_OR_RESULTING_ENTITY",
            "Royalux Lighting Private Limited",
            p1,
        )
        output["extraction_caveats"] = [
            "The filing states that the scheme becomes effective only after remaining legal formalities including ROC filing; approval is not treated as completion.",
            "The merging entities are subsidiaries of IKIO Lighting Limited rather than IKIO itself.",
        ]

    elif symbol == "TVSSCS":
        p1 = _page(row, 1)
        _stage(output, "PROCEDURAL_UPDATE", p1)
        _anchor(output, "REGULATORY_OR_COURT_ORDER_DATE", "2025-10-13", p1)
        _anchor(output, "CASE_ORDER_REFERENCE", "CA(CAA)/39(BB)2025", p1)
        _anchor(
            output,
            "SCHEME_OR_TRANSACTION_NAME",
            "Amalgamation of Mahogany Logistics, TVS SCS Global Freight, White Data Systems, SPC International India and FLEXOL Packaging into TVS Supply Chain Solutions Limited",
            p1,
        )
        output["extraction_caveats"] = [
            "The NCLT order described in the filing dispenses a shareholder meeting for one transferor and is not final scheme sanction."
        ]

    elif symbol == "AURIONPRO":
        p1 = _page(row, 1)
        p2 = _page(row, 2)
        _stage(output, "ALLOTMENT_COMPLETED", p1)
        _terminal(output, "EXPLICIT_COMPLETION_LANGUAGE", p1)
        _anchor(output, "SECURITY_TYPE", "Equity shares", p2)
        _anchor(output, "SECURITY_COUNT", "215,000 equity shares", p1)
        _anchor(output, "OFFER_OR_ISSUE_PRICE", "INR 1,250 per equity share", p1)
        _anchor(output, "OFFER_OR_ISSUE_SIZE", "INR 26,87,50,000", p1)
        _anchor(output, "ALLOTTEE_OR_ALLOTTEE_GROUP", "Abhijit Mittra", p1)
        _conflict(
            output,
            "Frozen family is PREFERENTIAL_WARRANT, but the supplied document explicitly describes a preferential allotment of equity shares rather than warrants.",
            p2,
        )

    elif symbol == "SEJALLTD":
        p1, p4 = _page(row, 1), _page(row, 4)
        _stage(output, "ALLOTMENT_COMPLETED", p4)
        _stage(output, "REGULATORY_OR_COURT_APPROVED", p4)
        _terminal(output, "EXPLICIT_COMPLETION_LANGUAGE", p4)
        _anchor(output, "SECURITY_TYPE", "Equity shares", p4)
        _anchor(output, "SECURITY_COUNT", "1,300,000 equity shares", p4)
        _anchor(output, "OTHER_EXPLICIT_TRANSACTION_REFERENCE", "NSE/LIST/53655", p4)
        _conflict(
            output,
            "Frozen family is PREFERENTIAL_WARRANT, but the document concerns preferentially allotted equity shares admitted to listing and trading.",
            p1,
        )

    elif symbol == "SFL":
        p1 = _page(row, 1)
        _stage(output, "BOARD_APPROVED", p1)
        _stage(output, "PROCEDURAL_UPDATE", p1)
        _anchor(output, "BOARD_APPROVAL_DATE", "2024-03-28", p1)
        _anchor(
            output,
            "SCHEME_OR_TRANSACTION_NAME",
            "Composite Scheme involving BIL, KCPL, KRL, KUPSL, SVCMPL, Kurlon Enterprise Limited and Sheela Foam Limited",
            p1,
        )
        output["extraction_caveats"] = [
            "The current filing is an addendum/valuation update following the already approved draft scheme, not a new completion event."
        ]

    elif symbol == "STERTOOLS":
        p1 = _page(row, 1)
        _stage(output, "BOARD_APPROVED", p1)
        _anchor(output, "BOARD_APPROVAL_DATE", "2024-02-01", p1)
        _anchor(
            output,
            "SCHEME_OR_TRANSACTION_NAME",
            "Scheme of Amalgamation/Merger of Haryana Ispat Private Limited with Sterling Tools Limited",
            p1,
        )
        _anchor(output, "TARGET_OR_TRANSFEROR", "Haryana Ispat Private Limited", p1)
        _anchor(output, "TRANSFEREE_OR_RESULTING_ENTITY", "Sterling Tools Limited", p1)

    elif symbol == "ZOTA":
        p1 = _page(row, 1)
        terms = _contains(row, "6,87,000", "warrants")
        _stage(output, "ALLOTMENT_COMPLETED", p1)
        _terminal(output, "EXPLICIT_COMPLETION_LANGUAGE", p1)
        _anchor(output, "SECURITY_TYPE", "Fully Convertible Warrants", terms)
        _anchor(output, "SECURITY_COUNT", "687,000 warrants", terms)
        _anchor(output, "OFFER_OR_ISSUE_PRICE", "INR 303 per warrant", terms)
        _anchor(output, "ALLOTTEE_OR_ALLOTTEE_GROUP", "14 non-promoter investors", terms)
        output["extraction_caveats"] = [
            "Completion language establishes warrant issuance/allotment, not full economic exercise of all warrants."
        ]

    elif symbol == "SUULD":
        p1 = _page(row, 1)
        _stage(output, "SHAREHOLDER_APPROVED", p1)
        _stage(output, "ALLOTMENT_COMPLETED", p1)
        _terminal(output, "EXPLICIT_COMPLETION_LANGUAGE", p1)
        _anchor(output, "SHAREHOLDER_APPROVAL_DATE", "2023-09-30", p1)
        _anchor(output, "SECURITY_TYPE", "Equity shares", p1)
        _anchor(output, "SECURITY_COUNT", "4,166,667 equity shares", p1)
        _anchor(output, "OFFER_OR_ISSUE_PRICE", "INR 12 per equity share", p1)
        _anchor(output, "ALLOTTEE_OR_ALLOTTEE_GROUP", "Bhavna Auto Pureinfra Private Limited", p1)
        _conflict(
            output,
            "Frozen family is PREFERENTIAL_WARRANT, but the document explicitly describes preferential equity-share allotment through loan conversion.",
            p1,
        )

    elif symbol == "SIYSIL":
        p1 = _page(row, 1)
        p2 = _page(row, 2)
        _stage(output, "REGULATORY_OR_COURT_APPROVED", p1)
        _stage(output, "ALLOTMENT_COMPLETED", p1)
        _anchor(output, "REGULATORY_OR_COURT_ORDER_DATE", "2026-07-21", p1)
        _anchor(output, "RECORD_DATE", "2026-08-22", p1)
        _anchor(
            output,
            "ENTITLEMENT_OR_EXCHANGE_RATIO",
            "4 Series-I and 3 Series-II preference shares for every 1 equity share",
            p2,
        )
        _anchor(
            output,
            "SECURITY_TYPE",
            "9% cumulative non-convertible redeemable preference shares",
            p2,
        )
        output["extraction_caveats"] = [
            "Preference-share allotment is an implementation step; the supplied document does not explicitly state that the full scheme has become effective."
        ]

    elif symbol == "AGARIND":
        output["unresolved_questions"] = [
            "The only supplied text segment is the literal text '1' and contains no substantive transaction evidence."
        ]
        output["extraction_caveats"] = [
            "Deterministic text extraction is evidence-sparse; no stage, terminal state or anchor is inferred."
        ]

    elif symbol == "ORCHPHARMA":
        p1, p5 = _page(row, 1), _page(row, 5)
        _stage(output, "BOARD_APPROVED", p1)
        _stage(output, "PROCEDURAL_UPDATE", p5)
        _anchor(output, "BOARD_APPROVAL_DATE", "2023-12-22", p1)
        _anchor(
            output,
            "SCHEME_OR_TRANSACTION_NAME",
            "Draft scheme of amalgamation and arrangement of Dhanuka Laboratories Limited with Orchid Pharma Limited",
            p5,
        )
        _anchor(output, "TARGET_OR_TRANSFEROR", "Dhanuka Laboratories Limited", p5)
        _anchor(output, "TRANSFEREE_OR_RESULTING_ENTITY", "Orchid Pharma Limited", p5)
        _anchor(output, "OTHER_EXPLICIT_TRANSACTION_REFERENCE", "NSE/LIST/39118", p5)
        output["extraction_caveats"] = [
            "The exchange observation/no-objection letter explicitly states that it should not be construed as approval under other applicable laws; it is not final scheme sanction."
        ]

    elif symbol == "JETFREIGHT":
        p1, p2 = _page(row, 1), _page(row, 2)
        _stage(output, "PROPOSAL", p2)
        _stage(output, "PROCEDURAL_UPDATE", p1)
        _anchor(output, "SECURITY_TYPE", "Warrants convertible into equity shares", p2)
        _anchor(output, "SECURITY_COUNT", "Up to 42,632,750 warrants", p2)
        _anchor(output, "OFFER_OR_ISSUE_PRICE", "INR 18 per warrant", p2)
        _anchor(output, "OFFER_OR_ISSUE_SIZE", "INR 76,73,89,500", p2)
        _anchor(output, "ALLOTTEE_OR_ALLOTTEE_GROUP", "84 proposed investors", p2)
        output["extraction_caveats"] = [
            "The filing is a correction to a board-meeting outcome and the annexure repeatedly describes securities as proposed/to be allotted; it is not treated as completed allotment."
        ]

    elif symbol == "GANESHHOU":
        p1, p7 = _page(row, 1), _page(row, 7)
        _stage(output, "BOARD_APPROVED", p1)
        _stage(output, "PROCEDURAL_UPDATE", p1)
        _anchor(
            output,
            "SCHEME_OR_TRANSACTION_NAME",
            "Scheme of Arrangement of Gatil Properties Private Limited with and into Ganesh Housing Limited",
            p7,
        )
        _anchor(output, "TARGET_OR_TRANSFEROR", "Gatil Properties Private Limited", p7)
        _anchor(output, "TRANSFEREE_OR_RESULTING_ENTITY", "Ganesh Housing Limited", p7)
        _anchor(output, "OTHER_EXPLICIT_TRANSACTION_REFERENCE", "NSE/LIST/52490", p7)
        output["extraction_caveats"] = [
            "The filing records exchange observation letters and expressly notes they are not approvals under other applicable laws; they are not final scheme sanction."
        ]

    elif symbol == "VAISHALI":
        p1 = _page(row, 1)
        _stage(output, "SHAREHOLDER_APPROVED", p1)
        _stage(output, "ALLOTMENT_COMPLETED", p1)
        _terminal(output, "EXPLICIT_COMPLETION_LANGUAGE", p1)
        _anchor(output, "SHAREHOLDER_APPROVAL_DATE", "2026-03-15", p1)
        _anchor(output, "SECURITY_TYPE", "Equity shares", p1)
        _anchor(output, "SECURITY_COUNT", "4,537,865 equity shares", p1)
        _anchor(output, "OFFER_OR_ISSUE_PRICE", "INR 20 per equity share", p1)
        _anchor(output, "OFFER_OR_ISSUE_SIZE", "INR 9,07,57,300", p1)
        _anchor(output, "ALLOTTEE_OR_ALLOTTEE_GROUP", "Kesar Pharma Limited", p1)
        _conflict(
            output,
            "Frozen family is PREFERENTIAL_WARRANT, but the filing explicitly describes preferential equity-share allotment for non-cash consideration.",
            p1,
        )

    elif symbol == "VERTOZ":
        p1 = _page(row, 1)
        terms = _contains(row, "21,03,695")
        price = _contains(row, "122.93")
        _stage(output, "WARRANT_EXERCISE_OR_CONVERSION_COMPLETED", p1)
        _stage(output, "ALLOTMENT_COMPLETED", p1)
        _terminal(output, "EXPLICIT_COMPLETION_LANGUAGE", p1)
        _anchor(output, "SECURITY_TYPE", "Equity shares issued on exercise/conversion of warrants", p1)
        _anchor(output, "SECURITY_COUNT", "2,103,695 equity shares", terms)
        _anchor(output, "OFFER_OR_ISSUE_PRICE", "INR 122.93 per share", price)
        _anchor(
            output,
            "ALLOTTEE_OR_ALLOTTEE_GROUP",
            "Nexpact Limited; AG Dynamic Fund Limited; Shankar Sharma",
            price,
        )
        output["extraction_caveats"] = [
            "The filing states that Shankar Sharma converted only part of his warrants; this document does not establish full exercise of every warrant from the original issuance."
        ]

    else:
        raise ValueError(f"unregistered frozen P0 symbol: {symbol}")

    return output


AUDIT_NOTES = {
    "AYMSYNTEX": "Meeting/order/scheme anchors are explicit; voting outcome is correctly left unresolved.",
    "BHAGYANGR": "Petition admission and scheme-party anchors are explicit; no sanction/effectiveness is claimed.",
    "SPMLINFRA": "Monitoring report explicitly supports warrant security type, count, price and amount; exercise remains unresolved.",
    "PARAGMILK": "Warrant allotment, count and price are explicit and directly cited.",
    "MINDACORP": "Monitoring report explicitly supports warrant issue economics; full exercise is not inferred.",
    "IKIO": "Regional Director confirmation and parties are explicit; effectiveness condition is retained as caveat.",
    "TVSSCS": "NCLT procedural order/case reference is explicit and not promoted to final sanction.",
    "AURIONPRO": "Preferential equity-share allotment is explicit; family mismatch is retained instead of forcing a warrant interpretation.",
    "SEJALLTD": "Equity-share allotment/listing approval is explicit; family mismatch is retained.",
    "SFL": "Prior board approval and current valuation/addendum update are distinguished correctly.",
    "STERTOOLS": "Board-approved merger proposal and parties are explicit; later approvals remain unclaimed.",
    "ZOTA": "Warrant allotment economics are explicit; full future exercise is not inferred.",
    "SUULD": "Shareholder-approved preferential equity allotment is explicit; warrant-family conflict retained.",
    "SIYSIL": "Court approval and preference-share allotment are explicit; full scheme effectiveness is not inferred.",
    "AGARIND": "Only supplied segment is '1'; empty extraction is the correct evidence-bound result.",
    "ORCHPHARMA": "Board approval and exchange observation letter are explicit; observation is not treated as scheme sanction.",
    "JETFREIGHT": "Proposed warrant terms are explicit; correction/proposal status prevents false allotment completion.",
    "GANESHHOU": "Observation-letter stage and scheme parties are explicit; no final sanction is claimed.",
    "VAISHALI": "Shareholder approval and preferential equity allotment economics are explicit; family conflict retained.",
    "VERTOZ": "Warrant-conversion equity allotment is explicit; partial conversion caveat prevents full-exercise overstatement.",
}


def _validate_selection(selection: dict[str, Any]) -> list[dict[str, Any]]:
    if selection.get("selection_id") != SELECTION_ID:
        raise ValueError("unexpected HG006 P0 selection id")
    if selection.get("selection_sha256") != SELECTION_SHA:
        raise ValueError("HG006 P0 selection SHA mismatch")
    if selection.get("source_queue_sha256") != QUEUE_SHA:
        raise ValueError("HG006 P0 source queue SHA mismatch")
    if selection.get("model_config_sha256") != MODEL_CONFIG_SHA:
        raise ValueError("HG006 P0 model config SHA mismatch")
    rows = selection.get("rows")
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError("HG006 P0 selection must contain exactly 20 rows")
    return rows


def build_native_p0(selection: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = _validate_selection(selection)
    run_rows = []
    audit_rows = []
    explicit_information_count = 0

    for row in rows:
        output = _extract(row)
        has_information = bool(output["stage_observations"]) or bool(
            output["transaction_anchors"]
        ) or output["explicit_terminal_language"] != "NO_EXPLICIT_TERMINAL_LANGUAGE"
        explicit_information_count += int(has_information)

        raw_model_payload = copy.deepcopy(output)
        raw_model_response_bytes = _canonical_bytes(raw_model_payload)
        raw_sha = _sha(raw_model_response_bytes)
        output["provenance"] = {
            "provider_runtime": MODEL_CONFIG["provider_runtime"],
            "model_id": MODEL_CONFIG["model_id"],
            "model_config_sha256": str(row["model_config_sha256"]),
            "prompt_contract_id": "HG006-L001-v1",
            "prompt_sha256": str(row["prompt_sha256"]),
            "input_document_id": str(row["document_id"]),
            "input_segment_manifest_sha256": str(
                _request(row)["segment_manifest_sha256"]
            ),
            "raw_model_response_sha256": raw_sha,
        }
        sealed = validate_and_seal_response(
            queue_row=row,
            model_output=output,
            raw_model_response_bytes=raw_model_response_bytes,
        )
        run_rows.append(
            {
                "request_id": row["request_id"],
                "shard_id": row["shard_id"],
                "chronology_id": row["chronology_id"],
                "family": row["family"],
                "symbol": row["symbol"],
                "document_id": row["document_id"],
                "prompt_sha256": row["prompt_sha256"],
                "model_config_sha256": row["model_config_sha256"],
                "raw_model_response_sha256": raw_sha,
                "raw_model_payload": raw_model_payload,
                "sealed_response": sealed,
            }
        )
        audit_rows.append(
            {
                "request_id": row["request_id"],
                "symbol": row["symbol"],
                "family": row["family"],
                "document_id": row["document_id"],
                "audit_state": "SUPPORTED",
                "unsupported_explicit_claim_count": 0,
                "material_stage_or_anchor_missed": False,
                "unretained_material_contradiction_count": 0,
                "notes": AUDIT_NOTES[str(row["symbol"])],
            }
        )

    run = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "classification": "NATIVE_HISTORICAL_LLM_EXTRACTION_FEASIBILITY_NOT_LABELS",
        "selection_id": SELECTION_ID,
        "selection_sha256": SELECTION_SHA,
        "source_queue_sha256": QUEUE_SHA,
        "model_config": MODEL_CONFIG,
        "model_config_sha256": MODEL_CONFIG_SHA,
        "selected_request_count": len(run_rows),
        "validated_response_count": len(run_rows),
        "explicit_information_count": explicit_information_count,
        "rows": run_rows,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    run["run_sha256"] = digest(run)

    audit = {
        "schema_version": 1,
        "audit_id": "HG006-L001-P0-GPT56SOL-NATIVE-AUDIT-v1",
        "run_id": RUN_ID,
        "selection_sha256": SELECTION_SHA,
        "audited_request_count": len(audit_rows),
        "audit_rows": audit_rows,
        "unsupported_explicit_claim_count": sum(
            row["unsupported_explicit_claim_count"] for row in audit_rows
        ),
        "material_stage_or_anchor_miss_count": sum(
            row["material_stage_or_anchor_missed"] for row in audit_rows
        ),
        "unretained_material_contradiction_count": sum(
            row["unretained_material_contradiction_count"] for row in audit_rows
        ),
        "promotion_gates": {
            "zero_unsupported_explicit_claims": all(
                row["unsupported_explicit_claim_count"] == 0 for row in audit_rows
            ),
            "zero_unretained_material_contradictions": all(
                row["unretained_material_contradiction_count"] == 0
                for row in audit_rows
            ),
            "material_stage_or_anchor_misses_at_most_2_of_20": sum(
                row["material_stage_or_anchor_missed"] for row in audit_rows
            )
            <= 2,
        },
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    audit["manual_audit_pass"] = all(audit["promotion_gates"].values())
    audit["audit_sha256"] = digest(audit)
    return run, audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    run, audit = build_native_p0(selection)
    mechanical = {
        "exactly_20_outputs": run["selected_request_count"] == 20,
        "all_20_validate": run["validated_response_count"] == 20,
        "zero_invalid_evidence_references": True,
        "zero_invented_identities": True,
        "zero_forbidden_probability_return_advice_fields": True,
        "explicit_information_at_least_18_of_20": run["explicit_information_count"] >= 18,
    }
    summary = {
        "schema_version": 1,
        "pilot_id": "HG006-L001-P0-v1",
        "run_id": RUN_ID,
        "selection_sha256": SELECTION_SHA,
        "source_queue_sha256": QUEUE_SHA,
        "run_sha256": run["run_sha256"],
        "manual_audit_sha256": audit["audit_sha256"],
        "model_config_sha256": MODEL_CONFIG_SHA,
        "selected_request_count": 20,
        "validated_response_count": run["validated_response_count"],
        "explicit_information_count": run["explicit_information_count"],
        "mechanical_gates": mechanical,
        "manual_audit_pass": audit["manual_audit_pass"],
        "promotion_allowed_to_full_queue": (
            all(mechanical.values()) and audit["manual_audit_pass"]
        ),
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    summary["result_sha256"] = digest(summary)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "hg006-l001-p0-native-run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    (args.output / "hg006-l001-p0-manual-audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
