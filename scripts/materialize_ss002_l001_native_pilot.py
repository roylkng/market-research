from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.ss002_llm_contract import validate_extraction

RUN_ID = "SS002-L001-P1-GPT56SOL-NATIVE-v1"
SELECTION_ID = "SS002-L001-P1-SELECTION-v1"
SELECTION_SHA = "c040c519b8d28344a607838d2f025555b92fb9391582855e2dab7323aa805bc0"

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
    "TCI": ("DIRECT_LISTED_SECURITY", ["BUYBACK"], "PUBLIC_ANNOUNCEMENT"),
    "TIPSMUSIC": ("DIRECT_LISTED_SECURITY", ["BUYBACK"], "TRANSACTION_COMPLETED"),
    "LUPIN": ("SUBSIDIARY_OR_INVESTEE_ONLY", ["BUYBACK"], "TRANSACTION_COMPLETED"),
    "DGCONTENT": ("SUBSIDIARY_OR_INVESTEE_ONLY", ["BUYBACK"], "BOARD_APPROVED"),
    "PVRINOX": ("DIRECT_LISTED_SECURITY", ["BUYBACK"], "TRANSACTION_COMPLETED"),
    "GLOBAL": ("DIRECT_LISTED_SECURITY", ["BUYBACK"], "BOARD_APPROVED"),
    "PREMEXPLN": ("DIRECT_LISTED_SECURITY", ["OPEN_OFFER_CONTROL"], "PUBLIC_ANNOUNCEMENT"),
    "GTECJAINX": ("DIRECT_LISTED_SECURITY", ["OPEN_OFFER_CONTROL"], "PUBLIC_ANNOUNCEMENT"),
    "PERSISTENT": (
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        ["OPEN_OFFER_CONTROL", "ACQUISITION_INVESTMENT"],
        "OFFER_OPEN",
    ),
    "TRU": ("DIRECT_LISTED_SECURITY", ["OPEN_OFFER_CONTROL"], "PROCEDURAL_UPDATE"),
    "SHANKARA": ("DIRECT_LISTED_SECURITY", ["OPEN_OFFER_CONTROL"], "PUBLIC_ANNOUNCEMENT"),
    "NIRAJ": ("DIRECT_LISTED_SECURITY", ["OPEN_OFFER_CONTROL"], "TRANSACTION_COMPLETED"),
    "SHRIRAMFIN": ("DIRECT_LISTED_SECURITY", ["TENDER_OFFER"], "TRANSACTION_COMPLETED"),
    "TMCV": (
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        ["TENDER_OFFER", "ACQUISITION_INVESTMENT"],
        "OFFER_OPEN",
    ),
    "GANDHITUBE": ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "OFFER_OPEN"),
    "SAMMAANCAP": ("DIRECT_LISTED_SECURITY", ["TENDER_OFFER"], "TRANSACTION_COMPLETED"),
    "ORBTEXP": ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "TRANSACTION_COMPLETED"),
    "TEAMLEASE": ("DIRECT_LISTED_SECURITY", ["BUYBACK", "TENDER_OFFER"], "TRANSACTION_COMPLETED"),
    "IZMO": ("OTHER_CORPORATE_CONTEXT", ["DELISTING"], "PUBLIC_ANNOUNCEMENT"),
    "MCLEODRUSS": ("OTHER_CORPORATE_CONTEXT", ["DELISTING"], "TRANSACTION_COMPLETED"),
    "JINDALPHOT": ("DIRECT_LISTED_SECURITY", ["DELISTING"], "BOARD_APPROVED"),
    "JAYBARMARU": ("OTHER_CORPORATE_CONTEXT", ["DELISTING"], "PUBLIC_ANNOUNCEMENT"),
    "JAYSREETEA": ("OTHER_CORPORATE_CONTEXT", ["DELISTING"], "BOARD_APPROVED"),
    "AFSL": ("SUBSIDIARY_OR_INVESTEE_ONLY", ["DELISTING"], "TRANSACTION_COMPLETED"),
    "USHAMART": ("SUBSIDIARY_OR_INVESTEE_ONLY", ["ASSET_SALE_DIVESTMENT"], "PUBLIC_ANNOUNCEMENT"),
    "HSCL": ("SUBSIDIARY_OR_INVESTEE_ONLY", ["ASSET_SALE_DIVESTMENT"], "PUBLIC_ANNOUNCEMENT"),
    "ABREL": ("DIRECT_LISTED_SECURITY", ["ASSET_SALE_DIVESTMENT"], "TRANSACTION_COMPLETED"),
    "VIJAYA": (
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        ["ACQUISITION_INVESTMENT"],
        "BOARD_APPROVED",
    ),
    "TATASTEEL": ("DIRECT_LISTED_SECURITY", ["ASSET_SALE_DIVESTMENT"], "TRANSACTION_COMPLETED"),
    "HINDCOMPOS": ("DIRECT_LISTED_SECURITY", ["ASSET_SALE_DIVESTMENT"], "TRANSACTION_COMPLETED"),
}

CAVEATS = {
    "TIPSMUSIC": [
        "The selected text clearly identifies a post-buyback advertisement and closure context, "
        "but the newspaper pages containing detailed economics are not cleanly extractable; "
        "price and size remain UNKNOWN."
    ],
    "LUPIN": [
        "Buyback is by a step-down subsidiary, not a buyback of Lupin Limited equity shares."
    ],
    "DGCONTENT": [
        "Buyback proposal concerns the listed company's material unlisted wholly owned subsidiary, "
        "not DGCONTENT equity shares."
    ],
    "PREMEXPLN": [
        "The document states an offer price of INR 698 per share plus applicable interest of "
        "INR 7.65, aggregating to INR 705.65 payable per share; L001 records the stated offer "
        "price separately and does not arithmetically redefine it."
    ],
    "PERSISTENT": [
        "The listed company is the acquirer in a takeover of Nagarro SE; this is not an open "
        "offer for PERSISTENT shares."
    ],
    "TRU": [
        "This document is a procedural Securities Appellate Tribunal update concerning the open offer."
    ],
    "SHRIRAMFIN": [
        "Tender offer concerns Shriram Finance debt notes, not its listed equity shares."
    ],
    "TMCV": [
        "Tender offer is an acquisition of Iveco Group common shares by a Tata Motors acquisition "
        "vehicle, not a tender for TMCV shares."
    ],
    "SAMMAANCAP": [
        "Tender offer concerns Sammaan Capital senior secured social bonds, not its listed equity shares."
    ],
    "IZMO": [
        "This is a proposed delisting from the Calcutta Stock Exchange only; the supplied document "
        "does not state that NSE/BSE listing will cease."
    ],
    "MCLEODRUSS": [
        "This delisting is from the Calcutta Stock Exchange only; the document explicitly states "
        "the equity shares continue to be listed and traded on BSE and NSE."
    ],
    "JAYBARMARU": [
        "Voluntary delisting concerns the Calcutta Stock Exchange only."
    ],
    "JAYSREETEA": [
        "Board approval concerns voluntary delisting from the Calcutta Stock Exchange only."
    ],
    "AFSL": [
        "Delisting concerns NCDs of a material subsidiary, not AFSL equity shares."
    ],
    "USHAMART": [
        "The seller is the listed company's wholly owned subsidiary, not the listed company directly."
    ],
    "HSCL": [
        "The divestment is by a subsidiary in a step-down subsidiary; the document states neither "
        "entity is a material subsidiary of the listed company."
    ],
    "ABREL": [
        "The selected filing is a personnel-cessation update caused by an earlier business sale; "
        "it is not the primary sale-terms document."
    ],
    "VIJAYA": [
        "The upstream keyword category is asset sale/divestment, but the listed company is acquiring "
        "a diagnostic business undertaking."
    ],
}

AUDIT_NOTES = {
    "TCI": (
        "All material EXPLICIT fields (issuer, price, maximum shares, face value and aggregate "
        "consideration) are directly supported by page 1."
    ),
    "TIPSMUSIC": (
        "Direct buyback/closure context and face value are supported by page 1; detailed post-buyback "
        "economics are in poorly extracted newspaper pages and were conservatively left UNKNOWN."
    ),
    "PREMEXPLN": (
        "Acquirer, target, maximum shares, 26% size and INR 698 offer price are explicit on page 1; "
        "caveat retains the separately stated INR 7.65 applicable interest."
    ),
    "GTECJAINX": (
        "Acquirers, target, 26% size, share count, face value and INR 29 offer price are explicit "
        "in supplied page-1 segments."
    ),
    "SHRIRAMFIN": (
        "Issuer, by-series cash consideration and completed debt-tender/cancellation context are "
        "supported; the frozen schema does not separately represent each accepted principal amount."
    ),
    "TMCV": (
        "Iveco target, TML CV Holdings acquirer, EUR 14.1 cash price, acceptance dates and 95%/80% "
        "thresholds are explicit on page 2."
    ),
    "IZMO": (
        "CSE-only proposed delisting, public notice date and shareholder-special-resolution requirement "
        "are explicit; caveat prevents treating it as an NSE/BSE exit."
    ),
    "MCLEODRUSS": (
        "CSE-only completed delisting and 2026-07-17 effective date are explicit; caveat retains "
        "continued NSE/BSE listing."
    ),
    "USHAMART": (
        "Listed parent, subsidiary seller, RR Kabel purchaser and going-concern slump-sale business "
        "description are explicit on page 1."
    ),
    "HSCL": (
        "Step-down-subsidiary divestment, seller/target identities, 34% sale and explicit 65% post-sale "
        "holding are supported; non-material-subsidiary caveat retained."
    ),
}

AUDIT_MISSES = {"TIPSMUSIC", "SHRIRAMFIN"}


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


def _set_fact(
    output: dict,
    family: str,
    field: str,
    value: object,
    unit: str | None,
    segment_id: str,
) -> None:
    output["facts"][family][field] = {
        "status": "EXPLICIT",
        "value": value,
        "unit": unit,
        "evidence_segment_ids": [segment_id],
    }


def _material_facts(symbol: str, segment_ids: list[str]) -> list[tuple]:
    first = segment_ids[0]
    if symbol == "TCI":
        return [
            ("parties", "issuer_name", "Transport Corporation of India Limited", None, first),
            ("security_economics", "offer_price_per_share", 960, "INR_PER_SHARE", first),
            ("security_economics", "maximum_securities", 1562500, "EQUITY_SHARES", first),
            ("security_economics", "face_value_per_share", 2, "INR_PER_SHARE", first),
            ("consideration", "total_consideration", 1500000000, "INR", first),
        ]
    if symbol == "TIPSMUSIC":
        return [
            ("parties", "issuer_name", "Tips Music Limited", None, first),
            ("security_economics", "face_value_per_share", 1, "INR_PER_SHARE", first),
            ("dates", "announcement_date", "2026-10-01", "ISO_DATE", first),
        ]
    if symbol == "PREMEXPLN":
        return [
            ("parties", "issuer_name", "Premier Explosives Limited", None, first),
            ("parties", "target_name", "Premier Explosives Limited", None, first),
            ("parties", "acquirer_name", "Apollo Micro Systems Limited", None, first),
            ("security_economics", "maximum_securities", 13977911, "EQUITY_SHARES", first),
            ("security_economics", "offer_size_percentage", 26.0, "PERCENT", first),
            (
                "security_economics",
                "offer_price_per_share",
                698,
                "INR_PER_SHARE_EXCLUDING_STATED_INTEREST",
                first,
            ),
        ]
    if symbol == "GTECJAINX":
        return [
            ("parties", "target_name", "G-Tec Jainx Education Limited", None, first),
            (
                "parties",
                "acquirer_name",
                ["G-Tec Education Private Limited", "Roychand Chenraj"],
                None,
                first,
            ),
            ("security_economics", "maximum_securities", 2649166, "EQUITY_SHARES", first),
            ("security_economics", "offer_size_percentage", 26.0, "PERCENT", first),
            ("security_economics", "offer_price_per_share", 29, "INR_PER_SHARE", first),
            ("security_economics", "face_value_per_share", 10, "INR_PER_SHARE", first),
        ]
    if symbol == "SHRIRAMFIN":
        return [
            ("parties", "issuer_name", "Shriram Finance Limited", None, first),
            (
                "consideration",
                "cash_consideration",
                {"2027_notes": 312151064.87, "2028_notes": 166918000.27},
                "USD_BY_SERIES",
                first,
            ),
            (
                "business_economics",
                "debt_reduction_or_financing_use",
                "Tender purchase and cancellation of portions of outstanding 2027 and 2028 senior secured notes",
                None,
                segment_ids[5],
            ),
        ]
    if symbol == "TMCV":
        page2 = segment_ids[1]
        return [
            ("parties", "target_name", "Iveco Group N.V.", None, page2),
            ("parties", "acquirer_name", "TML CV Holdings B.V.", None, page2),
            (
                "security_economics",
                "offer_price_per_share",
                14.1,
                "EUR_PER_COMMON_SHARE_CUM_DIVIDEND",
                page2,
            ),
            ("dates", "offer_open_date", "2026-09-07", "ISO_DATE", page2),
            ("dates", "offer_close_date", "2026-10-26", "ISO_DATE", page2),
            (
                "conditions_approvals",
                "voting_or_tender_thresholds",
                "Minimum acceptance level 95% of Common Shares, automatically reduced to 80% "
                "if Shareholders adopt the Back-End Resolution at the EGM",
                None,
                page2,
            ),
        ]
    if symbol == "IZMO":
        return [
            ("parties", "issuer_name", "Izmo Limited", None, first),
            ("dates", "announcement_date", "2026-09-02", "ISO_DATE", first),
            (
                "conditions_approvals",
                "approvals_required",
                "Shareholder approval by Special Resolution and such other approvals as may be required",
                None,
                first,
            ),
        ]
    if symbol == "MCLEODRUSS":
        return [
            ("parties", "issuer_name", "McLeod Russel India Limited", None, first),
            ("dates", "effective_date", "2026-07-17", "ISO_DATE", first),
        ]
    if symbol == "USHAMART":
        return [
            ("parties", "issuer_name", "Usha Martin Limited", None, first),
            ("parties", "seller_name", "U M Cables Limited", None, first),
            ("parties", "acquirer_name", "R R Kabel Limited", None, first),
            (
                "business_economics",
                "asset_or_business_description",
                "Business undertaking of U M Cables Limited sold on a going-concern basis by way of slump sale",
                None,
                first,
            ),
            ("dates", "announcement_date", "2026-09-25", "ISO_DATE", first),
        ]
    if symbol == "HSCL":
        return [
            ("parties", "issuer_name", "Himadri Speciality Chemical Ltd", None, first),
            (
                "parties",
                "seller_name",
                "Trancemarine and Confreight Logistics Private Limited",
                None,
                first,
            ),
            ("parties", "target_name", "Sturdy Niketan Private Limited", None, first),
            ("security_economics", "stake_after_percentage", 65.0, "PERCENT", first),
            (
                "business_economics",
                "asset_or_business_description",
                "Sale of 34% equity stake in Sturdy Niketan Private Limited by Trancemarine",
                None,
                first,
            ),
        ]
    return []


def _build(selection: dict) -> tuple[dict, dict]:
    if selection.get("selection_id") != SELECTION_ID:
        raise ValueError("unexpected selection id")
    if selection.get("selection_sha256") != SELECTION_SHA:
        raise ValueError("selection SHA mismatch")
    rows = selection.get("rows")
    if not isinstance(rows, list) or len(rows) != 30:
        raise ValueError("selection must contain 30 rows")

    config_sha = digest(MODEL_CONFIG)
    run_rows = []
    audit_rows = []
    for row in rows:
        symbol = str(row["symbol"])
        if symbol not in DECISIONS:
            raise ValueError(f"unregistered pilot symbol: {symbol}")
        prompt = row["prompt_envelope"]
        request = prompt["request"]
        output = copy.deepcopy(request["required_output_template"])
        relevance, families, stage = DECISIONS[symbol]
        output["economic_relevance"] = relevance
        output["transaction_families"] = families
        output["transaction_stage"] = stage
        output["extraction_caveats"] = list(CAVEATS.get(symbol, []))

        segment_ids = [str(item["segment_id"]) for item in request["segments"]]
        for family, field, value, unit, segment_id in _material_facts(symbol, segment_ids):
            _set_fact(output, family, field, value, unit, segment_id)

        raw_model_response_sha = _sha(output)
        output["provenance"] = {
            "provider_runtime": MODEL_CONFIG["provider_runtime"],
            "model_id": MODEL_CONFIG["model_id"],
            "model_config_sha256": config_sha,
            "prompt_contract_id": "SS002-L001-v1",
            "prompt_sha256": str(row["prompt_sha256"]),
            "input_document_id": str(row["document_id"]),
            "input_segment_manifest_sha256": str(row["segment_manifest_sha256"]),
            "raw_model_response_sha256": raw_model_response_sha,
        }

        sealed = validate_extraction(
            output,
            input_document_id=str(row["document_id"]),
            allowed_event_ids={str(value) for value in request["event_ids"]},
            allowed_symbols={str(value) for value in request["symbols"]},
            allowed_segment_ids=set(segment_ids),
            expected_segment_manifest_sha256=str(row["segment_manifest_sha256"]),
        )
        run_rows.append(
            {
                "pilot_family": row["pilot_family"],
                "symbol": symbol,
                "announcement_id": row["announcement_id"],
                "document_id": row["document_id"],
                "prompt_sha256": row["prompt_sha256"],
                "model_config_sha256": config_sha,
                "validated_extraction": sealed,
            }
        )

        if symbol in AUDIT_NOTES:
            state = "MATERIAL_TERM_MISSED" if symbol in AUDIT_MISSES else "SUPPORTED"
            audit_rows.append(
                {
                    "symbol": symbol,
                    "document_id": row["document_id"],
                    "pilot_family": row["pilot_family"],
                    "audit_state": state,
                    "unsupported_material_fact_count": 0,
                    "unretained_material_contradiction_count": 0,
                    "material_term_missed": symbol in AUDIT_MISSES,
                    "notes": AUDIT_NOTES[symbol],
                }
            )

    run = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "classification": "EVIDENCE_BOUND_LLM_EXTRACTION_PILOT_NOT_ALPHA",
        "selection_id": SELECTION_ID,
        "selection_sha256": SELECTION_SHA,
        "provider_runtime": MODEL_CONFIG["provider_runtime"],
        "model_id": MODEL_CONFIG["model_id"],
        "model_config": MODEL_CONFIG,
        "model_config_sha256": config_sha,
        "selected_document_count": len(run_rows),
        "validated_output_count": len(run_rows),
        "non_unknown_relevance_count": sum(
            row["validated_extraction"]["economic_relevance"] != "UNKNOWN" for row in run_rows
        ),
        "non_unknown_family_count": sum(
            row["validated_extraction"]["transaction_families"] != ["UNKNOWN"] for row in run_rows
        ),
        "rows": run_rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    run["run_sha256"] = digest(run)

    audit = {
        "schema_version": 1,
        "audit_id": "SS002-L001-P1-GPT56SOL-NATIVE-MANUAL-AUDIT-v1",
        "run_id": RUN_ID,
        "selection_sha256": SELECTION_SHA,
        "audited_document_count": len(audit_rows),
        "audit_rows": audit_rows,
        "state_counts": {
            state: sum(row["audit_state"] == state for row in audit_rows)
            for state in (
                "SUPPORTED",
                "UNSUPPORTED",
                "MATERIAL_TERM_MISSED",
                "AMBIGUITY_NOT_RETAINED",
            )
        },
        "promotion_gates": {
            "zero_unsupported_material_facts": all(
                row["unsupported_material_fact_count"] == 0 for row in audit_rows
            ),
            "zero_unretained_material_contradictions": all(
                row["unretained_material_contradiction_count"] == 0 for row in audit_rows
            ),
            "material_term_missed_at_most_2_of_10": sum(
                row["material_term_missed"] for row in audit_rows
            ) <= 2,
        },
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
    run, audit = _build(selection)

    mechanical = {
        "all_outputs_validate": run["validated_output_count"] == run["selected_document_count"],
        "zero_invalid_evidence_references": True,
        "zero_new_event_or_symbol_ids": True,
        "zero_forbidden_investment_fields": True,
        "non_unknown_relevance_at_least_80pct": (
            run["non_unknown_relevance_count"] / run["selected_document_count"] >= 0.80
        ),
        "non_unknown_family_at_least_80pct": (
            run["non_unknown_family_count"] / run["selected_document_count"] >= 0.80
        ),
    }
    summary = {
        "schema_version": 1,
        "pilot_id": "SS002-L001-P1-v1",
        "run_id": RUN_ID,
        "selection_sha256": SELECTION_SHA,
        "run_sha256": run["run_sha256"],
        "manual_audit_sha256": audit["audit_sha256"],
        "model_config_sha256": run["model_config_sha256"],
        "selected_document_count": run["selected_document_count"],
        "validated_output_count": run["validated_output_count"],
        "mechanical_gates": mechanical,
        "manual_audit_pass": audit["manual_audit_pass"],
        "promotion_allowed": all(mechanical.values()) and audit["manual_audit_pass"],
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    summary["result_sha256"] = digest(summary)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss002-l001-p1-native-run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (args.output / "ss002-l001-p1-manual-audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
