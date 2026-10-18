"""L001 P013: exceptional-profit accounting reconciliation for frozen HG009-100.

All inputs are original Q1 FY27 issuer XBRL bytes anchored in P004/P007.
The ordinary NSE statement notion of "exceptional" is not a reliable
economic nonrecurrence test. Neither a PBT adjustment nor its tax effect
is a normalized earnings forecast. No historic alpha is inferred.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p007_earnings_components import original_income_values

P004_SHA = "97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d"
P007_SHA = "ade5ea8f0d1e491fba4416443a8c5831b69cbbae81f6479bec61cfbba0e0c276"
SOURCE_CUTOFF = "2026-10-15T13:00:00Z"
MATERIAL_POSITIVE_EXCEPTIONAL_PBT_RATIO = 0.50


def _bound_original(doc: dict, *, sha: str, tag: str) -> None:
    if not isinstance(doc, dict) or doc.get("report_sha256") != sha:
        raise AlphaContractError(f"{tag}: source not pinned")
    if digest({k: v for k, v in doc.items() if k != "report_sha256"}) != sha:
        raise AlphaContractError(f"{tag}: source contents changed")


def _utc(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("original exchange publication timestamp invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise AlphaContractError("exchange publication timestamp must be UTC")
    return stamp


def _facts_equal(a: dict, b: dict) -> bool:
    if a.keys() != b.keys():
        return False
    return all(
        a[k] is None and b[k] is None or (
            type(a[k]) in (float, int) and type(b[k]) in (float, int)
            and math.isfinite(a[k]) and math.isfinite(b[k])
            and abs(float(a[k]) - float(b[k])) <= 0.000002
        )
        for k in a
    )


def exceptional_profit_replay(
    p004_report: dict,
    p007_report: dict,
    original_quarter_xml: dict[str, bytes],
) -> dict:
    """Re-derive Q1 before-exceptional / exceptional / PBT from original bytes.

    The post-hoc diagnostic does not try to remove after-tax exceptional gains
    from PAT or produce a tradable ranking from the already observed figures.
    """
    _bound_original(p004_report, sha=P004_SHA, tag="P004")
    _bound_original(p007_report, sha=P007_SHA, tag="P007")
    original = p004_report.get("source_results")
    rows = p007_report.get("companies")
    if (
        p004_report.get("company_count") != 100
        or p007_report.get("company_count") != 100
        or p007_report.get("original_quarter_xbrl_hashes_verified") != 100
        or p007_report.get("q1_numerical_cells_read_directly") != 700
        or p007_report.get("p004_source_sha256") != P004_SHA
        or p007_report.get("live_capital_allowed") is not False
        or not isinstance(original, list) or not isinstance(rows, list)
        or len(original) != 100 or len(rows) != 100
    ):
        raise AlphaContractError("P013 original 100-issuer accounting provenance invalid")
    by_original: dict[tuple[str, str], dict] = {}
    expected_shas = set()
    for x in original:
        key = (x["symbol"], x["isin"])
        if key in by_original:
            raise AlphaContractError("P004 issuer identity duplicated")
        by_original[key] = x
        expected_shas.add(x["financial_sources"]["quarter"]["raw_sha256"])
    if set(original_quarter_xml) != expected_shas:
        raise AlphaContractError("P013 exact 100 original Q1 XBRL files required")
    cutoff = _utc(SOURCE_CUTOFF)
    members = []
    for item in rows:
        key = (item["symbol"], item["isin"])
        prior = by_original.get(key)
        if prior is None:
            raise AlphaContractError("P013 exact original symbol/ISIN not found")
        source_meta = prior["financial_sources"]["quarter"]
        sha = source_meta["raw_sha256"]
        raw = original_quarter_xml[sha]
        if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != sha:
            raise AlphaContractError("P013 issuer Q1 original bytes missing or altered")
        if (
            sha != item["original_quarter_sha256"]
            or source_meta["period_end"] != "2026-06-30"
            or source_meta["accounting_basis"] != item["reported_scope"]
            or item["original_quarter_issued_at_utc"] != source_meta["exchange_published_at_utc"]
            or _utc(item["original_quarter_issued_at_utc"]) > cutoff
        ):
            raise AlphaContractError("P013 filing scope or timestamp drift")
        actual = original_income_values(raw)
        if not _facts_equal(actual, item["q1_original_income_facts_cr"]):
            raise AlphaContractError("P013 parsed original earnings disagree with P007")
        revenue, pat = actual["revenue_operations"], actual["profit_loss_for_period"]
        if (
            revenue is None or pat is None
            or abs(revenue - prior["q1fy27_revenue_cr"]) > .000002
            or abs(pat - prior["q1fy27_pat_cr"]) > .000002
        ):
            raise AlphaContractError("P013 Q1 primary XBRL source accounting drift")
        before = actual["profit_before_exceptional"]
        after = actual["profit_before_tax"]
        exceptional = actual["exceptional_items_before_tax"]
        if before is None or after is None or exceptional is None:
            raise AlphaContractError("P013 original exceptional bridge incomplete")
        if abs(round(before + exceptional - after, 6)) > .000002:
            raise AlphaContractError("P013 original PBT bridge does not reconcile")
        if abs(exceptional) < .000001:
            sign = "NONE_REPORTED"
        elif exceptional > 0:
            sign = "POSITIVE"
        else:
            sign = "NEGATIVE"
        share = (
            round(exceptional / after, 8)
            if after > 0 else None
        )
        large = (
            sign == "POSITIVE" and share is not None
            and share >= MATERIAL_POSITIVE_EXCEPTIONAL_PBT_RATIO
            and item["nbfc_source_form_requires_specialist_review"] is False
        )
        members.append({
            "symbol": item["symbol"],
            "isin": item["isin"],
            "original_quarter_sha256": sha,
            "original_issuer_publication_utc": item["original_quarter_issued_at_utc"],
            "financial_accounting_basis": item["reported_scope"],
            "nbfc_filing_format_requires_specialist_review": item[
                "nbfc_source_form_requires_specialist_review"
            ],
            "reported_q1_pbt_before_exceptional_cr": before,
            "reported_q1_exceptional_item_cr": exceptional,
            "reported_q1_pbt_after_exceptional_cr": after,
            "reported_q1_pat_cr_not_parent_attributable": pat,
            "exceptional_item_sign": sign,
            "exceptional_item_divided_by_positive_pbt_fraction": share,
            "large_positive_exceptional_vs_pbt_diagnostic": large,
            "pbt_excluding_exceptional_mechanically_cr_not_normalized_operating_income": before,
            "exceptional_item_cash_receipt_proven": False,
            "nonrecurrence_and_after_tax_adjustment_verified": False,
            "parent_attributable_normalized_profit": None,
            "expected_return": None,
            "investment_authorized": False,
        })
    if len({(x["symbol"], x["isin"]) for x in members}) != 100:
        raise AlphaContractError("P013 original cohort identity duplication")
    members.sort(key=lambda x: (x["symbol"], x["isin"]))
    report = {
        "schema_version": 1,
        "report_id": "L001-P013-Q1-FY27-ORIGINAL-EXCEPTIONAL-PROFIT-ALL100-v1",
        "original_p004_report_sha256": P004_SHA,
        "original_p007_report_sha256": P007_SHA,
        "source_exchange_publication_cutoff_utc": SOURCE_CUTOFF,
        "review_compiled_posthoc_not_pre_registered_signal": True,
        "original_company_count": len(members),
        "original_q1_sha256_files_reopened_and_replayed": len(original_quarter_xml),
        "original_quarterly_numeric_facts_replayed": len(members) * 7,
        "positive_exceptional_count": sum(r["exceptional_item_sign"] == "POSITIVE" for r in members),
        "negative_exceptional_count": sum(r["exceptional_item_sign"] == "NEGATIVE" for r in members),
        "zero_exceptional_count": sum(r["exceptional_item_sign"] == "NONE_REPORTED" for r in members),
        "major_positive_exceptional_over_half_pbt_symbols_posthoc": [
            r["symbol"] for r in members if r["large_positive_exceptional_vs_pbt_diagnostic"]
        ],
        "before_exceptional_pbt_is_not_normalized_earnings": True,
        "after_tax_exceptional_cash_reconciliation_available": False,
        "price_outcomes_consulted": False,
        "forecast_or_stock_rank_created": False,
        "live_capital_allowed": False,
        "companies": members,
    }
    report["report_sha256"] = digest(report)
    return report
