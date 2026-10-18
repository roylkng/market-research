"""L001 P007: source-exact FY27 Q1 earnings composition for original 100.

Authenticated XBRL original from P004, not earnings prediction. Other income
may be recurring or valuable financial investment return; its proportion of
PBT is a diagnostic, not proof of low quality or a sell signal.
"""

from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET

from marketlab.alpha import AlphaContractError, digest

P004_SHA256 = "97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d"
TAGS = {
    "revenue_operations": "RevenueFromOperations",
    "other_income": "OtherIncome",
    "finance_costs": "FinanceCosts",
    "profit_before_exceptional": "ProfitBeforeExceptionalItemsAndTax",
    "exceptional_items_before_tax": "ExceptionalItemsBeforeTax",
    "profit_before_tax": "ProfitBeforeTax",
    "profit_loss_for_period": "ProfitLossForPeriod",
}


def original_income_values(raw: bytes) -> dict[str, float | None]:
    """Exact INR/OneD source cells. Missing stays null, conflict rejects."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise AlphaContractError("original quarter financial XBRL is invalid") from exc
    result: dict[str, float | None] = {}
    for key, concept in TAGS.items():
        matches = []
        for element in root.iter():
            if (
                element.tag.rsplit("}", 1)[-1] == concept
                and element.attrib.get("contextRef") == "OneD"
                and element.attrib.get("unitRef") == "INR"
            ):
                try:
                    value = float(element.text) / 10000000
                except (ValueError, TypeError) as exc:
                    raise AlphaContractError("original quarterly financial cell nonnumeric") from exc
                if not math.isfinite(value):
                    raise AlphaContractError("original quarterly financial cell nonfinite")
                matches.append(round(value, 6))
        if len(set(matches)) > 1:
            raise AlphaContractError("conflicting original Q1 source cell")
        result[key] = None if not matches else matches[0]
    return result


def q1_income_quality_context(p004: dict, original_quarter_xml: dict[str, bytes]) -> dict:
    """Review all 100 Q1 original earnings decompositions without a buy score."""
    unsigned = {k: v for k, v in p004.items() if k != "report_sha256"}
    if (
        p004.get("report_sha256") != P004_SHA256
        or digest(unsigned) != P004_SHA256
        or p004.get("company_count") != 100
        or p004.get("original_numeric_xbrl_values_replayed") != 400
    ):
        raise AlphaContractError("P004 pinned original financial panel changed")
    originals = p004.get("source_results")
    if not isinstance(originals, list) or len(originals) != 100:
        raise AlphaContractError("P004 original company set incomplete")
    expected = {row["financial_sources"]["quarter"]["raw_sha256"] for row in originals}
    if set(original_quarter_xml) != expected:
        raise AlphaContractError("exact 100 original Q1 filing bytes required")
    rows = []
    for issuer in originals:
        meta = issuer["financial_sources"]["quarter"]
        if meta["period_end"] != "2026-06-30":
            raise AlphaContractError("original Q1 reporting period drift")
        sha = meta["raw_sha256"]
        raw = original_quarter_xml.get(sha)
        if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != sha:
            raise AlphaContractError("original Q1 source byte integrity failed")
        facts = original_income_values(raw)
        if (
            facts["revenue_operations"] != issuer["q1fy27_revenue_cr"]
            or facts["profit_loss_for_period"] != issuer["q1fy27_pat_cr"]
        ):
            raise AlphaContractError("original revenue/PAT does not match P004 source")
        pbt, other = facts["profit_before_tax"], facts["other_income"]
        gross_pct = (
            round(100 * other / pbt, 6)
            if pbt is not None and other is not None and pbt > 0
            else None
        )
        # No reclassification as core EBIT; subtraction is arithmetic only.
        pbt_less_other = (
            round(pbt - other, 6)
            if pbt is not None and other is not None else None
        )
        document_type = meta["original_url"].rsplit("/", 1)[-1].upper()
        nbfc_format = document_type.startswith("INTEGRATED_FILING_NBFC_INDAS_")
        rows.append({
            "symbol": issuer["symbol"],
            "isin": issuer["isin"],
            "original_quarter_sha256": sha,
            "original_quarter_issued_at_utc": meta["exchange_published_at_utc"],
            "reported_scope": meta["accounting_basis"],
            "nbfc_source_form_requires_specialist_review": nbfc_format,
            "q1_original_income_facts_cr": facts,
            "other_income_as_positive_pbt_pct_arithmetic_only": gross_pct,
            "pbt_excluding_other_income_arithmetic_only_cr": pbt_less_other,
            "other_income_recurring_or_nonrecurring_not_established": True,
            "profit_attributable_to_parent_not_proven": True,
            "after_tax_normalized_core_earnings": None,
            "business_intrinsic_value": None,
            "expected_return": None,
            "investment_authorized": False,
        })
    rows.sort(key=lambda x: (x["symbol"], x["isin"]))
    if len({(x["symbol"], x["isin"]) for x in rows}) != 100:
        raise AlphaContractError("duplicate original issuer identity")
    ratio_count = sum(x["other_income_as_positive_pbt_pct_arithmetic_only"] is not None
                      for x in rows)
    evidence_cautions = [
        x["symbol"] for x in rows
        if x["other_income_as_positive_pbt_pct_arithmetic_only"] is not None
        and x["other_income_as_positive_pbt_pct_arithmetic_only"] >= 50
        and not x["nbfc_source_form_requires_specialist_review"]
    ]
    report = {
        "schema_version": 1,
        "report_id": "L001-P007-ORIGINAL-Q1-OTHER-INCOME-TRIAGE-ALL100-v1",
        "p004_source_sha256": P004_SHA256,
        "company_count": 100,
        "original_quarter_xbrl_hashes_verified": 100,
        "q1_numerical_cells_read_directly": 7 * 100,
        "positive_pbt_denominator_ratio_available_count": ratio_count,
        "other_income_gte_50pct_pbt_diagnostic_non_nbfc_symbols": evidence_cautions,
        "ratio_cutoff_is_posthoc_triage_not_frozen_alpha": True,
        "note": "Other income may be recurring; an earnings-quality label needs original note review.",
        "no_return_model_or_company_selection": True,
        "live_capital_allowed": False,
        "companies": rows,
    }
    report["report_sha256"] = digest(report)
    return report
