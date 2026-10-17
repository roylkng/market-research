"""L001 P006: archived XBRL cash-flow component diagnostics for 100 issuers.

This is post-hoc *accounting falsification*, not an alpha feature. Exact FY26
original XML, signed P004 bridge and all 100 identities are required. It does
not infer recurring FCF, correct capex taxonomy, or rank potential investments.
"""

from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET

from marketlab.alpha import AlphaContractError, digest

P004_SHA256 = "97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d"
CASH_TAGS = {
    "cfo_reported": "CashFlowsFromUsedInOperatingActivities",
    "pre_tax_operating_cash": "CashFlowsFromUsedInOperations",
    "trade_receivables_current_change": "AdjustmentsForDecreaseIncreaseInTradeReceivablesCurrent",
    "trade_receivables_noncurrent_change": "AdjustmentsForDecreaseIncreaseInTradeReceivablesNoncurrent",
    "inventory_cash_change": "AdjustmentsForDecreaseIncreaseInInventories",
    "trade_payables_current_change": "AdjustmentsForIncreaseDecreaseInTradePayablesCurrent",
    "net_investing_cash": "CashFlowsFromUsedInInvestingActivities",
    "other_investing_net": "OtherInflowsOutflowsOfCashClassifiedAsInvestingActivities",
    "ppe_cash_purchase": "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    "ppe_disposal_receipts": (
        "ProceedsFromSalesOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
    ),
}


def _extract_original_cash_tags(root: ET.Element) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    for name, concept in CASH_TAGS.items():
        matches = []
        for element in root.iter():
            if (
                element.tag.rsplit("}", 1)[-1] == concept
                and element.attrib.get("contextRef") == "FourD"
                and element.attrib.get("unitRef") == "INR"
            ):
                try:
                    amount = float(element.text)
                except (ValueError, TypeError) as exc:
                    raise AlphaContractError("original cash component not numeric") from exc
                if not math.isfinite(amount):
                    raise AlphaContractError("original cash component not finite")
                matches.append(amount)
        if len(set(matches)) > 1:
            raise AlphaContractError("conflicting original XBRL cash component facts")
        values[name] = None if not matches else round(matches[0] / 10000000, 6)
    return values


def cashflow_quality_context(p004: dict, original_annual_xml: dict[str, bytes]) -> dict:
    """Reconcile all 100 exact original cash-flow statements, without ranking."""
    unsigned = {k: v for k, v in p004.items() if k != "report_sha256"}
    if (
        p004.get("report_sha256") != P004_SHA256
        or digest(unsigned) != P004_SHA256
        or p004.get("company_count") != 100
        or p004.get("original_xml_sha256_checked") != 300
    ):
        raise AlphaContractError("P004 original source evidence pin failed")
    records = p004.get("source_results")
    if not isinstance(records, list) or len(records) != 100:
        raise AlphaContractError("original 100-company evidence set incomplete")
    expected_raw = {row["financial_sources"]["annual"]["raw_sha256"] for row in records}
    if set(original_annual_xml) != expected_raw:
        raise AlphaContractError("exact 100 original annual XBRL inputs required")
    output = []
    for row in records:
        sha = row["financial_sources"]["annual"]["raw_sha256"]
        raw = original_annual_xml.get(sha)
        if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != sha:
            raise AlphaContractError("original annual XBRL source hash mismatch")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise AlphaContractError("original annual XBRL XML invalid") from exc
        cells = _extract_original_cash_tags(root)
        if (
            cells["cfo_reported"] != row["fy26_operating_cfo_cr"]
            or cells["ppe_cash_purchase"] != row["fy26_ppe_purchase_cr"]
        ):
            raise AlphaContractError("original CFO/PPE does not reproduce P004")
        cfo = cells["cfo_reported"]
        assert cfo is not None
        recv = [
            cells["trade_receivables_current_change"],
            cells["trade_receivables_noncurrent_change"],
        ]
        recv_present = [x for x in recv if x is not None]
        receivable_adjustment = (
            round(sum(recv_present), 6) if len(recv_present) == 2 else None
        )
        # Algebraic single-item subtraction. NOT normalized CFO or a trading
        # cash-flow forecast: other working capital, taxes and disposed entities
        # remain undisentangled.
        without_receivable_sensitivity = (
            round(cfo - receivable_adjustment, 6)
            if receivable_adjustment is not None else None
        )
        # Source diagnostics only, deliberately no return-ranked screen.
        missing_or_zero_taxonomy = (
            "ZERO_STANDARD_PPE_WHILE_NET_INVESTING_MATERIAL"
            if cells["ppe_cash_purchase"] == 0
            and cells["net_investing_cash"] is not None
            and abs(cells["net_investing_cash"]) > 100
            else None
        )
        output.append({
            "symbol": row["symbol"],
            "isin": row["isin"],
            "financial_accounting_scope": row["financial_sources"]["annual"]["accounting_basis"],
            "original_xml_sha256": sha,
            "fy26_cashflow_components_cr_from_original": cells,
            "fy26_total_trade_receivable_cash_adjustment_cr": receivable_adjustment,
            "fy26_cfo_without_receivable_adjustment_arithmetic_only_cr": (
                without_receivable_sensitivity
            ),
            "standard_ppe_taxonomy_caution": missing_or_zero_taxonomy,
            "liquidation_acquisition_and_disposal_normalization_unverified": True,
            "noncash_working_capital_changes_not_owner_cash": True,
            "llm_historical_alpha_signal_created": False,
            "fair_value_cr": None,
            "investment_authorized": False,
        })
    output.sort(key=lambda row: (row["symbol"], row["isin"]))
    if len({(x["symbol"], x["isin"]) for x in output}) != 100:
        raise AlphaContractError("source identity duplication")
    pnc = next(row for row in output if row["symbol"] == "PNCINFRA")
    oil = next(row for row in output if row["symbol"] == "OIL")
    report = {
        "schema_version": 1,
        "report_id": "L001-P006-ALL100-ORIGINAL-CASHFLOW-ANOMALY-EXPLANATION-v1",
        "p004_sha256": P004_SHA256,
        "company_count": 100,
        "annual_originals_verified": 100,
        "pnc_receivable_original_cr": pnc[
            "fy26_cashflow_components_cr_from_original"
        ]["trade_receivables_noncurrent_change"],
        "pnc_cfo_excluding_one_component_sensitivity_cr": pnc[
            "fy26_cfo_without_receivable_adjustment_arithmetic_only_cr"
        ],
        "oil_general_ppe_concept_zero_but_material_investing_outflow": (
            oil["standard_ppe_taxonomy_caution"] is not None
        ),
        "no_stock_selection_ranking_or_return_model": True,
        "all_source_only": True,
        "live_capital_allowed": False,
        "companies": output,
    }
    report["report_sha256"] = digest(report)
    return report
