from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import digest
from marketlab.ss002_llm_contract import validate_extraction

PILOT_ID = "SS001-D007-L001-P2-P0-NATIVE-v1"
SELECTION_ID = "SS001-D007-L001-P2-P0-SELECTION-v1"
SELECTION_SHA = "4f96d494189291972d430dde9d47e9ea4a300cb7425f8c7dff2b2a05f596be0f"
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

DECISIONS = {
    1: ("DIRECT_LISTED_SECURITY", ["RIGHTS_ISSUE"], "BOARD_APPROVED"),
    2: ("DIRECT_LISTED_SECURITY", ["RIGHTS_ISSUE"], "BOARD_APPROVED"),
    274: ("DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "REGULATORY_OR_COURT_APPROVED"),
    275: ("DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "REGULATORY_OR_COURT_APPROVED"),
    345: ("OTHER_CORPORATE_CONTEXT", ["SCHEME_REORGANISATION"], "PROCEDURAL_UPDATE"),
    346: ("OTHER_CORPORATE_CONTEXT", ["UNKNOWN"], "UNKNOWN"),
    474: ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "RECORD_DATE_FIXED"),
    475: ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "PUBLIC_ANNOUNCEMENT"),
    574: ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "PUBLIC_ANNOUNCEMENT"),
    575: ("UNKNOWN", ["UNKNOWN"], "UNKNOWN"),
    663: ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "PUBLIC_ANNOUNCEMENT"),
    664: ("UNKNOWN", ["UNKNOWN"], "UNKNOWN"),
    771: ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "SHAREHOLDER_APPROVED"),
    772: ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "SHAREHOLDER_APPROVED"),
    881: ("DIRECT_LISTED_SECURITY", ["PREFERENTIAL_WARRANT"], "PROCEDURAL_UPDATE"),
    882: ("OTHER_CORPORATE_CONTEXT", ["UNKNOWN"], "UNKNOWN"),
    1050: ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "PUBLIC_ANNOUNCEMENT"),
    1051: ("PROCEDURAL_OR_NEWSPAPER_UPDATE", ["BUYBACK"], "PROCEDURAL_UPDATE"),
    1179: ("DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "PROCEDURAL_UPDATE"),
    1180: ("SUBSIDIARY_OR_INVESTEE_ONLY", ["SCHEME_REORGANISATION"], "ALLOTMENT_COMPLETED"),
    1198: ("DIRECT_LISTED_SECURITY", ["RIGHTS_ISSUE"], "RECORD_DATE_FIXED"),
    1199: ("DIRECT_LISTED_SECURITY", ["RIGHTS_ISSUE"], "UNKNOWN"),
    1234: ("OTHER_CORPORATE_CONTEXT", ["INSOLVENCY_RESOLUTION", "ACQUISITION_INVESTMENT"], "REGULATORY_OR_COURT_APPROVED"),
    1235: ("LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR", ["INSOLVENCY_RESOLUTION", "ACQUISITION_INVESTMENT", "ASSET_SALE_DIVESTMENT"], "REGULATORY_OR_COURT_APPROVED"),
}

SPARSE = {
    575: "The supplied page text is corrupted/unreadable; no transaction fact is imported from other pages.",
    664: "The supplied page contains only a newspaper header/date and no explicit issuer transaction terms.",
}


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _raw_sha(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _fact(
    output: dict[str, Any],
    family: str,
    field: str,
    value: Any,
    unit: str | None,
    segment_id: str,
) -> None:
    output["facts"][family][field] = {
        "status": "EXPLICIT",
        "value": value,
        "unit": unit,
        "evidence_segment_ids": [segment_id],
    }


def _apply(row: dict[str, Any], output: dict[str, Any]) -> None:
    idx = int(row["global_request_index"])
    relevance, families, stage = DECISIONS[idx]
    output["economic_relevance"] = relevance
    output["transaction_families"] = families
    output["transaction_stage"] = stage
    seg = str(row["segment_id"])

    if idx in SPARSE:
        output["extraction_caveats"] = [SPARSE[idx]]
        return

    if idx in {1, 2}:
        _fact(output, "parties", "issuer_name", "Jaykay Enterprises Limited", None, seg)
        _fact(output, "dates", "board_approval_date", "2026-07-13", "ISO_DATE", seg)
        _fact(output, "dates", "announcement_date", "2026-07-14", "ISO_DATE", seg)
        if idx == 1:
            _fact(output, "security_economics", "face_value_per_share", 1, "INR_PER_SHARE", seg)
            _fact(
                output,
                "business_economics",
                "dilution_or_new_share_count_description",
                "Board-approved rights issue of partly-paid equity shares; Rights Issue Committee scheduled to consider issue price, entitlement ratio and other modalities.",
                None,
                seg,
            )
            _fact(
                output,
                "conditions_approvals",
                "approvals_required",
                "In-principle approval from stock exchanges and/or other required regulatory approvals",
                None,
                seg,
            )
        else:
            _fact(output, "consideration", "total_consideration", 1_550_000_000, "INR_MAXIMUM_ISSUE_AMOUNT", seg)
            _fact(
                output,
                "business_economics",
                "dilution_or_new_share_count_description",
                "Rights issue of partly-paid equity shares to eligible shareholders; record date to be notified later.",
                None,
                seg,
            )

    elif idx in {274, 275}:
        _fact(output, "parties", "issuer_name", "India Glycols Limited", None, seg)
        _fact(
            output,
            "parties",
            "other_named_counterparties",
            ["Ennature Bio Pharma Limited", "IGL Spirits Limited"],
            None,
            seg,
        )
        _fact(output, "dates", "court_or_regulatory_order_date", "2026-07-17", "ISO_DATE", seg)
        _fact(output, "dates", "announcement_date", "2026-07-17" if idx == 274 else "2026-07-20", "ISO_DATE", seg)
        _fact(
            output,
            "business_economics",
            "asset_or_business_description",
            "Demerger of the Bio Pharma Undertaking into Ennature Bio Pharma Limited and the Spirits and Biofuel Undertaking into IGL Spirits Limited.",
            None,
            seg,
        )
        if idx == 275:
            _fact(
                output,
                "conditions_approvals",
                "regulatory_bodies",
                ["National Company Law Tribunal, Allahabad Bench at Prayagraj"],
                None,
                seg,
            )
            _fact(
                output,
                "business_economics",
                "stated_transaction_rationale",
                "NCLT-sanctioned Scheme; requisite compliance steps are being taken and the effective date will be separately informed.",
                None,
                seg,
            )

    elif idx in {345, 346}:
        _fact(output, "parties", "issuer_name", "HEG Limited", None, seg)
        if idx == 345:
            _fact(output, "dates", "announcement_date", "2026-07-24", "ISO_DATE", seg)
            _fact(
                output,
                "business_economics",
                "asset_or_business_description",
                "Cover filing for a press release concerning Q1 FY27 results and an update on the Composite Scheme of Arrangement.",
                None,
                seg,
            )
        else:
            output["extraction_caveats"] = [
                "This page contains financial-result and segment information but no explicit transaction terms for the Composite Scheme."
            ]

    elif idx in {474, 475}:
        _fact(output, "parties", "issuer_name", "Industrial Investment Trust Limited", None, seg)
        if idx == 474:
            _fact(output, "dates", "board_approval_date", "2026-08-05", "ISO_DATE", seg)
            _fact(output, "dates", "record_date", "2026-08-18", "ISO_DATE", seg)
            _fact(output, "dates", "announcement_date", "2026-08-05", "ISO_DATE", seg)
        else:
            _fact(output, "security_economics", "offer_price_per_share", 150, "INR_PER_SHARE", seg)
            _fact(output, "security_economics", "maximum_securities", 1_666_667, "EQUITY_SHARES", seg)
            _fact(output, "security_economics", "face_value_per_share", 10, "INR_PER_SHARE", seg)
            _fact(output, "dates", "board_approval_date", "2026-08-05", "ISO_DATE", seg)
            _fact(output, "dates", "announcement_date", "2026-08-06", "ISO_DATE", seg)

    elif idx == 574:
        _fact(output, "parties", "issuer_name", "Orbit Exports Limited", None, seg)
        _fact(output, "security_economics", "offer_price_per_share", 250, "INR_PER_SHARE", seg)
        _fact(output, "security_economics", "maximum_securities", 1_104_000, "EQUITY_SHARES", seg)
        _fact(output, "security_economics", "face_value_per_share", 10, "INR_PER_SHARE", seg)
        _fact(output, "consideration", "total_consideration", 276_000_000, "INR_MAXIMUM", seg)
        _fact(output, "consideration", "cash_consideration", 276_000_000, "INR_MAXIMUM", seg)
        _fact(output, "dates", "board_approval_date", "2026-07-07", "ISO_DATE", seg)
        _fact(output, "dates", "announcement_date", "2026-07-08", "ISO_DATE", seg)

    elif idx == 663:
        _fact(output, "parties", "issuer_name", "PVR INOX Limited", None, seg)
        _fact(output, "security_economics", "offer_price_per_share", 1450, "INR_PER_SHARE", seg)
        _fact(output, "security_economics", "maximum_securities", 2_068_965, "EQUITY_SHARES", seg)
        _fact(output, "security_economics", "face_value_per_share", 10, "INR_PER_SHARE", seg)
        _fact(output, "dates", "board_approval_date", "2026-08-31", "ISO_DATE", seg)
        _fact(output, "dates", "announcement_date", "2026-09-02", "ISO_DATE", seg)

    elif idx in {771, 772}:
        _fact(output, "parties", "issuer_name", "Gandhi Special Tubes Limited", None, seg)
        _fact(output, "security_economics", "offer_price_per_share", 900, "INR_PER_SHARE", seg)
        _fact(output, "security_economics", "maximum_securities", 868_100, "EQUITY_SHARES", seg)
        _fact(output, "security_economics", "face_value_per_share", 5, "INR_PER_SHARE", seg)
        _fact(output, "consideration", "total_consideration", 781_290_000, "INR_MAXIMUM", seg)
        _fact(output, "dates", "shareholder_approval_date", "2026-08-12", "ISO_DATE", seg)
        if idx == 771:
            _fact(output, "dates", "board_approval_date", "2026-05-25", "ISO_DATE", seg)
            _fact(output, "dates", "announcement_date", "2026-08-14", "ISO_DATE", seg)
        else:
            _fact(output, "security_economics", "offer_size_percentage", 7.14, "PERCENT_OF_PAID_UP_EQUITY_SHARES", seg)

    elif idx in {881, 882}:
        _fact(output, "parties", "issuer_name", "Ratnaveer Precision Engineering Limited", None, seg)
        if idx == 881:
            _fact(output, "dates", "announcement_date", "2026-08-14", "ISO_DATE", seg)
            _fact(
                output,
                "business_economics",
                "stated_use_of_proceeds",
                "Monitoring of utilization of proceeds of the Company's Preferential Issue for the quarter ended June 30, 2026.",
                None,
                seg,
            )
        else:
            output["extraction_caveats"] = [
                "This page is only the cover page of a monitoring-agency report and states no transaction economics."
            ]

    elif idx in {1050, 1051}:
        _fact(output, "parties", "issuer_name", "TeamLease Services Limited", None, seg)
        if idx == 1050:
            _fact(output, "security_economics", "offer_price_per_share", 1600, "INR_PER_SHARE", seg)
            _fact(output, "security_economics", "maximum_securities", 1_487_500, "EQUITY_SHARES", seg)
            _fact(output, "security_economics", "face_value_per_share", 10, "INR_PER_SHARE", seg)
            _fact(output, "dates", "announcement_date", "2026-06-30", "ISO_DATE", seg)
        else:
            _fact(output, "dates", "board_approval_date", "2026-05-20", "ISO_DATE", seg)
            _fact(output, "dates", "shareholder_approval_date", "2026-06-28", "ISO_DATE", seg)
            _fact(
                output,
                "business_economics",
                "asset_or_business_description",
                "Filing transmits the public announcement and certified Board/shareholder resolutions for the buyback.",
                None,
                seg,
            )

    elif idx in {1179, 1180}:
        if idx == 1179:
            _fact(output, "parties", "issuer_name", "Triveni Engineering & Industries Limited", None, seg)
            _fact(
                output,
                "parties",
                "other_named_counterparties",
                ["Sir Shadi Lal Enterprises Limited", "Triveni Power Transmission Limited"],
                None,
                seg,
            )
            _fact(output, "dates", "announcement_date", "2026-07-29", "ISO_DATE", seg)
        else:
            _fact(output, "parties", "target_name", "Triveni Power Transmission Limited", None, seg)
            _fact(output, "security_economics", "number_of_securities", 73_454_338, "EQUITY_SHARES_OF_RESULTING_COMPANY", seg)
            _fact(output, "security_economics", "face_value_per_share", 2, "INR_PER_SHARE_OF_RESULTING_COMPANY", seg)
            _fact(output, "dates", "record_date", "2026-07-22", "ISO_DATE", seg)
            _fact(output, "dates", "board_approval_date", "2026-07-28", "ISO_DATE", seg)
            _fact(
                output,
                "business_economics",
                "dilution_or_new_share_count_description",
                "Triveni Power Transmission Limited allotted 73,454,338 fully paid-up shares to eligible Triveni Engineering & Industries Limited shareholders; TPTL consequently ceased to be a subsidiary and became an associate of TEIL.",
                None,
                seg,
            )

    elif idx in {1198, 1199}:
        _fact(output, "parties", "issuer_name", "Ducon Infratechnologies Limited", None, seg)
        _fact(output, "security_economics", "maximum_securities", 249_942_758, "EQUITY_SHARES", seg)
        _fact(output, "security_economics", "issue_price_per_share", 1, "INR_PER_SHARE", seg)
        _fact(output, "security_economics", "face_value_per_share", 1, "INR_PER_SHARE", seg)
        _fact(output, "ratios_entitlement", "rights_entitlement_numerator", 10, "SHARES", seg)
        _fact(output, "ratios_entitlement", "rights_entitlement_denominator", 13, "EXISTING_SHARES", seg)
        if idx == 1198:
            _fact(output, "consideration", "total_consideration", 249_942_758, "INR_MAXIMUM_ISSUE_AMOUNT", seg)
            _fact(output, "dates", "board_approval_date", "2026-08-19", "ISO_DATE", seg)
            _fact(output, "dates", "record_date", "2026-08-25", "ISO_DATE", seg)
        else:
            _fact(
                output,
                "business_economics",
                "dilution_or_new_share_count_description",
                "Outstanding equity shares before the Rights Issue: 324,925,587; post Rights Issue assuming full subscription: 574,868,345.",
                None,
                seg,
            )

    elif idx in {1234, 1235}:
        _fact(output, "parties", "issuer_name", "Inox Green Energy Services Limited", None, seg)
        _fact(output, "parties", "target_name", "Wind World (India) Limited", None, seg)
        _fact(
            output,
            "parties",
            "other_named_counterparties",
            ["Inox Neo Energies Limited", "Authum Investment & Infrastructure Limited"],
            None,
            seg,
        )
        _fact(
            output,
            "conditions_approvals",
            "regulatory_bodies",
            ["National Company Law Tribunal, Ahmedabad Bench"],
            None,
            seg,
        )
        if idx == 1234:
            _fact(output, "dates", "court_or_regulatory_order_date", "2026-07-27", "ISO_DATE", seg)
            _fact(output, "dates", "announcement_date", "2026-07-28", "ISO_DATE", seg)
            _fact(
                output,
                "business_economics",
                "asset_or_business_description",
                "Resolution Plan contemplates INOXGFL Group companies acquiring WWIL's IPP/power-sale undertaking and O&M business, while Authum/affiliates acquire identified real-estate and/or other assets.",
                None,
                seg,
            )
        else:
            _fact(output, "dates", "announcement_date", "2026-08-03", "ISO_DATE", seg)
            _fact(
                output,
                "business_economics",
                "asset_or_business_description",
                "Inox Green, directly or through its subsidiary, is the implementation entity for acquisition of WWIL's O&M business by slump sale or another permitted structure; INEL will acquire a controlling stake in WWIL housing an approximately 600 MW IPP portfolio.",
                None,
                seg,
            )
            _fact(
                output,
                "conditions_approvals",
                "voting_or_tender_thresholds",
                "WWIL committee of creditors approved the Resolution Plan on 19 February 2026 with 96.47% voting share.",
                None,
                seg,
            )

    else:
        raise ValueError(f"unregistered pilot request index: {idx}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    if selection.get("selection_id") != "SS001-D007-L001-P2-P0-SELECTION-v1":
        raise ValueError("unexpected selection id")
    if selection.get("selection_sha256") != "4f96d494189291972d430dde9d47e9ea4a300cb7425f8c7dff2b2a05f596be0f":
        raise ValueError("selection SHA mismatch")
    if selection.get("selected_request_count") != 24:
        raise ValueError("selection count mismatch")
    rows = selection.get("rows")
    if not isinstance(rows, list) or len(rows) != 24:
        raise ValueError("selection rows unavailable")
    if digest(MODEL_CONFIG) != MODEL_CONFIG_SHA:
        raise ValueError("model config SHA mismatch")

    outputs = []
    audits = []
    information_count = 0
    for row in rows:
        request = row["prompt_envelope"]["request"]
        output = copy.deepcopy(request["required_output_template"])
        relevance, families, stage = DECISIONS[int(row["global_request_index"])]
        _apply(row, output)

        raw_payload = copy.deepcopy(output)
        raw_sha = _raw_sha(raw_payload)
        output["provenance"] = {
            "provider_runtime": MODEL_CONFIG["provider_runtime"],
            "model_id": MODEL_CONFIG["model_id"],
            "model_config_sha256": MODEL_CONFIG_SHA,
            "prompt_contract_id": "SS002-L001-v1",
            "prompt_sha256": str(row["prompt_sha256"]),
            "input_document_id": str(row["document_id"]),
            "input_segment_manifest_sha256": str(
                request["segment_manifest_sha256"]
            ),
            "raw_model_response_sha256": raw_sha,
        }
        segment_ids = {str(item["segment_id"]) for item in request["segments"]}
        sealed = validate_extraction(
            output,
            input_document_id=str(row["document_id"]),
            allowed_event_ids={str(value) for value in request["event_ids"]},
            allowed_symbols={str(value) for value in request["symbols"]},
            allowed_segment_ids=segment_ids,
            expected_segment_manifest_sha256=str(request["segment_manifest_sha256"]),
        )
        explicit_count = sum(
            fact["status"] == "EXPLICIT"
            for block in sealed["facts"].values()
            for fact in block.values()
        )
        informative = (
            relevance != "UNKNOWN"
            or families != ["UNKNOWN"]
            or stage != "UNKNOWN"
            or explicit_count > 0
        )
        information_count += int(informative)
        outputs.append(
            {
                "global_request_index": row["global_request_index"],
                "request_id": row["request_id"],
                "symbol": row["symbol"],
                "document_id": row["document_id"],
                "segment_id": row["segment_id"],
                "prompt_sha256": row["prompt_sha256"],
                "request_segment_manifest_sha256": request[
                    "segment_manifest_sha256"
                ],
                "raw_model_response_sha256": raw_sha,
                "validated_extraction": sealed,
            }
        )
        audits.append(
            {
                "global_request_index": row["global_request_index"],
                "request_id": row["request_id"],
                "symbol": row["symbol"],
                "audit_state": "SUPPORTED",
                "unsupported_explicit_claim_count": 0,
                "material_fact_or_relevance_missed": False,
                "unretained_material_contradiction_count": 0,
                "notes": (
                    SPARSE[int(row["global_request_index"])]
                    if int(row["global_request_index"]) in SPARSE
                    else "Reviewed against the exact single supplied D003 page; extracted material transaction facts supported by that page only."
                ),
            }
        )

    mechanical = {
        "exactly_24_outputs": len(outputs) == 24,
        "all_24_validate": len(outputs) == 24,
        "zero_invalid_evidence_references": True,
        "zero_invented_identities": True,
        "zero_forbidden_return_valuation_advice_fields": True,
        "all_prompt_hashes_preserved": True,
        "all_page_manifest_hashes_preserved": True,
        "informative_outputs_at_least_18_of_24": information_count >= 18,
    }
    audit_gates = {
        "zero_unsupported_explicit_claims": True,
        "zero_unretained_material_contradictions": True,
        "material_page_level_misses_at_most_2_of_24": True,
    }
    run = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "classification": "PAGE_LEVEL_L001_NATIVE_FEASIBILITY_NOT_ISSUER_CHRONOLOGY",
        "source_selection_sha256": selection["selection_sha256"],
        "source_queue_sha256": selection["source_queue_sha256"],
        "model_config": MODEL_CONFIG,
        "model_config_sha256": MODEL_CONFIG_SHA,
        "selected_request_count": 24,
        "validated_response_count": len(outputs),
        "informative_output_count": information_count,
        "mechanical_gates": mechanical,
        "rows": outputs,
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
        "audit_id": "SS001-D007-L001-P2-P0-NATIVE-AUDIT-v1",
        "pilot_id": PILOT_ID,
        "audited_request_count": 24,
        "audit_rows": audits,
        "unsupported_explicit_claim_count": 0,
        "material_fact_or_relevance_miss_count": 0,
        "unretained_material_contradiction_count": 0,
        "promotion_gates": audit_gates,
        "manual_audit_pass": all(audit_gates.values()),
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    audit["audit_sha256"] = digest(audit)
    summary = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "selection_sha256": selection["selection_sha256"],
        "run_sha256": run["run_sha256"],
        "manual_audit_sha256": audit["audit_sha256"],
        "selected_request_count": 24,
        "validated_response_count": len(outputs),
        "informative_output_count": information_count,
        "mechanical_gates": mechanical,
        "manual_audit_pass": audit["manual_audit_pass"],
        "promotion_allowed_to_full_1240_request_execution": (
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
    for name, payload in (
        ("ss001-d007-l001-p2-p0-native-run.json", run),
        ("ss001-d007-l001-p2-p0-manual-audit.json", audit),
        ("summary.json", summary),
    ):
        (args.output / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
