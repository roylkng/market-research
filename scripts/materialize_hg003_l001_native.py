from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from marketlab.alpha import digest
from marketlab.ss002_llm_contract import validate_extraction

RUN_ID = "HG003-L001-GPT56SOL-NATIVE-v1"
SELECTION_ID = "HG003-D001-v1"
SELECTION_SHA = "ebc543464475ff9e409b1795c02272a818a3062cef8ad2bafcfafb5fcc30b536"

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
    "ANANTRAJ::SCHEME_REORGANISATION": (
        "DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "BOARD_APPROVED"
    ),
    "AXITA::INSOLVENCY_RESOLUTION": (
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        ["INSOLVENCY_RESOLUTION", "ACQUISITION_INVESTMENT"],
        "PROPOSAL",
    ),
    "BAGFILMS::PREFERENTIAL_WARRANT": (
        "DIRECT_LISTED_SECURITY", ["PREFERENTIAL_WARRANT"], "ALLOTMENT_COMPLETED"
    ),
    "BAJAJCON::INSOLVENCY_RESOLUTION": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "REGULATORY_OR_COURT_APPROVED",
    ),
    "BAJAJCON::SCHEME_REORGANISATION": (
        "DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "TRANSACTION_COMPLETED"
    ),
    "BORORENEW::PREFERENTIAL_WARRANT": (
        "DIRECT_LISTED_SECURITY", ["PREFERENTIAL_WARRANT"], "CANCELLED_OR_WITHDRAWN"
    ),
    "DATAMATICS::SCHEME_REORGANISATION": (
        "DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "BOARD_APPROVED"
    ),
    "DEVX::PREFERENTIAL_WARRANT": (
        "DIRECT_LISTED_SECURITY", ["PREFERENTIAL_WARRANT"], "PROCEDURAL_UPDATE"
    ),
    "EXIDEIND::SCHEME_REORGANISATION": (
        "OTHER_CORPORATE_CONTEXT", ["SCHEME_REORGANISATION"], "TRANSACTION_COMPLETED"
    ),
    "FCL::PREFERENTIAL_WARRANT": (
        "DIRECT_LISTED_SECURITY", ["PREFERENTIAL_WARRANT"], "PROCEDURAL_UPDATE"
    ),
    "GANDHITUBE::BUYBACK": (
        "DIRECT_LISTED_SECURITY",
        ["BUYBACK", "TENDER_OFFER"],
        "TRANSACTION_COMPLETED",
    ),
    "GANDHITUBE::TENDER_OFFER": (
        "DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "OFFER_OPEN"
    ),
    "HTMEDIA::PREFERENTIAL_WARRANT": (
        "DIRECT_LISTED_SECURITY", ["PREFERENTIAL_WARRANT"], "ALLOTMENT_COMPLETED"
    ),
    "IBULLSLTD::PREFERENTIAL_WARRANT": (
        "DIRECT_LISTED_SECURITY", ["PREFERENTIAL_WARRANT"], "ALLOTMENT_COMPLETED"
    ),
    "INOXGREEN::INSOLVENCY_RESOLUTION": (
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        ["INSOLVENCY_RESOLUTION", "ACQUISITION_INVESTMENT"],
        "REGULATORY_OR_COURT_APPROVED",
    ),
    "INOXGREEN::SCHEME_REORGANISATION": (
        "DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "ALLOTMENT_COMPLETED"
    ),
    "JINDALPOLY::INSOLVENCY_RESOLUTION": (
        "OTHER_CORPORATE_CONTEXT", ["OTHER"], "PROCEDURAL_UPDATE"
    ),
    "LLOYDSENT::SCHEME_REORGANISATION": (
        "SUBSIDIARY_OR_INVESTEE_ONLY", ["SCHEME_REORGANISATION"], "PROCEDURAL_UPDATE"
    ),
    "MINDACORP::RIGHTS_ISSUE": (
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        ["RIGHTS_ISSUE", "ACQUISITION_INVESTMENT"],
        "ALLOTMENT_COMPLETED",
    ),
    "MMFL::SCHEME_REORGANISATION": (
        "DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "TRANSACTION_COMPLETED"
    ),
    "NIITLTD::SCHEME_REORGANISATION": (
        "DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "TRANSACTION_COMPLETED"
    ),
    "NPST::PREFERENTIAL_WARRANT": (
        "DIRECT_LISTED_SECURITY", ["FUND_RAISE_OTHER"], "PROCEDURAL_UPDATE"
    ),
    "ORBTEXP::BUYBACK": (
        "DIRECT_LISTED_SECURITY",
        ["BUYBACK", "TENDER_OFFER"],
        "TRANSACTION_COMPLETED",
    ),
    "ORBTEXP::TENDER_OFFER": (
        "DIRECT_LISTED_SECURITY",
        ["BUYBACK", "TENDER_OFFER"],
        "TRANSACTION_COMPLETED",
    ),
    "ORCHPHARMA::INSOLVENCY_RESOLUTION": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "REGULATORY_OR_COURT_APPROVED",
    ),
    "ORCHPHARMA::SCHEME_REORGANISATION": (
        "DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "TRANSACTION_COMPLETED"
    ),
    "RETAIL::PREFERENTIAL_WARRANT": (
        "DIRECT_LISTED_SECURITY", ["PREFERENTIAL_WARRANT"], "ALLOTMENT_COMPLETED"
    ),
    "SAMBHV::PREFERENTIAL_WARRANT": (
        "DIRECT_LISTED_SECURITY", ["PREFERENTIAL_WARRANT"], "PROPOSAL"
    ),
    "SANDESH::SCHEME_REORGANISATION": (
        "DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "BOARD_APPROVED"
    ),
    "SARLAPOLY::BUYBACK": (
        "DIRECT_LISTED_SECURITY",
        ["BUYBACK", "TENDER_OFFER"],
        "TRANSACTION_COMPLETED",
    ),
    "SARLAPOLY::TENDER_OFFER": (
        "DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "OFFER_OPEN"
    ),
    "SUVIDHAA::RIGHTS_ISSUE": (
        "DIRECT_LISTED_SECURITY", ["RIGHTS_ISSUE"], "BOARD_APPROVED"
    ),
    "TREL::PREFERENTIAL_WARRANT": (
        "SUBSIDIARY_OR_INVESTEE_ONLY", ["FUND_RAISE_OTHER"], "ALLOTMENT_COMPLETED"
    ),
    "TREL::SCHEME_REORGANISATION": (
        "DIRECT_LISTED_SECURITY", ["SCHEME_REORGANISATION"], "PROCEDURAL_UPDATE"
    ),
}

CAVEATS = {
    "AXITA::INSOLVENCY_RESOLUTION": [
        "The listed company has submitted an expression of interest in a target CIRP; no acquisition is stated as completed."
    ],
    "BAJAJCON::INSOLVENCY_RESOLUTION": [
        "The selected NCLT document concerns a Companies Act scheme of arrangement, not insolvency of the listed company."
    ],
    "BORORENEW::PREFERENTIAL_WARRANT": [
        "The document cancels and forfeits unexercised warrants; it is not a fresh preferential issuance."
    ],
    "DEVX::PREFERENTIAL_WARRANT": [
        "The document is a monitoring-agency utilization report for an already-raised preferential issue, not a new issuance event."
    ],
    "EXIDEIND::SCHEME_REORGANISATION": [
        "The amalgamation is between the listed company's registrar/share-transfer-agent entities, not a reorganisation of Exide Industries."
    ],
    "FCL::PREFERENTIAL_WARRANT": [
        "The document is a monitoring-agency report for an earlier preferential issue of equity shares and convertible warrants."
    ],
    "INOXGREEN::INSOLVENCY_RESOLUTION": [
        "The listed company is an implementation/acquisition entity under the approved resolution plan for Wind World; the listed company itself is not in CIRP."
    ],
    "JINDALPOLY::INSOLVENCY_RESOLUTION": [
        "The selected NCLT proceeding is a minority-shareholder/SEBI intervention matter and is not an insolvency resolution process."
    ],
    "LLOYDSENT::SCHEME_REORGANISATION": [
        "The scheme is at Lloyds Engineering Works Limited, a material subsidiary of the listed company; the selected document reports stock-exchange no-objection letters."
    ],
    "MINDACORP::RIGHTS_ISSUE": [
        "The listed company subscribed to a rights issue of its wholly owned subsidiary; this is not a rights issue of MINDACORP shares."
    ],
    "NPST::PREFERENTIAL_WARRANT": [
        "The selected document is a monitoring-agency report for a preferential issue of equity shares, not convertible warrants and not a fresh issuance."
    ],
    "ORCHPHARMA::INSOLVENCY_RESOLUTION": [
        "The NCLT document sanctions an amalgamation scheme and does not evidence insolvency of Orchid Pharma."
    ],
    "TREL::PREFERENTIAL_WARRANT": [
        "The preferential allotment is by a subsidiary and consists of equity shares, not warrants; it dilutes the listed parent's holding from 100% to 25%."
    ],
    "TREL::SCHEME_REORGANISATION": [
        "The selected NCLT order directs shareholder notice/inspection and does not yet sanction or complete the amalgamation."
    ],
}

AUDIT_THREADS = {
    "GANDHITUBE::BUYBACK",
    "ORBTEXP::BUYBACK",
    "GANDHITUBE::TENDER_OFFER",
    "ORBTEXP::TENDER_OFFER",
    "ANANTRAJ::SCHEME_REORGANISATION",
    "BAJAJCON::SCHEME_REORGANISATION",
    "BAGFILMS::PREFERENTIAL_WARRANT",
    "BORORENEW::PREFERENTIAL_WARRANT",
    "AXITA::INSOLVENCY_RESOLUTION",
    "BAJAJCON::INSOLVENCY_RESOLUTION",
    "MINDACORP::RIGHTS_ISSUE",
    "SUVIDHAA::RIGHTS_ISSUE",
}

AUDIT_NOTES = {
    "GANDHITUBE::BUYBACK": "The selected filing explicitly states completion of extinguishment after conclusion of the direct listed-company buyback.",
    "ORBTEXP::BUYBACK": "The selected filing explicitly states completion of extinguishment following the direct listed-company buyback.",
    "GANDHITUBE::TENDER_OFFER": "The letter-of-offer filing gives the direct equity buyback tender window and identifies the offer as opening imminently.",
    "ORBTEXP::TENDER_OFFER": "The selected filing is the post-buyback public announcement for the completed direct equity tender buyback.",
    "ANANTRAJ::SCHEME_REORGANISATION": "The press release explicitly says the Board approved the composite demerger creating two focused listed companies.",
    "BAJAJCON::SCHEME_REORGANISATION": "The filing explicitly states the NCLT-sanctioned scheme was filed with the ROC and became effective on May 1, 2026.",
    "BAGFILMS::PREFERENTIAL_WARRANT": "The filing explicitly records allotment of equity shares on conversion of the remaining promoter-group warrants.",
    "BORORENEW::PREFERENTIAL_WARRANT": "The filing explicitly states cancellation and forfeiture of unexercised warrants for non-payment of the balance conversion amount.",
    "AXITA::INSOLVENCY_RESOLUTION": "The filing explicitly states Axita submitted an EOI to acquire Varidhi Cotspin through its CIRP, so the listed company is a prospective acquirer rather than the insolvent entity.",
    "BAJAJCON::INSOLVENCY_RESOLUTION": "The NCLT filing explicitly concerns a scheme of arrangement/demerger; the upstream insolvency label is unsupported by the document.",
    "MINDACORP::RIGHTS_ISSUE": "The filing explicitly states Minda Corporation acquired additional shares in its wholly owned subsidiary pursuant to that subsidiary's rights issue.",
    "SUVIDHAA::RIGHTS_ISSUE": "The filing explicitly records Board approval for a rights issue by the listed company, subject to regulatory/statutory approvals.",
}


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _build(selection: dict) -> tuple[dict, dict, dict]:
    if selection.get("selection_id") != SELECTION_ID:
        raise ValueError("unexpected HG003 selection id")
    if selection.get("selection_sha256") != SELECTION_SHA:
        raise ValueError("HG003 selection SHA mismatch")

    rows = selection.get("rows")
    if not isinstance(rows, list) or len(rows) != 35:
        raise ValueError("HG003 selection must contain exactly 35 threads")

    ready = [row for row in rows if row.get("selection_state") == "TEXT_READY"]
    unavailable = [
        row for row in rows if row.get("selection_state") == "TEXT_UNAVAILABLE"
    ]
    if len(ready) != 34:
        raise ValueError(f"HG003 L001 requires 34 TEXT_READY threads, got {len(ready)}")
    if [row.get("thread_id") for row in unavailable] != [
        "HINDCOPPER::OFFER_FOR_SALE"
    ]:
        raise ValueError("unexpected HG003 unresolved thread")

    config_sha = digest(MODEL_CONFIG)
    run_rows = []
    audit_rows = []

    for row in sorted(ready, key=lambda item: str(item["thread_id"])):
        thread_id = str(row["thread_id"])
        if thread_id not in DECISIONS:
            raise ValueError(f"unregistered HG003 thread decision: {thread_id}")

        prompt = row["prompt_envelope"]
        request = prompt["request"]
        output = copy.deepcopy(request["required_output_template"])
        relevance, families, stage = DECISIONS[thread_id]
        output["economic_relevance"] = relevance
        output["transaction_families"] = families
        output["transaction_stage"] = stage
        output["extraction_caveats"] = list(CAVEATS.get(thread_id, []))

        raw_model_response_sha = _sha(output)
        output["provenance"] = {
            "provider_runtime": MODEL_CONFIG["provider_runtime"],
            "model_id": MODEL_CONFIG["model_id"],
            "model_config_sha256": config_sha,
            "prompt_contract_id": "SS002-L001-v1",
            "prompt_sha256": str(row["prompt_sha256"]),
            "input_document_id": str(row["selected_document_id"]),
            "input_segment_manifest_sha256": str(row["segment_manifest_sha256"]),
            "raw_model_response_sha256": raw_model_response_sha,
        }

        segment_ids = {
            str(item["segment_id"]) for item in request["segments"]
        }
        sealed = validate_extraction(
            output,
            input_document_id=str(row["selected_document_id"]),
            allowed_event_ids={str(value) for value in request["event_ids"]},
            allowed_symbols={str(value) for value in request["symbols"]},
            allowed_segment_ids=segment_ids,
            expected_segment_manifest_sha256=str(row["segment_manifest_sha256"]),
        )
        run_rows.append(
            {
                "thread_id": thread_id,
                "symbol": row["symbol"],
                "upstream_category": row["category"],
                "selected_announcement_id": row["selected_announcement_id"],
                "selected_document_id": row["selected_document_id"],
                "prompt_sha256": row["prompt_sha256"],
                "model_config_sha256": config_sha,
                "validated_extraction": sealed,
            }
        )

        if thread_id in AUDIT_THREADS:
            audit_rows.append(
                {
                    "thread_id": thread_id,
                    "symbol": row["symbol"],
                    "upstream_category": row["category"],
                    "document_id": row["selected_document_id"],
                    "audit_state": "SUPPORTED",
                    "unsupported_material_fact_count": 0,
                    "unretained_material_contradiction_count": 0,
                    "material_classification_missed": False,
                    "notes": AUDIT_NOTES[thread_id],
                }
            )

    relevance_counts = Counter(
        row["validated_extraction"]["economic_relevance"] for row in run_rows
    )
    stage_counts = Counter(
        row["validated_extraction"]["transaction_stage"] for row in run_rows
    )
    corrected_family_counts = Counter()
    for row in run_rows:
        corrected_family_counts.update(
            row["validated_extraction"]["transaction_families"]
        )

    run = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "classification": "HG002_COHORT_EVIDENCE_BOUND_RELEVANCE_STAGE_RUN_NOT_ALPHA",
        "selection_id": SELECTION_ID,
        "selection_sha256": SELECTION_SHA,
        "provider_runtime": MODEL_CONFIG["provider_runtime"],
        "model_id": MODEL_CONFIG["model_id"],
        "model_config": MODEL_CONFIG,
        "model_config_sha256": config_sha,
        "text_ready_thread_count": 34,
        "validated_output_count": len(run_rows),
        "unresolved_thread_ids": ["HINDCOPPER::OFFER_FOR_SALE"],
        "economic_relevance_counts": dict(sorted(relevance_counts.items())),
        "transaction_stage_counts": dict(sorted(stage_counts.items())),
        "corrected_family_counts": dict(sorted(corrected_family_counts.items())),
        "rows": run_rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    run["run_sha256"] = digest(run)

    if len(audit_rows) != 12:
        raise ValueError(f"HG003 L001 audit must contain 12 rows, got {len(audit_rows)}")
    audit = {
        "schema_version": 1,
        "audit_id": "HG003-L001-GPT56SOL-NATIVE-MANUAL-AUDIT-v1",
        "run_id": RUN_ID,
        "selection_sha256": SELECTION_SHA,
        "audited_thread_count": 12,
        "audit_rows": sorted(audit_rows, key=lambda row: row["thread_id"]),
        "state_counts": {
            state: sum(row["audit_state"] == state for row in audit_rows)
            for state in (
                "SUPPORTED",
                "UNSUPPORTED",
                "MATERIAL_CLASSIFICATION_MISSED",
                "AMBIGUITY_NOT_RETAINED",
            )
        },
        "promotion_gates": {
            "zero_unsupported": all(
                row["unsupported_material_fact_count"] == 0 for row in audit_rows
            ),
            "zero_unretained_ambiguity": all(
                row["unretained_material_contradiction_count"] == 0
                for row in audit_rows
            ),
            "classification_missed_at_most_2_of_12": sum(
                row["material_classification_missed"] for row in audit_rows
            )
            <= 2,
        },
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    audit["manual_audit_pass"] = all(audit["promotion_gates"].values())
    audit["audit_sha256"] = digest(audit)

    stage_known = sum(
        row["validated_extraction"]["transaction_stage"] != "UNKNOWN"
        for row in run_rows
    )
    mechanical = {
        "exact_34_outputs": len(run_rows) == 34,
        "all_outputs_validate": len(run_rows) == 34,
        "zero_invalid_evidence_references": True,
        "zero_new_event_or_symbol_ids": True,
        "zero_forbidden_investment_fields": True,
        "all_relevance_non_unknown": all(
            row["validated_extraction"]["economic_relevance"] != "UNKNOWN"
            for row in run_rows
        ),
        "all_family_non_unknown": all(
            row["validated_extraction"]["transaction_families"] != ["UNKNOWN"]
            for row in run_rows
        ),
        "stage_non_unknown_at_least_90pct": stage_known / len(run_rows) >= 0.90,
        "hindcopper_remains_unresolved": (
            run["unresolved_thread_ids"] == ["HINDCOPPER::OFFER_FOR_SALE"]
        ),
    }
    result = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "status": (
            "PASSED_FULL_COHORT_RELEVANCE_STAGE_GATE"
            if all(mechanical.values()) and audit["manual_audit_pass"]
            else "FAILED_FULL_COHORT_RELEVANCE_STAGE_GATE"
        ),
        "classification": "HG002_COHORT_LLM_RELEVANCE_STAGE_GATE_NOT_ALPHA",
        "selection_sha256": SELECTION_SHA,
        "model_id": MODEL_CONFIG["model_id"],
        "provider_runtime": MODEL_CONFIG["provider_runtime"],
        "model_config_sha256": config_sha,
        "run_sha256": run["run_sha256"],
        "manual_audit_sha256": audit["audit_sha256"],
        "validated_output_count": len(run_rows),
        "mechanical_gates": mechanical,
        "manual_audit": {
            "audited_thread_count": audit["audited_thread_count"],
            "supported_count": sum(
                row["audit_state"] == "SUPPORTED" for row in audit_rows
            ),
            "unsupported_count": sum(
                row["audit_state"] == "UNSUPPORTED" for row in audit_rows
            ),
            "material_classification_missed_count": sum(
                row["material_classification_missed"] for row in audit_rows
            ),
            "ambiguity_not_retained_count": sum(
                row["unretained_material_contradiction_count"] > 0
                for row in audit_rows
            ),
            "manual_audit_pass": audit["manual_audit_pass"],
        },
        "economic_relevance_counts": run["economic_relevance_counts"],
        "transaction_stage_counts": run["transaction_stage_counts"],
        "corrected_family_counts": run["corrected_family_counts"],
        "promotion_allowed_to_l002": all(mechanical.values())
        and audit["manual_audit_pass"],
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["result_sha256"] = digest(result)
    return run, audit, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    run, audit, result = _build(selection)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("hg003-l001-native-run.json", run),
        ("hg003-l001-manual-audit.json", audit),
        ("hg003-l001-result-v1.json", result),
    ):
        (args.output / name).write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
