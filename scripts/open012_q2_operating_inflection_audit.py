"""OPEN012: compare original FY26 IndiaMART and labelled FY27 Q2 news disclosures.

The 27-Oct-2026 Q2 numbers are SECONDARY company-filing transcriptions,
not raw issuer PDFs in this repo. Do not mix standalone with consolidated,
convert quarterly cash into owner FCFE, or retroactively update HG009.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN012_Q2_INDIAMART_CENTENKA_INPUT_20261027.json"
)


def number(v: object, field: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{field}: numeric fact required")
    result = float(v)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field}: positive finite fact required")
    return result


def growth(new: float, old: float) -> float:
    return round((new / old - 1) * 100, 2)


def compute(p: dict) -> dict:
    if p["schema"] != "OPEN012-20261027-Q2-CROSS_CYCLE_OPERATIONAL_CHECK-V1":
        raise ValueError("wrong report version")
    if p["date"] != "2026-10-27" or p["current_q2_release_date"] != "2026-10-27":
        raise ValueError("Q2 observation chronology changed")
    if p["market_price_reference_date"] != "2026-10-26":
        raise ValueError("cannot use post-release price as prior market input")
    if p["status"] != "POST_PUBLICATION_RESEARCH_NOT_HG009_ALPHA":
        raise ValueError("post-hoc report cannot be labeled prospective alpha")
    if p["guards"] != {
        "original_100_and_200_cohorts_unchanged": True,
        "source_raw_bytes_for_current_Q2_not_archived": True,
        "current_q2_exchange_dissemination_time_verified": False,
        "investment_approved": False,
        "capital_authorized": False,
        "owner_cash_verified": False,
        "shareholder_expected_return_probability": None,
    }:
        raise ValueError("false source provenance or investment approval")
    s = p["sources"]
    if not s["indiamart_fy26_q2_original_issuer_presentation"].startswith(
        "https://nsearchives.nseindia.com/corporate/INDIAMART_17102025"
    ) or s["indiamart_fy26_q2_source_page_indexes"] != [5, 7]:
        raise ValueError("original prior-source reference unavailable")
    if not all(s[k].startswith("https://businessupturn.com/") for k in (
        "indiamart_fy27_q2_secondary_article",
        "century_fy27_q2_secondary_article",
    )):
        raise ValueError("2026 Q2 source links not validated")
    if s["source_classification"] != (
        "FY26 original issuer prior-period reference; 2026-10-27 Q2 secondary "
        "issuer-filing press summaries, NOT original signed bytes nor trade-eligible freeze"
    ):
        raise ValueError("original financial source status overstated")

    im = p["indiamart"]
    if im["symbol"] != "INDIAMART" or im["isin"] != "INE933S01016":
        raise ValueError("IndiaMART issuer identity mismatch")
    if im["units"] != "INR_CRORE":
        raise ValueError("IndiaMART source units changed")
    old = im["Q2_FY26"]
    q1 = im["Q1_FY27"]
    q2 = im["Q2_FY27"]
    if [x["end"] for x in (old, q1, q2)] != [
        "2025-09-30", "2026-06-30", "2026-09-30"
    ]:
        raise ValueError("IndiaMART period comparisons shifted")
    if (
        old["basis"] != "ISSUER_ORIGINAL_NSE_PDF_VISUALLY_CHECKED"
        or q1["basis"] != "ISSUER_PRESS_RELEASE_TRANSCRIPTION_PREVIOUSLY_REVIEWED"
        or q2["basis"] !=
            "SECONDARY_Q2_NEWS_TRANSCRIPTION_ORIGINAL_ISSUER_PDF_UNVERIFIED"
    ):
        raise ValueError("IndiaMART source provenance changed")
    fields = (
        "consolidated_revenue", "consolidated_EBITDA", "consolidated_group_PAT",
        "consolidated_operating_cash", "consolidated_collections",
        "consolidated_deferred_revenue", "paying_suppliers",
    )
    checks = {field: number(q2[field], field) for field in fields}
    if old["annualized_revenue_per_paying_supplier_inr"] != 65000:
        raise ValueError("old ARPU source changed")
    if q2["annualized_revenue_per_paying_supplier_inr"] != 72000:
        raise ValueError("new ARPU requires precise issuer verification")
    if q1["annualized_revenue_per_paying_supplier_inr"] is not None:
        raise ValueError("unknown Q1 ARPU must stay null")
    im_growth = {}
    for name in fields:
        im_growth[name + "_YoY_pct"] = growth(
            checks[name], number(old[name], name + " previous year")
        )
        im_growth[name + "_QoQ_pct"] = growth(
            checks[name], number(q1[name], name + " prior quarter")
        )
    im_growth["ARPU_YoY_pct"] = growth(72000, 65000)
    for label, row in (("Q2FY26", old), ("Q1FY27", q1), ("Q2FY27", q2)):
        im_growth["CFO_to_collections_" + label + "_pct"] = round(
            number(row["consolidated_operating_cash"], "CFO")
            / number(row["consolidated_collections"], "collections") * 100, 2
        )
    if im_growth["paying_suppliers_YoY_pct"] >= 0:
        raise ValueError("new Q2 data must not fabricate supplier growth")
    if im_growth["consolidated_operating_cash_YoY_pct"] <= 0:
        raise ValueError("YoY CFO growth cannot be misstated as negative")

    ce = p["centuryenka"]
    if (ce["symbol"], ce["isin"], ce["units"]) != (
        "CENTENKA", "INE485A01015", "INR_CRORE"
    ):
        raise ValueError("Century Enka identity/unit mismatch")
    ce_old = ce["Q2_FY26_standalone"]
    ce_q1 = ce["Q1_FY27_standalone"]
    ce_q2 = ce["Q2_FY27_standalone"]
    if [x["end"] for x in (ce_old, ce_q1, ce_q2)] != [
        "2025-09-30", "2026-06-30", "2026-09-30"
    ]:
        raise ValueError("Century Enka financial period changed")
    if ce_q2["basis"] != (
        "SECONDARY_Q2_NEWS_TRANSCRIPTION_ORIGINAL_FILING_PENDING"
    ) or ce["Q2_original_issuer_signed_results_URL"] is not None:
        raise ValueError("Century Enka original Q2 bytes falsely asserted")
    margins = {}
    for label, period in (
        ("Q2FY26", ce_old), ("Q1FY27", ce_q1), ("Q2FY27", ce_q2)
    ):
        revenue = number(period["revenue"], label + " revenue")
        ebitda = number(period["EBITDA"], label + " EBITDA")
        number(period["PAT"], label + " standalone PAT")
        raw_material_fraction = period["raw_material_net_cost_fraction_of_revenue"]
        if not isinstance(raw_material_fraction, (int, float)) or (
            isinstance(raw_material_fraction, bool)
            or not (0 < raw_material_fraction < 1)
        ):
            raise ValueError("unverified raw material accounting")
        margins["standalone_EBITDA_margin_" + label + "_pct"] = round(
            ebitda / revenue * 100, 2
        )
    ce_growth = {
        "standalone_revenue_YoY_pct": growth(ce_q2["revenue"], ce_old["revenue"]),
        "standalone_EBITDA_YoY_pct": growth(ce_q2["EBITDA"], ce_old["EBITDA"]),
        "standalone_PAT_YoY_pct": growth(ce_q2["PAT"], ce_old["PAT"]),
        "standalone_revenue_QoQ_pct": growth(ce_q2["revenue"], ce_q1["revenue"]),
        "standalone_EBITDA_QoQ_pct": growth(ce_q2["EBITDA"], ce_q1["EBITDA"]),
        "standalone_PAT_QoQ_pct": growth(ce_q2["PAT"], ce_q1["PAT"]),
        "materials_pct_of_revenue_Q1_FY27": round(
            ce_q1["raw_material_net_cost_fraction_of_revenue"] * 100, 2
        ),
        "materials_pct_of_revenue_Q2_FY27": round(
            ce_q2["raw_material_net_cost_fraction_of_revenue"] * 100, 2
        ),
        "group_PAT_Q2_FY27_crore_secondary_only": number(
            ce["Q2_FY27_consolidated_PAT_from_article"], "group Q2 PAT"
        ),
        "group_PAT_Q1_FY27_crore_secondary_only": number(
            ce["Q1_FY27_consolidated_PAT_from_comparative_source"], "group Q1 PAT"
        ),
        "source_original_Q2_consolidated_operating_cash_crore": None,
    }
    ce_growth.update(margins)
    if ce_growth["standalone_EBITDA_QoQ_pct"] >= 0:
        raise ValueError("margin reversal cannot be marked positive")
    if ce_growth["materials_pct_of_revenue_Q2_FY27"] <= (
        ce_growth["materials_pct_of_revenue_Q1_FY27"]
    ):
        raise ValueError("quarterly raw input cost rise unproven")
    return {
        "research_date": p["date"],
        "current_Q2_original_source_eligible": False,
        "original_HG009_alpha_panel_modified": False,
        "capital_authorized": False,
        "investment_recommendation": "NONE",
        "INDIAMART": im_growth,
        "CENTENKA": ce_growth,
        "status":
            "SECONDARY_CURRENT_Q2_NEEDS_ORIGINAL_ISSUER_FINANCIAL_AND_CASH_SOURCE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(compute(json.loads(args.input.read_text())), indent=2,
                     sort_keys=True))


if __name__ == "__main__":
    main()
