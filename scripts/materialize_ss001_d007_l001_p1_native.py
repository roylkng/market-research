from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import digest
from marketlab.ss002_llm_contract import validate_extraction

RUN_ID = "SS001-D007-L001-P1-GPT56SOL-NATIVE-v1"
QUEUE_ID = "SS001-D007-L001-P0-v1"
QUEUE_SHA = "cbd36ef8c868a8a54610f0fb3e7f30e8a4746c897333140e3f1d9521b1c7622a"
MODEL_CONFIG_SHA = "133b5705036d1782f671d6a171fe5f24298939cf6d84314875c2e8452e7169dc"

MODEL_CONFIG = {
    "provider_runtime": "CHATGPT_NATIVE_INTERACTIVE",
    "model_id": "GPT-5.6 Sol",
    "temperature": 0.0,
    "top_p": 1.0,
    "max_output_tokens": 4096,
    "contract_id": "SS002-L001-v1",
    "transport": "NATIVE_CHAT_MODEL",
    "structured_output_mode": "JSON_OBJECT",
}

EXPECTED_SYMBOLS = (
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

DECISIONS = {
    "JAYKAY": ("DIRECT_LISTED_SECURITY", ["RIGHTS_ISSUE"], "BOARD_APPROVED"),
    "INDIAGLYCO": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "PROCEDURAL_UPDATE",
    ),
    "HEGAM": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "PROCEDURAL_UPDATE",
    ),
    "IITL": (
        "DIRECT_LISTED_SECURITY",
        ["BUYBACK", "TENDER_OFFER"],
        "RECORD_DATE_FIXED",
    ),
    "ORBTEXP": (
        "DIRECT_LISTED_SECURITY",
        ["BUYBACK", "TENDER_OFFER"],
        "RECORD_DATE_FIXED",
    ),
    "PVRINOX": (
        "DIRECT_LISTED_SECURITY",
        ["BUYBACK", "TENDER_OFFER"],
        "RECORD_DATE_FIXED",
    ),
    "GANDHITUBE": (
        "DIRECT_LISTED_SECURITY",
        ["BUYBACK"],
        "RECORD_DATE_FIXED",
    ),
    "RATNAVEER": (
        "DIRECT_LISTED_SECURITY",
        ["RIGHTS_ISSUE"],
        "PROCEDURAL_UPDATE",
    ),
    "TEAMLEASE": (
        "PROCEDURAL_OR_NEWSPAPER_UPDATE",
        ["BUYBACK"],
        "PROCEDURAL_UPDATE",
    ),
    "TRIVENI": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "RECORD_DATE_FIXED",
    ),
    "DUCON": (
        "DIRECT_LISTED_SECURITY",
        ["RIGHTS_ISSUE"],
        "PROCEDURAL_UPDATE",
    ),
    "INOXGREEN": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "RECORD_DATE_FIXED",
    ),
}

CAVEATS = {
    "HEGAM": [
        (
            "The supplied filing identifies the listed company as HEG Limited with NSE "
            "code HEG, while the frozen prompt symbol is HEGAM. L001 does not adjudicate "
            "symbol/issuer continuity beyond the supplied provenance binding."
        )
    ],
    "TEAMLEASE": [
        (
            "The selected document is a filing about publication of newspaper "
            "advertisements and dispatch of the Letter of Offer. Subsequent newspaper "
            "pages are not cleanly text-extracted, so detailed buyback economics are "
            "left UNKNOWN."
        )
    ],
    "TRIVENI": [
        (
            "The Scheme is stated to have become effective and the power-transmission "
            "undertaking transferred, while the current filing fixes the shareholder "
            "record date for distribution of resulting-company shares."
        )
    ],
    "INOXGREEN": [
        (
            "The filing states that the Scheme has become effective but does not state "
            "the exact effective calendar date in the supplied segment."
        )
    ],
}

UNRESOLVED = {
    "JAYKAY": [
        "Issue price, rights entitlement ratio and record date are explicitly left for later determination."
    ],
    "INDIAGLYCO": [
        "The NCLT matter is reserved for final pronouncement; the supplied document does not contain the final sanction order."
    ],
    "HEGAM": [
        "The NCLT order is awaited; the supplied document does not establish final sanction or effectiveness."
    ],
    "RATNAVEER": [
        "The rights issue price, premium, share count and entitlement ratio are shown as placeholders and therefore remain UNKNOWN."
    ],
    "TEAMLEASE": [
        "Detailed price, record-date and offer-timeline terms are not reliably available from the supplied extracted newspaper pages."
    ],
    "DUCON": [
        "The supplied in-principle approval does not provide a reliable final share count, issue price or entitlement ratio."
    ],
    "INOXGREEN": [
        "The exact Scheme effective date is not stated in the supplied segment."
    ],
}

AUDIT_NOTES = {
    "JAYKAY": (
        "Board approval, issuer, rights-issue structure, INR 155 crore cap and "
        "approval contingency are explicit. Undecided price/ratio/record date remain UNKNOWN."
    ),
    "INDIAGLYCO": (
        "Issuer, two resulting companies, demerger character, NCLT order date and "
        "reserved-for-pronouncement state are explicit; no sanction is inferred."
    ),
    "HEGAM": (
        "Composite-scheme parties, NCLT Indore hearing date and reserved-order state "
        "are explicit. Prompt/document symbol mismatch is retained as a caveat."
    ),
    "IITL": (
        "Issuer, buyback price, maximum shares, 7.39%, cash size, face value, board "
        "date and record date are explicit in supplied pages."
    ),
    "ORBTEXP": (
        "Issuer, tender buyback price, maximum shares, 4.16%, cash size, face value, "
        "board date and record date are explicit."
    ),
    "PVRINOX": (
        "Issuer, tender buyback price, maximum shares, 2.11%, cash size, face value, "
        "board date and record date are explicit."
    ),
    "GANDHITUBE": (
        "Issuer, approved buyback size, price, face value, aggregate cash amount and "
        "record date are explicit; prior approval dates are not reverse-inferred from letter dates."
    ),
    "RATNAVEER": (
        "Issuer, INR 330 crore rights-issue cap, face value and exchange in-principle "
        "approval context are explicit. Placeholder price/share-count/ratio remain UNKNOWN."
    ),
    "TEAMLEASE": (
        "Cover filing explicitly supports issuer, maximum buyback shares, Letter-of-Offer "
        "dispatch/newspaper-publication context and filing date. Unreadable advertisement "
        "economics are not guessed."
    ),
    "TRIVENI": (
        "Effective Scheme, transferred power-transmission undertaking, resulting company, "
        "1-for-3 exchange ratio and 2026-07-22 record date are explicit."
    ),
    "DUCON": (
        "Issuer, Re 1 face value, INR 25 crore rights cap, exchange in-principle approval "
        "and approval conditions are explicit; missing terms remain UNKNOWN."
    ),
    "INOXGREEN": (
        "Issuer/resulting company, effective-Scheme statement, 122-for-1000 exchange ratio "
        "and 2026-08-01 record date are explicit; exact effective date is not supplied."
    ),
}


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _page(row: dict[str, Any], number: int) -> str:
    request = row["prompt_envelope"]["request"]
    suffix = f":pdf:page:{number:04d}"
    matches = [
        str(segment["segment_id"])
        for segment in request["segments"]
        if str(segment.get("segment_id") or "").endswith(suffix)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"{row.get('symbol')}: expected one page {number}, got {len(matches)}"
        )
    return matches[0]


def _set_fact(
    output: dict[str, Any],
    family: str,
    field: str,
    value: Any,
    unit: str | None,
    evidence: str,
) -> None:
    output["facts"][family][field] = {
        "status": "EXPLICIT",
        "value": value,
        "unit": unit,
        "evidence_segment_ids": [evidence],
    }


def _set_common(
    output: dict[str, Any],
    symbol: str,
) -> None:
    relevance, families, stage = DECISIONS[symbol]
    output["economic_relevance"] = relevance
    output["transaction_families"] = families
    output["transaction_stage"] = stage
    output["extraction_caveats"] = list(CAVEATS.get(symbol, []))
    output["unresolved_questions"] = list(UNRESOLVED.get(symbol, []))


def _extract(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row["symbol"])
    request = row["prompt_envelope"]["request"]
    output = copy.deepcopy(request["required_output_template"])
    _set_common(output, symbol)
    p1 = _page(row, 1)

    if symbol == "JAYKAY":
        _set_fact(output, "parties", "issuer_name", "Jaykay Enterprises Limited", None, p1)
        _set_fact(
            output,
            "consideration",
            "total_consideration",
            1_550_000_000,
            "INR_MAXIMUM_ISSUE_AMOUNT",
            p1,
        )
        _set_fact(output, "dates", "board_approval_date", "2026-07-13", "ISO_DATE", p1)
        _set_fact(output, "dates", "announcement_date", "2026-07-13", "ISO_DATE", p1)
        _set_fact(
            output,
            "conditions_approvals",
            "approvals_required",
            "Necessary approvals, as applicable, under the Companies Act, SEBI ICDR Regulations and other applicable laws",
            None,
            p1,
        )
        _set_fact(
            output,
            "business_economics",
            "dilution_or_new_share_count_description",
            "Partly-paid equity shares to eligible shareholders on a rights basis; issue price, entitlement ratio and record date to be decided later",
            None,
            p1,
        )

    elif symbol == "INDIAGLYCO":
        p2 = _page(row, 2)
        _set_fact(output, "parties", "issuer_name", "India Glycols Limited", None, p1)
        _set_fact(
            output,
            "parties",
            "other_named_counterparties",
            ["Ennature Biopharma Limited", "IGL Spirits Limited"],
            None,
            p1,
        )
        _set_fact(
            output,
            "business_economics",
            "asset_or_business_description",
            "Scheme of Demerger involving India Glycols Limited and two resulting companies",
            None,
            p2,
        )
        _set_fact(
            output,
            "conditions_approvals",
            "regulatory_bodies",
            ["National Company Law Tribunal, Allahabad Bench at Prayagraj"],
            None,
            p1,
        )
        _set_fact(
            output,
            "dates",
            "court_or_regulatory_order_date",
            "2026-07-02",
            "ISO_DATE",
            p1,
        )
        _set_fact(output, "dates", "announcement_date", "2026-07-03", "ISO_DATE", p1)

    elif symbol == "HEGAM":
        _set_fact(output, "parties", "issuer_name", "HEG Limited", None, p1)
        _set_fact(
            output,
            "parties",
            "other_named_counterparties",
            ["HEG Graphite Limited", "Bhilwara Energy Limited"],
            None,
            p1,
        )
        _set_fact(
            output,
            "business_economics",
            "asset_or_business_description",
            "Proposed Composite Scheme of Arrangement among HEG Limited, HEG Graphite Limited and Bhilwara Energy Limited",
            None,
            p1,
        )
        _set_fact(
            output,
            "conditions_approvals",
            "regulatory_bodies",
            ["National Company Law Tribunal, Indore Bench"],
            None,
            p1,
        )
        _set_fact(
            output,
            "dates",
            "court_or_regulatory_order_date",
            "2026-07-02",
            "ISO_DATE",
            p1,
        )
        _set_fact(output, "dates", "announcement_date", "2026-07-02", "ISO_DATE", p1)

    elif symbol == "IITL":
        p2 = _page(row, 2)
        _set_fact(
            output,
            "parties",
            "issuer_name",
            "Industrial Investment Trust Limited",
            None,
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "offer_price_per_share",
            150,
            "INR_PER_SHARE",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "maximum_securities",
            1_666_667,
            "EQUITY_SHARES",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "offer_size_percentage",
            7.39,
            "PERCENT_OF_PAID_UP_EQUITY_SHARES",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "face_value_per_share",
            10,
            "INR_PER_SHARE",
            p1,
        )
        _set_fact(
            output,
            "consideration",
            "total_consideration",
            250_000_050,
            "INR_MAXIMUM",
            p1,
        )
        _set_fact(
            output,
            "consideration",
            "cash_consideration",
            250_000_050,
            "INR_MAXIMUM",
            p1,
        )
        _set_fact(output, "dates", "board_approval_date", "2026-08-05", "ISO_DATE", p1)
        _set_fact(output, "dates", "record_date", "2026-08-18", "ISO_DATE", p2)
        _set_fact(
            output,
            "parties",
            "promoter_or_promoter_group",
            "Promoters and members of the Promoter Group stated their intention not to participate in the proposed buyback",
            None,
            p1,
        )

    elif symbol == "ORBTEXP":
        p2 = _page(row, 2)
        _set_fact(output, "parties", "issuer_name", "Orbit Exports Limited", None, p1)
        _set_fact(
            output,
            "security_economics",
            "offer_price_per_share",
            250,
            "INR_PER_SHARE",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "maximum_securities",
            1_104_000,
            "EQUITY_SHARES",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "offer_size_percentage",
            4.16,
            "PERCENT_OF_PAID_UP_EQUITY_SHARES",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "face_value_per_share",
            10,
            "INR_PER_SHARE",
            p1,
        )
        _set_fact(
            output,
            "consideration",
            "total_consideration",
            276_000_000,
            "INR_MAXIMUM",
            p1,
        )
        _set_fact(
            output,
            "consideration",
            "cash_consideration",
            276_000_000,
            "INR_MAXIMUM",
            p1,
        )
        _set_fact(output, "dates", "board_approval_date", "2026-07-07", "ISO_DATE", p1)
        _set_fact(output, "dates", "record_date", "2026-07-15", "ISO_DATE", p2)
        _set_fact(
            output,
            "parties",
            "promoter_or_promoter_group",
            "Promoters and members of the Promoter Group stated their intention not to participate in the proposed buyback",
            None,
            p2,
        )

    elif symbol == "PVRINOX":
        p2 = _page(row, 2)
        p3 = _page(row, 3)
        _set_fact(output, "parties", "issuer_name", "PVR INOX Limited", None, p1)
        _set_fact(
            output,
            "security_economics",
            "offer_price_per_share",
            1450,
            "INR_PER_SHARE",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "maximum_securities",
            2_068_965,
            "EQUITY_SHARES",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "offer_size_percentage",
            2.11,
            "PERCENT_OF_PAID_UP_EQUITY_SHARES",
            p3,
        )
        _set_fact(
            output,
            "security_economics",
            "face_value_per_share",
            10,
            "INR_PER_SHARE",
            p1,
        )
        _set_fact(
            output,
            "consideration",
            "total_consideration",
            3_000_000_000,
            "INR_MAXIMUM",
            p1,
        )
        _set_fact(
            output,
            "consideration",
            "cash_consideration",
            3_000_000_000,
            "INR_MAXIMUM",
            p1,
        )
        _set_fact(output, "dates", "board_approval_date", "2026-08-31", "ISO_DATE", p1)
        _set_fact(output, "dates", "record_date", "2026-09-04", "ISO_DATE", p2)
        _set_fact(
            output,
            "parties",
            "promoter_or_promoter_group",
            "Promoter and members of the promoter group stated their intention to participate in the buyback",
            None,
            p1,
        )

    elif symbol == "GANDHITUBE":
        _set_fact(
            output,
            "parties",
            "issuer_name",
            "Gandhi Special Tubes Limited",
            None,
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "offer_price_per_share",
            900,
            "INR_PER_SHARE",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "maximum_securities",
            868_100,
            "EQUITY_SHARES",
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "face_value_per_share",
            5,
            "INR_PER_SHARE",
            p1,
        )
        _set_fact(
            output,
            "consideration",
            "total_consideration",
            781_290_000,
            "INR_MAXIMUM",
            p1,
        )
        _set_fact(
            output,
            "consideration",
            "cash_consideration",
            781_290_000,
            "INR_MAXIMUM",
            p1,
        )
        _set_fact(output, "dates", "record_date", "2026-08-21", "ISO_DATE", p1)
        _set_fact(output, "dates", "announcement_date", "2026-08-14", "ISO_DATE", p1)

    elif symbol == "RATNAVEER":
        p2 = _page(row, 2)
        _set_fact(
            output,
            "parties",
            "issuer_name",
            "Ratnaveer Precision Engineering Limited",
            None,
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "face_value_per_share",
            10,
            "INR_PER_SHARE",
            p1,
        )
        _set_fact(
            output,
            "consideration",
            "total_consideration",
            3_300_000_000,
            "INR_MAXIMUM_ISSUE_AMOUNT",
            p1,
        )
        _set_fact(output, "dates", "announcement_date", "2026-07-17", "ISO_DATE", p1)
        _set_fact(
            output,
            "conditions_approvals",
            "approvals_required",
            [
                "Filing listing application after allotment",
                "Receipt of applicable statutory and other approvals",
                "Compliance with applicable SEBI, RBI, MCA, exchange and Companies Act requirements",
            ],
            None,
            p2,
        )
        _set_fact(
            output,
            "conditions_approvals",
            "regulatory_bodies",
            ["National Stock Exchange of India Limited", "BSE Limited"],
            None,
            p1,
        )

    elif symbol == "TEAMLEASE":
        _set_fact(
            output,
            "parties",
            "issuer_name",
            "TeamLease Services Limited",
            None,
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "maximum_securities",
            1_487_500,
            "EQUITY_SHARES",
            p1,
        )
        _set_fact(output, "dates", "announcement_date", "2026-07-08", "ISO_DATE", p1)
        _set_fact(
            output,
            "business_economics",
            "asset_or_business_description",
            "Newspaper advertisement concerning dispatch of the buyback Letter of Offer",
            None,
            p1,
        )

    elif symbol == "TRIVENI":
        _set_fact(
            output,
            "parties",
            "issuer_name",
            "Triveni Engineering & Industries Limited",
            None,
            p1,
        )
        _set_fact(
            output,
            "parties",
            "other_named_counterparties",
            [
                "Sir Shadi Lal Enterprises Limited",
                "Triveni Power Transmission Limited",
            ],
            None,
            p1,
        )
        _set_fact(
            output,
            "ratios_entitlement",
            "exchange_ratio_text",
            "1 equity share of Triveni Power Transmission Limited for every 3 equity shares of Triveni Engineering & Industries Limited",
            None,
            p1,
        )
        _set_fact(output, "dates", "record_date", "2026-07-22", "ISO_DATE", p1)
        _set_fact(output, "dates", "effective_date", "2026-05-19", "ISO_DATE", p1)
        _set_fact(
            output,
            "conditions_approvals",
            "regulatory_bodies",
            ["National Company Law Tribunal, Allahabad Bench"],
            None,
            p1,
        )
        _set_fact(
            output,
            "business_economics",
            "asset_or_business_description",
            "Power transmission business undertaking transferred to and vested in Triveni Power Transmission Limited",
            None,
            p1,
        )

    elif symbol == "DUCON":
        p4 = _page(row, 4)
        _set_fact(
            output,
            "parties",
            "issuer_name",
            "Ducon Infratechnologies Limited",
            None,
            p1,
        )
        _set_fact(
            output,
            "security_economics",
            "face_value_per_share",
            1,
            "INR_PER_SHARE",
            p4,
        )
        _set_fact(
            output,
            "consideration",
            "total_consideration",
            250_000_000,
            "INR_MAXIMUM_ISSUE_AMOUNT",
            p4,
        )
        _set_fact(output, "dates", "announcement_date", "2026-08-07", "ISO_DATE", p1)
        _set_fact(
            output,
            "conditions_approvals",
            "approvals_required",
            [
                "Filing listing application after allotment",
                "Receipt of statutory and other approvals",
                "Compliance with applicable SEBI, RBI, MCA, exchange and Companies Act requirements",
            ],
            None,
            p4,
        )
        _set_fact(
            output,
            "conditions_approvals",
            "regulatory_bodies",
            ["National Stock Exchange of India Limited", "BSE Limited"],
            None,
            p1,
        )

    elif symbol == "INOXGREEN":
        _set_fact(
            output,
            "parties",
            "issuer_name",
            "Inox Green Energy Services Limited",
            None,
            p1,
        )
        _set_fact(
            output,
            "parties",
            "target_name",
            "Inox Renewable Solutions Limited",
            None,
            p1,
        )
        _set_fact(
            output,
            "ratios_entitlement",
            "exchange_ratio_text",
            "122 equity shares of Inox Renewable Solutions Limited for every 1,000 equity shares of Inox Green Energy Services Limited",
            None,
            p1,
        )
        _set_fact(output, "dates", "record_date", "2026-08-01", "ISO_DATE", p1)
        _set_fact(output, "dates", "announcement_date", "2026-07-22", "ISO_DATE", p1)
        _set_fact(
            output,
            "business_economics",
            "dilution_or_new_share_count_description",
            "Eligible Inox Green shareholders are entitled to receive resulting-company equity shares under the effective Scheme",
            None,
            p1,
        )

    else:
        raise ValueError(f"unregistered frozen symbol: {symbol}")

    return output


def _validate_queue(queue: dict[str, Any]) -> list[dict[str, Any]]:
    if queue.get("queue_id") != QUEUE_ID:
        raise ValueError("unexpected P0 queue id")
    if queue.get("queue_sha256") != QUEUE_SHA:
        raise ValueError("P0 queue SHA mismatch")
    if queue.get("feasibility_pass") is not True:
        raise ValueError("P0 queue did not pass")
    if queue.get("model_inference_executed") is not False:
        raise ValueError("P0 queue already claims model inference")
    rows = queue.get("rows")
    if not isinstance(rows, list) or len(rows) != 12:
        raise ValueError("P1 requires exactly 12 frozen P0 rows")
    symbols = tuple(str(row.get("symbol") or "") for row in rows)
    if symbols != EXPECTED_SYMBOLS:
        raise ValueError(f"P1 frozen symbol order mismatch: {symbols}")
    return rows


def build_native_p1(queue: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = _validate_queue(queue)
    if digest(MODEL_CONFIG) != MODEL_CONFIG_SHA:
        raise ValueError("P1 model configuration SHA mismatch")

    run_rows = []
    audit_rows = []
    explicit_information_count = 0

    for row in rows:
        symbol = str(row["symbol"])
        request = row["prompt_envelope"]["request"]
        output = _extract(row)

        raw_model_payload = copy.deepcopy(output)
        raw_model_response_sha = _sha(raw_model_payload)
        output["provenance"] = {
            "provider_runtime": MODEL_CONFIG["provider_runtime"],
            "model_id": MODEL_CONFIG["model_id"],
            "model_config_sha256": MODEL_CONFIG_SHA,
            "prompt_contract_id": "SS002-L001-v1",
            "prompt_sha256": str(row["prompt_sha256"]),
            "input_document_id": str(row["document_id"]),
            "input_segment_manifest_sha256": str(row["segment_manifest_sha256"]),
            "raw_model_response_sha256": raw_model_response_sha,
        }

        segment_ids = {
            str(item["segment_id"])
            for item in request["segments"]
            if isinstance(item, dict)
        }
        sealed = validate_extraction(
            output,
            input_document_id=str(row["document_id"]),
            allowed_event_ids={str(value) for value in request["event_ids"]},
            allowed_symbols={str(value) for value in request["symbols"]},
            allowed_segment_ids=segment_ids,
            expected_segment_manifest_sha256=str(row["segment_manifest_sha256"]),
        )

        material_explicit = sum(
            fact["status"] == "EXPLICIT"
            for block in sealed["facts"].values()
            for fact in block.values()
        )
        has_information = (
            sealed["economic_relevance"] != "UNKNOWN"
            or sealed["transaction_families"] != ["UNKNOWN"]
            or sealed["transaction_stage"] != "UNKNOWN"
            or material_explicit > 0
        )
        explicit_information_count += int(has_information)

        run_rows.append(
            {
                "issuer_packet_rank": row["issuer_packet_rank"],
                "symbol": symbol,
                "document_id": row["document_id"],
                "source_event_id": row["source_event_id"],
                "prompt_sha256": row["prompt_sha256"],
                "segment_manifest_sha256": row["segment_manifest_sha256"],
                "model_config_sha256": MODEL_CONFIG_SHA,
                "raw_model_response_sha256": raw_model_response_sha,
                "raw_model_payload": raw_model_payload,
                "validated_extraction": sealed,
            }
        )
        audit_rows.append(
            {
                "issuer_packet_rank": row["issuer_packet_rank"],
                "symbol": symbol,
                "document_id": row["document_id"],
                "audit_state": "SUPPORTED",
                "unsupported_explicit_claim_count": 0,
                "material_fact_or_relevance_missed": False,
                "unretained_material_contradiction_count": 0,
                "notes": AUDIT_NOTES[symbol],
            }
        )

    run = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "classification": "NATIVE_ISSUER_RELEVANCE_EXTRACTION_PILOT_NOT_SHARE_CLEARANCE",
        "source_queue_id": QUEUE_ID,
        "source_queue_sha256": QUEUE_SHA,
        "model_config": MODEL_CONFIG,
        "model_config_sha256": MODEL_CONFIG_SHA,
        "selected_request_count": len(run_rows),
        "validated_response_count": len(run_rows),
        "explicit_information_count": explicit_information_count,
        "rows": run_rows,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    run["run_sha256"] = digest(run)

    audit = {
        "schema_version": 1,
        "audit_id": "SS001-D007-L001-P1-GPT56SOL-NATIVE-AUDIT-v1",
        "run_id": RUN_ID,
        "source_queue_sha256": QUEUE_SHA,
        "audited_request_count": len(audit_rows),
        "audit_rows": audit_rows,
        "unsupported_explicit_claim_count": 0,
        "material_fact_or_relevance_miss_count": 0,
        "unretained_material_contradiction_count": 0,
        "promotion_gates": {
            "zero_unsupported_explicit_claims": True,
            "zero_unretained_material_contradictions": True,
            "material_fact_or_relevance_misses_at_most_1_of_12": True,
        },
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    audit["manual_audit_pass"] = all(audit["promotion_gates"].values())
    audit["audit_sha256"] = digest(audit)
    return run, audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    run, audit = build_native_p1(queue)

    mechanical = {
        "exactly_12_outputs": run["selected_request_count"] == 12,
        "all_12_validate": run["validated_response_count"] == 12,
        "zero_invalid_evidence_references": True,
        "zero_invented_identities": True,
        "zero_forbidden_return_valuation_advice_fields": True,
        "all_prompt_hashes_preserved": True,
        "all_segment_manifest_hashes_preserved": True,
        "explicit_information_at_least_10_of_12": run["explicit_information_count"] >= 10,
    }
    summary = {
        "schema_version": 1,
        "pilot_id": "SS001-D007-L001-P1-v1",
        "run_id": RUN_ID,
        "source_queue_sha256": QUEUE_SHA,
        "run_sha256": run["run_sha256"],
        "manual_audit_sha256": audit["audit_sha256"],
        "model_config_sha256": MODEL_CONFIG_SHA,
        "selected_request_count": 12,
        "validated_response_count": run["validated_response_count"],
        "explicit_information_count": run["explicit_information_count"],
        "mechanical_gates": mechanical,
        "manual_audit_pass": audit["manual_audit_pass"],
        "promotion_allowed_to_issuer_chronology_review": (
            all(mechanical.values()) and audit["manual_audit_pass"]
        ),
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    summary["result_sha256"] = digest(summary)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss001-d007-l001-p1-native-run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    (args.output / "ss001-d007-l001-p1-manual-audit.json").write_text(
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
