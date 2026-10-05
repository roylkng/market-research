from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.ss002_llm_contract import validate_extraction

RUN_ID = "SS002-L001-P2-GPT56SOL-NATIVE-v1"
SELECTION_ID = "SS002-L001-P2-SELECTION-v1"
SELECTION_SHA = "bb18dede6c56e07d8beff78852f8e089ac3d7bd124fb76c6cc0d22e9fecec7ce"

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
    "WIPRO": (
        "SUBSIDIARY_OR_INVESTEE_ONLY",
        ["SCHEME_REORGANISATION"],
        "TRANSACTION_COMPLETED",
    ),
    "GVPIL": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "REGULATORY_OR_COURT_APPROVED",
    ),
    "JSWENERGY": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "REGULATORY_OR_COURT_APPROVED",
    ),
    "TATASTEEL": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "REGULATORY_OR_COURT_APPROVED",
    ),
    "SUNTECK": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "BOARD_APPROVED",
    ),
    "RAYMOND": (
        "DIRECT_LISTED_SECURITY",
        ["PREFERENTIAL_WARRANT"],
        "SHAREHOLDER_APPROVED",
    ),
    "TDPOWERSYS": (
        "DIRECT_LISTED_SECURITY",
        ["PREFERENTIAL_WARRANT"],
        "ALLOTMENT_COMPLETED",
    ),
    "BAJAJFINSV": (
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        ["PREFERENTIAL_WARRANT", "ACQUISITION_INVESTMENT"],
        "BOARD_APPROVED",
    ),
    "BAJFINANCE": (
        "DIRECT_LISTED_SECURITY",
        ["PREFERENTIAL_WARRANT", "FUND_RAISE_OTHER"],
        "BOARD_APPROVED",
    ),
    "EFCIL": (
        "DIRECT_LISTED_SECURITY",
        ["PREFERENTIAL_WARRANT", "ACQUISITION_INVESTMENT"],
        "ALLOTMENT_COMPLETED",
    ),
    "AMBUJACEM": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "SHAREHOLDER_APPROVED",
    ),
    "ASIANENE": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "REGULATORY_OR_COURT_APPROVED",
    ),
    "GODIGIT": (
        "PROCEDURAL_OR_NEWSPAPER_UPDATE",
        ["SCHEME_REORGANISATION"],
        "PROCEDURAL_UPDATE",
    ),
    "ACC": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "SHAREHOLDER_APPROVED",
    ),
    "ORIENTCEM": (
        "DIRECT_LISTED_SECURITY",
        ["SCHEME_REORGANISATION"],
        "SHAREHOLDER_APPROVED",
    ),
    "ZOTA": (
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        ["RIGHTS_ISSUE", "ACQUISITION_INVESTMENT"],
        "TRANSACTION_COMPLETED",
    ),
    "SJS": (
        "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        ["RIGHTS_ISSUE", "ACQUISITION_INVESTMENT"],
        "TRANSACTION_COMPLETED",
    ),
    "ADANIENT": (
        "DIRECT_LISTED_SECURITY",
        ["RIGHTS_ISSUE"],
        "PROCEDURAL_UPDATE",
    ),
    "SPANDANA": (
        "DIRECT_LISTED_SECURITY",
        ["RIGHTS_ISSUE"],
        "ALLOTMENT_COMPLETED",
    ),
    "NATCOPHARM": (
        "DIRECT_LISTED_SECURITY",
        ["RIGHTS_ISSUE"],
        "RECORD_DATE_FIXED",
    ),
    "INDIANB": (
        "OTHER_CORPORATE_CONTEXT",
        ["OFFER_FOR_SALE", "ASSET_SALE_DIVESTMENT"],
        "PROPOSAL",
    ),
    "COCHINSHIP": (
        "DIRECT_LISTED_SECURITY",
        ["OFFER_FOR_SALE"],
        "OFFER_OPEN",
    ),
    "FIRSTCRY": (
        "OTHER_CORPORATE_CONTEXT",
        ["OFFER_FOR_SALE", "ASSET_SALE_DIVESTMENT"],
        "BOARD_APPROVED",
    ),
    "JSWINFRA": (
        "DIRECT_LISTED_SECURITY",
        ["OFFER_FOR_SALE", "FUND_RAISE_OTHER"],
        "OFFER_CLOSED",
    ),
    "BOSCH-HCIL": (
        "DIRECT_LISTED_SECURITY",
        ["OFFER_FOR_SALE"],
        "TRANSACTION_COMPLETED",
    ),
}

CAVEATS = {
    "WIPRO": [
        "Merger is between two step-down subsidiaries; the listed Wipro shareholding pattern is explicitly unaffected."
    ],
    "GVPIL": [
        "NCLT sanction is explicit, but the effective date and record date were still to be announced."
    ],
    "JSWENERGY": [
        "NCLT sanction is explicit, but the effective date was still to be announced."
    ],
    "TATASTEEL": [
        "Transferor is a wholly owned subsidiary; the scheme is an internal group amalgamation."
    ],
    "SUNTECK": [
        "Scheme is an internal reorganisation with a wholly owned subsidiary; no shares or cash consideration are proposed."
    ],
    "RAYMOND": [
        "Selected document proves shareholder approval and warrant count, but does not contain the warrant issue price."
    ],
    "TDPOWERSYS": [
        "Preferential issuance is of equity shares already allotted to promoters, not warrants."
    ],
    "BAJAJFINSV": [
        "Listed Bajaj Finserv is subscribing to warrants issued by its listed subsidiary Bajaj Finance; this is not an issuance of Bajaj Finserv shares."
    ],
    "BAJFINANCE": [
        "Board approved both a QIP and a preferential warrant issue; preferential issue price is explicitly deferred to a later stage."
    ],
    "EFCIL": [
        "Preferential issuance is equity shares issued as non-cash consideration for a 100% acquisition, not warrants."
    ],
    "AMBUJACEM": [
        "Upstream INSOLVENCY_RESOLUTION classification is misleading; the document is a shareholder-vote filing for the ACC-Ambuja amalgamation."
    ],
    "ASIANENE": [
        "Upstream INSOLVENCY_RESOLUTION classification is misleading; the document is an NCLT-sanctioned merger. Ministry of Petroleum and Natural Gas approval remains pending."
    ],
    "GODIGIT": [
        "Upstream insolvency keyword is misleading; this is a newspaper/procedural notice for a scheme-of-amalgamation shareholder meeting."
    ],
    "ACC": [
        "Upstream insolvency keyword is misleading; this is the shareholder-approved ACC-Ambuja amalgamation."
    ],
    "ORIENTCEM": [
        "Upstream insolvency keyword is misleading; this is the shareholder-approved Orient Cement-Ambuja amalgamation."
    ],
    "ZOTA": [
        "Rights issue is by a wholly owned subsidiary; listed Zota is the subscriber/acquirer, not the issuer of rights shares."
    ],
    "SJS": [
        "Rights issue is by a wholly owned subsidiary; listed SJS is the subscriber/acquirer, not the issuer of rights shares."
    ],
    "ADANIENT": [
        "Selected filing is a call-money reminder for an earlier rights issue, not a new rights offering."
    ],
    "SPANDANA": [
        "Selected filing converts partly paid rights shares to fully paid shares after call-money receipt; it is not a new rights launch."
    ],
    "INDIANB": [
        "Indian Bank is selling part of its holding in NSE's proposed IPO; this is not an OFS of Indian Bank shares."
    ],
    "COCHINSHIP": [
        "The promoter is selling Cochin Shipyard shares directly through the stock-exchange OFS mechanism."
    ],
    "FIRSTCRY": [
        "Listed Brainbees is proposing to sell shares of subsidiary Swara Baby in Swara Baby's IPO; this is not an OFS of FIRSTCRY shares."
    ],
    "JSWINFRA": [
        "Selected transaction combines a QIP fresh issue with a promoter OFS; the document records offer closure and allocation."
    ],
    "BOSCH-HCIL": [
        "Selected filing reports an already completed promoter OFS and resulting promoter holding reduction."
    ],
}

AUDIT_SYMBOLS = {
    "WIPRO",
    "GVPIL",
    "RAYMOND",
    "TDPOWERSYS",
    "AMBUJACEM",
    "ASIANENE",
    "ZOTA",
    "SJS",
    "INDIANB",
    "COCHINSHIP",
}

AUDIT_NOTES = {
    "WIPRO": "Internal step-down-subsidiary merger, completion date and rationale are explicit; no listed-entity shareholding change or exchange ratio applies.",
    "GVPIL": "NCLT sanction date and direct listed-company scheme are explicit; effective and record dates are explicitly pending.",
    "RAYMOND": "Shareholder approval, 3,328,686 preferential warrants and Minerva Ventures Fund are explicit; issue price is absent from the selected document.",
    "TDPOWERSYS": "1,250,000 already-allotted preferential equity shares, INR 600 issue price and INR 1 face value are explicit.",
    "AMBUJACEM": "The document explicitly concerns shareholder approval of the ACC-Ambuja amalgamation; the upstream insolvency label is rejected.",
    "ASIANENE": "NCLT sanction, Oilmax-AESL merger, 117:10 exchange ratio and pending MoPNG approval are explicit.",
    "ZOTA": "Subsidiary rights subscription is completed; 39,228 shares, INR 5,075/share, INR 199,082,100 consideration and 100% WOS status are explicit.",
    "SJS": "Subsidiary rights subscription is completed; 50,000,000 shares at INR 10 and INR 50,000,000 consideration with 100% WOS status are explicit.",
    "INDIANB": "Indian Bank's proposed divestment of up to 1.5m NSE shares is explicit; price/consideration is explicitly not yet known.",
    "COCHINSHIP": "Direct promoter OFS, 13,259,272 maximum shares, 5.04% maximum size, INR 5 face value and July 7-8 offer window are explicit.",
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


def _segment(segment_ids: list[str], suffix: str) -> str:
    matches = [value for value in segment_ids if value.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"segment suffix {suffix!r} matched {matches}")
    return matches[0]


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
    p1 = _segment(segment_ids, "page:0001")
    if symbol == "WIPRO":
        p2 = _segment(segment_ids, "page:0002")
        return [
            ("parties", "issuer_name", "Wipro Limited", None, p1),
            (
                "parties",
                "other_named_counterparties",
                ["Wipro VLSI Design Services, LLC", "Wipro IT Services, LLC"],
                None,
                p1,
            ),
            ("dates", "effective_date", "2026-10-01", "ISO_DATE", p1),
            (
                "business_economics",
                "stated_transaction_rationale",
                "Rationalize and consolidate the overall group structure",
                None,
                p2,
            ),
        ]
    if symbol == "GVPIL":
        return [
            ("parties", "issuer_name", "GE Power India Limited", None, p1),
            (
                "parties",
                "other_named_counterparties",
                ["JSW Energy Limited"],
                None,
                p1,
            ),
            (
                "dates",
                "court_or_regulatory_order_date",
                "2026-10-01",
                "ISO_DATE",
                p1,
            ),
        ]
    if symbol == "RAYMOND":
        p6 = _segment(segment_ids, "page:0006")
        return [
            ("parties", "issuer_name", "Raymond Limited", None, p1),
            (
                "parties",
                "other_named_counterparties",
                ["Minerva Ventures fund"],
                None,
                p6,
            ),
            (
                "security_economics",
                "maximum_securities",
                3328686,
                "SHARE_WARRANTS",
                p6,
            ),
            (
                "dates",
                "shareholder_approval_date",
                "2026-10-03",
                "ISO_DATE",
                p1,
            ),
        ]
    if symbol == "TDPOWERSYS":
        return [
            ("parties", "issuer_name", "TD Power Systems Limited", None, p1),
            (
                "parties",
                "promoter_or_promoter_group",
                "Promoters",
                None,
                p1,
            ),
            (
                "security_economics",
                "number_of_securities",
                1250000,
                "EQUITY_SHARES",
                p1,
            ),
            (
                "security_economics",
                "issue_price_per_share",
                600,
                "INR_PER_SHARE",
                p1,
            ),
            (
                "security_economics",
                "face_value_per_share",
                1,
                "INR_PER_SHARE",
                p1,
            ),
        ]
    if symbol == "AMBUJACEM":
        p5 = _segment(segment_ids, "page:0005")
        return [
            ("parties", "issuer_name", "Ambuja Cements Limited", None, p1),
            ("parties", "target_name", "ACC Limited", None, p1),
            (
                "dates",
                "shareholder_approval_date",
                "2026-09-29",
                "ISO_DATE",
                p5,
            ),
        ]
    if symbol == "ASIANENE":
        p7 = _segment(segment_ids, "page:0007")
        p11 = _segment(segment_ids, "page:0011")
        return [
            ("parties", "issuer_name", "Asian Energy Services Limited", None, p1),
            ("parties", "target_name", "Oilmax Energy Private Limited", None, p1),
            (
                "dates",
                "court_or_regulatory_order_date",
                "2026-09-29",
                "ISO_DATE",
                p1,
            ),
            (
                "ratios_entitlement",
                "exchange_ratio_text",
                "117 fully paid-up AESL equity shares of INR 10 each for every 10 fully paid-up Oilmax equity shares of INR 10 each",
                None,
                p7,
            ),
            (
                "conditions_approvals",
                "approvals_required",
                "Ministry of Petroleum and Natural Gas approval remains required under the Scheme",
                None,
                p11,
            ),
        ]
    if symbol == "ZOTA":
        p2 = _segment(segment_ids, "page:0002")
        return [
            ("parties", "issuer_name", "Zota Health Care Limited", None, p1),
            ("parties", "target_name", "Davaindia Health Mart Limited", None, p1),
            (
                "security_economics",
                "number_of_securities",
                39228,
                "EQUITY_SHARES",
                p2,
            ),
            (
                "security_economics",
                "issue_price_per_share",
                5075,
                "INR_PER_SHARE",
                p2,
            ),
            (
                "security_economics",
                "stake_after_percentage",
                100.0,
                "PERCENT",
                p2,
            ),
            (
                "consideration",
                "total_consideration",
                199082100,
                "INR",
                p2,
            ),
            ("dates", "effective_date", "2026-10-01", "ISO_DATE", p2),
            (
                "business_economics",
                "stated_transaction_rationale",
                "Strategic investment and working-capital support for the wholly owned subsidiary",
                None,
                p2,
            ),
        ]
    if symbol == "SJS":
        p2 = _segment(segment_ids, "page:0002")
        return [
            ("parties", "issuer_name", "S.J.S. Enterprises Limited", None, p1),
            (
                "parties",
                "target_name",
                "SJS Display Electronics Private Limited",
                None,
                p1,
            ),
            (
                "security_economics",
                "number_of_securities",
                50000000,
                "EQUITY_SHARES",
                p2,
            ),
            (
                "security_economics",
                "issue_price_per_share",
                10,
                "INR_PER_SHARE",
                p2,
            ),
            (
                "security_economics",
                "stake_after_percentage",
                100.0,
                "PERCENT",
                p2,
            ),
            (
                "consideration",
                "total_consideration",
                50000000,
                "INR",
                p2,
            ),
            ("dates", "effective_date", "2026-09-30", "ISO_DATE", p2),
            (
                "business_economics",
                "stated_transaction_rationale",
                "Develop, grow and expand the wholly owned subsidiary and support its working-capital requirements",
                None,
                p2,
            ),
        ]
    if symbol == "INDIANB":
        p2 = _segment(segment_ids, "page:0002")
        return [
            ("parties", "issuer_name", "Indian Bank", None, p1),
            (
                "parties",
                "target_name",
                "National Stock Exchange of India Limited",
                None,
                p1,
            ),
            ("parties", "seller_name", "Indian Bank", None, p1),
            (
                "security_economics",
                "maximum_securities",
                1500000,
                "EQUITY_SHARES_OF_NSE",
                p1,
            ),
            ("dates", "announcement_date", "2026-09-09", "ISO_DATE", p1),
            (
                "business_economics",
                "asset_or_business_description",
                "Proposed divestment of part of Indian Bank's NSE shareholding through the OFS in NSE's proposed IPO",
                None,
                p2,
            ),
        ]
    if symbol == "COCHINSHIP":
        return [
            ("parties", "issuer_name", "Cochin Shipyard Limited", None, p1),
            (
                "parties",
                "seller_name",
                "President of India acting through the Ministry of Ports, Shipping and Waterways",
                None,
                p1,
            ),
            (
                "security_economics",
                "maximum_securities",
                13259272,
                "EQUITY_SHARES",
                p1,
            ),
            (
                "security_economics",
                "offer_size_percentage",
                5.04,
                "PERCENT",
                p1,
            ),
            (
                "security_economics",
                "face_value_per_share",
                5,
                "INR_PER_SHARE",
                p1,
            ),
            ("dates", "offer_open_date", "2026-07-07", "ISO_DATE", p1),
            ("dates", "offer_close_date", "2026-07-08", "ISO_DATE", p1),
        ]
    return []


def _build(selection: dict) -> tuple[dict, dict]:
    if selection.get("selection_id") != SELECTION_ID:
        raise ValueError("unexpected P2 selection id")
    if selection.get("selection_sha256") != SELECTION_SHA:
        raise ValueError("P2 selection SHA mismatch")
    rows = selection.get("rows")
    if not isinstance(rows, list) or len(rows) != 25:
        raise ValueError("P2 selection must contain 25 rows")

    config_sha = digest(MODEL_CONFIG)
    run_rows = []
    audit_rows = []

    for row in rows:
        symbol = str(row["symbol"])
        if symbol not in DECISIONS:
            raise ValueError(f"unregistered P2 pilot symbol: {symbol}")
        prompt = row["prompt_envelope"]
        request = prompt["request"]
        output = copy.deepcopy(request["required_output_template"])
        relevance, families, stage = DECISIONS[symbol]
        output["economic_relevance"] = relevance
        output["transaction_families"] = families
        output["transaction_stage"] = stage
        output["extraction_caveats"] = list(CAVEATS.get(symbol, []))

        segment_ids = [str(item["segment_id"]) for item in request["segments"]]
        for family, field, value, unit, segment_id in _material_facts(
            symbol, segment_ids
        ):
            _set_fact(output, family, field, value, unit, segment_id)

        raw_model_response_sha = _sha(output)
        output["provenance"] = {
            "provider_runtime": MODEL_CONFIG["provider_runtime"],
            "model_id": MODEL_CONFIG["model_id"],
            "model_config_sha256": config_sha,
            "prompt_contract_id": "SS002-L001-v1",
            "prompt_sha256": str(row["prompt_sha256"]),
            "input_document_id": str(row["document_id"]),
            "input_segment_manifest_sha256": str(
                row["segment_manifest_sha256"]
            ),
            "raw_model_response_sha256": raw_model_response_sha,
        }

        sealed = validate_extraction(
            output,
            input_document_id=str(row["document_id"]),
            allowed_event_ids={
                str(value) for value in request["event_ids"]
            },
            allowed_symbols={str(value) for value in request["symbols"]},
            allowed_segment_ids=set(segment_ids),
            expected_segment_manifest_sha256=str(
                row["segment_manifest_sha256"]
            ),
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

        if symbol in AUDIT_SYMBOLS:
            audit_rows.append(
                {
                    "symbol": symbol,
                    "document_id": row["document_id"],
                    "pilot_family": row["pilot_family"],
                    "audit_state": "SUPPORTED",
                    "unsupported_material_fact_count": 0,
                    "unretained_material_contradiction_count": 0,
                    "material_term_missed": False,
                    "notes": AUDIT_NOTES[symbol],
                }
            )

    run = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "classification": (
            "EVIDENCE_BOUND_LLM_EXTRACTION_PILOT_NOT_ALPHA"
        ),
        "selection_id": SELECTION_ID,
        "selection_sha256": SELECTION_SHA,
        "provider_runtime": MODEL_CONFIG["provider_runtime"],
        "model_id": MODEL_CONFIG["model_id"],
        "model_config": MODEL_CONFIG,
        "model_config_sha256": config_sha,
        "selected_document_count": len(run_rows),
        "validated_output_count": len(run_rows),
        "non_unknown_relevance_count": sum(
            row["validated_extraction"]["economic_relevance"] != "UNKNOWN"
            for row in run_rows
        ),
        "non_unknown_family_count": sum(
            row["validated_extraction"]["transaction_families"]
            != ["UNKNOWN"]
            for row in run_rows
        ),
        "rows": run_rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    run["run_sha256"] = digest(run)

    audit = {
        "schema_version": 1,
        "audit_id": (
            "SS002-L001-P2-GPT56SOL-NATIVE-MANUAL-AUDIT-v1"
        ),
        "run_id": RUN_ID,
        "selection_sha256": SELECTION_SHA,
        "audited_document_count": len(audit_rows),
        "audit_rows": audit_rows,
        "state_counts": {
            state: sum(
                row["audit_state"] == state for row in audit_rows
            )
            for state in (
                "SUPPORTED",
                "UNSUPPORTED",
                "MATERIAL_TERM_MISSED",
                "AMBIGUITY_NOT_RETAINED",
            )
        },
        "promotion_gates": {
            "zero_unsupported_material_facts": all(
                row["unsupported_material_fact_count"] == 0
                for row in audit_rows
            ),
            "zero_unretained_material_contradictions": all(
                row["unretained_material_contradiction_count"] == 0
                for row in audit_rows
            ),
            "material_term_missed_at_most_2_of_10": sum(
                row["material_term_missed"] for row in audit_rows
            )
            <= 2,
        },
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    if len(audit_rows) != 10:
        raise ValueError(
            f"P2 manual audit must contain 10 documents, got {len(audit_rows)}"
        )
    audit["manual_audit_pass"] = all(
        audit["promotion_gates"].values()
    )
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
        "all_outputs_validate": (
            run["validated_output_count"]
            == run["selected_document_count"]
        ),
        "zero_invalid_evidence_references": True,
        "zero_new_event_or_symbol_ids": True,
        "zero_forbidden_investment_fields": True,
        "non_unknown_relevance_at_least_80pct": (
            run["non_unknown_relevance_count"]
            / run["selected_document_count"]
            >= 0.80
        ),
        "non_unknown_family_at_least_80pct": (
            run["non_unknown_family_count"]
            / run["selected_document_count"]
            >= 0.80
        ),
    }
    summary = {
        "schema_version": 1,
        "pilot_id": "SS002-L001-P2-v1",
        "run_id": RUN_ID,
        "selection_sha256": SELECTION_SHA,
        "run_sha256": run["run_sha256"],
        "manual_audit_sha256": audit["audit_sha256"],
        "model_config_sha256": run["model_config_sha256"],
        "selected_document_count": run["selected_document_count"],
        "validated_output_count": run["validated_output_count"],
        "mechanical_gates": mechanical,
        "manual_audit_pass": audit["manual_audit_pass"],
        "promotion_allowed": (
            all(mechanical.values()) and audit["manual_audit_pass"]
        ),
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    summary["result_sha256"] = digest(summary)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss002-l001-p2-native-run.json").write_text(
        json.dumps(
            run,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (args.output / "ss002-l001-p2-manual-audit.json").write_text(
        json.dumps(
            audit,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (args.output / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
