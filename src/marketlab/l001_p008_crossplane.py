"""L001 P008: source-joined post-hoc valuation-falsification diagnostics.

Never interprets CFO-minus-PPE as owner cash, issued shares as diluted, or NSE
OHLC as executable price. Its late-captured October 15 close is NOT information
available by the October 15 18:30 IST AE001 decision cutoff.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from math import isclose, isfinite

from marketlab.alpha import AlphaContractError, digest

PINS = {
    "p004": "97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d",
    "p005": "69b33b1cce46fbdd1adb41f68a2e1416c62642f52489c6c3bdd6d8836a82ffe1",
    "p006": "8f85e798e05de7e00b469146ccff1e72962dba0e1fb42942f32bddb491cb7757",
    "p007": "ade5ea8f0d1e491fba4416443a8c5831b69cbbae81f6479bec61cfbba0e0c276",
    "oct15": "529b0680a7d6e2c42bcfe0a8f98a665acac34f7b38b2a46d87c9bcc36dfb3c7d",
}
P004_ID = "L001-P004-FROZEN-HG009-ALL100-ORIGINAL-REPLAY-v1"
PRICE_RECORD_ID = "HG009-P002-300-FROZEN-NSE-OFFICIAL-EQ-DAILY-v1"
OBSERVED = "ORIGINAL_NSE_EQ_OHLC_OBSERVED_NOT_FILL"


def _pin(doc: dict, field: str, expected: str) -> None:
    if doc.get(field) != expected or digest({k: v for k, v in doc.items() if k != field}) != expected:
        raise AlphaContractError("immutable input source panel hash changed")


def _by_symbol(rows: object, label: str) -> dict[str, dict]:
    if not isinstance(rows, list) or len(rows) != 100:
        raise AlphaContractError(f"{label}: exact 100-company source required")
    result: dict[str, dict] = {}
    for row in rows:
        symbol = row.get("symbol") if isinstance(row, dict) else None
        isin = row.get("isin") if isinstance(row, dict) else None
        if not isinstance(symbol, str) or not symbol or not isinstance(isin, str) or len(isin) != 12:
            raise AlphaContractError(f"{label}: malformed issuer identity")
        if symbol in result:
            raise AlphaContractError(f"{label}: duplicate issuer")
        result[symbol] = row
    return result


def _timestamp(value: object) -> datetime:
    try:
        dt = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        dt = None
    if dt is None or dt.utcoffset() != timedelta(0):
        raise AlphaContractError("source capture timestamp is not exact UTC")
    return dt


def _same_amount(first: object, second: object) -> bool:
    return (
        type(first) in (int, float) and type(second) in (int, float)
        and isfinite(first) and isfinite(second)
        and isclose(float(first), float(second), rel_tol=0, abs_tol=0.000002)
    )


def crossplane_diagnostic(
    p004: dict, p005: dict, p006: dict, p007: dict, daily_oct15: dict,
) -> dict:
    for item, field, pin in (
        (p004, "report_sha256", PINS["p004"]),
        (p005, "report_sha256", PINS["p005"]),
        (p006, "report_sha256", PINS["p006"]),
        (p007, "report_sha256", PINS["p007"]),
        (daily_oct15, "packet_sha256", PINS["oct15"]),
    ):
        _pin(item, field, pin)
    if (
        p004.get("report_id") != P004_ID
        or daily_oct15.get("record_id") != PRICE_RECORD_ID
        or daily_oct15.get("date_ist") != "2026-10-15"
        or daily_oct15.get("no_future_prices_used_in_cohort_selection") is not True
        or daily_oct15.get("live_capital_allowed") is not False
        or p005.get("nbfc_financial_accounting_forms") != 8
        or p006.get("annual_originals_verified") != 100
        or p007.get("original_quarter_xbrl_hashes_verified") != 100
    ):
        raise AlphaContractError("source semantic contract not fulfilled")
    source_capture = _timestamp(daily_oct15.get("original_source_market_captured_at_utc"))
    if source_capture <= _timestamp("2026-10-15T13:00:00Z"):
        raise AlphaContractError("expected late-captured October 15 price semantics changed")
    source_a = _by_symbol(p004.get("source_results"), "P004")
    source_b = _by_symbol(p005.get("companies"), "P005")
    source_c = _by_symbol(p006.get("companies"), "P006")
    source_d = _by_symbol(p007.get("companies"), "P007")
    ids = {(symbol, row["isin"]) for symbol, row in source_a.items()}
    for label, panel in (("P005", source_b), ("P006", source_c), ("P007", source_d)):
        if {(symbol, row["isin"]) for symbol, row in panel.items()} != ids:
            raise AlphaContractError(f"{label}: original 100 issuer identities differ")
    prices = daily_oct15.get("source_identity_rows")
    if not isinstance(prices, list) or len(prices) != 300:
        raise AlphaContractError("price daily packet does not contain frozen 300 arms")
    selected = [r for r in prices if r.get("arm") == "SELECTED"]
    if len(selected) != 100:
        raise AlphaContractError("frozen selected source prices not 100")
    price_map = {}
    for row in selected:
        key = (row.get("symbol"), row.get("frozen_isin"))
        if key in price_map or key not in ids:
            raise AlphaContractError("source price identity missing or duplicate")
        if row.get("actual_trade_fill") is not False:
            raise AlphaContractError("historical NSE close is not an order fill")
        price_map[key] = row
    if set(price_map) != ids:
        raise AlphaContractError("original frozen price universe changed")
    companies = []
    for symbol, original in sorted(source_a.items()):
        isin = original["isin"]
        format_row, cash_row, income_row = source_b[symbol], source_c[symbol], source_d[symbol]
        pricing = price_map[(symbol, isin)]
        observed = pricing.get("state") == OBSERVED and isinstance(pricing.get("ohlcv"), dict)
        if observed:
            close = pricing["ohlcv"].get("close_inr")
            if type(close) not in (float, int) or not isfinite(close) or close <= 0:
                raise AlphaContractError("original NSE close price malformed")
        elif pricing.get("state") == "MISSING_EQ_IDENTITY_NO_SUBSTITUTION":
            close = None
        else:
            raise AlphaContractError("unknown original price source state")
        annual = original["financial_sources"]["annual"]["accounting_basis"]
        quarter = original["financial_sources"]["quarter"]["accounting_basis"]
        cf = cash_row.get("fy26_cashflow_components_cr_from_original")
        q1 = income_row.get("q1_original_income_facts_cr")
        if not isinstance(cf, dict) or not isinstance(q1, dict):
            raise AlphaContractError("original cash or quarterly source facts unavailable")
        if (
            not _same_amount(cf.get("cfo_reported"), original.get("fy26_operating_cfo_cr"))
            or not _same_amount(cf.get("ppe_cash_purchase"), original.get("fy26_ppe_purchase_cr"))
            or not _same_amount(q1.get("revenue_operations"), original.get("q1fy27_revenue_cr"))
            or not _same_amount(q1.get("profit_loss_for_period"), original.get("q1fy27_pat_cr"))
            or cash_row.get("original_xml_sha256") != original["financial_sources"]["annual"]["raw_sha256"]
            or income_row.get("original_quarter_sha256") != original["financial_sources"]["quarter"]["raw_sha256"]
        ):
            raise AlphaContractError("cross-plane original FY26/Q1 accounting facts drifted")
        is_financial = format_row["requires_financial_institution_specialist_review"] is True
        if format_row["source_based_accounting_format"] not in {
            "NSE_GENERAL_INDAS_ACCOUNTING_FORMAT",
            "NSE_NBFC_INDAS_FINANCIAL_ACCOUNTING_FORMAT",
        }:
            raise AlphaContractError("unverified original financial reporting basis")
        issued = original.get("reported_issued_shares_not_fully_diluted")
        if type(issued) is not int or issued <= 0:
            raise AlphaContractError("historical share count missing")
        cap_eligible = original.get("capitalization_source_eligible") is True
        basic_cap_cr = round(close * issued / 10000000, 6) if close is not None and cap_eligible else None
        same_consolidated = annual == "Consolidated" and quarter == "Consolidated"
        interpretive_basis = basic_cap_cr is not None and same_consolidated and not is_financial
        cash_yield = (
            round(100 * original["fy26_cfo_less_ppe_cr_not_owner_cash"] / basic_cap_cr, 6)
            if interpretive_basis and basic_cap_cr > 0 else None
        )
        receivable = cash_row.get("fy26_total_trade_receivable_cash_adjustment_cr")
        cfo = original["fy26_operating_cfo_cr"]
        other_share = income_row.get("other_income_as_positive_pbt_pct_arithmetic_only")
        flags: list[str] = []
        if is_financial:
            flags.append("NBFC_FORMAT_NO_INDUSTRIAL_CASH_VALUATION")
        if not same_consolidated:
            flags.append("NONCONSOLIDATED_OR_MIXED_SCOPE")
        if basic_cap_cr is None:
            flags.append("UNVERIFIED_HISTORICAL_PRICE_OR_SHARE_DENOMINATOR")
        if (
            type(receivable) in (float, int) and type(cfo) in (float, int)
            and cfo > 0 and receivable > 0.5 * cfo
        ):
            flags.append("RECEIVABLE_CASH_RELEASE_GT_HALF_CFO")
        if type(other_share) in (float, int) and other_share >= 50:
            flags.append("Q1_OTHER_INCOME_GT_HALF_POSITIVE_PBT")
        if cash_row.get("standard_ppe_taxonomy_caution") is not None:
            flags.append("STANDARD_PPE_TAXONOMY_INCOMPLETE")
        if cash_yield is not None and cash_yield > 20:
            flags.append("UNUSUALLY_HIGH_MECHANICAL_CASH_PROXY_REVIEW")
        companies.append({
            "symbol": symbol, "isin": isin, "fy26_annual_basis": annual,
            "q1fy27_basis": quarter, "source_price_date": "2026-10-15",
            "original_close_inr_not_fill": close,
            "historical_basic_cap_cr_issued_share_only": basic_cap_cr,
            "q1_other_income_to_pbt_pct_not_nonrecurring_proof": other_share,
            "fy26_cfo_minus_ppe_cr_not_owner_cash": original["fy26_cfo_less_ppe_cr_not_owner_cash"],
            "fy26_cfo_to_net_investing_cr_not_owner_cash": (
                round(cfo + cf["net_investing_cash"], 6)
                if type(cf.get("net_investing_cash")) in (float, int) else None
            ),
            "cash_proxy_over_historical_basic_cap_pct_not_owner_cash_yield": cash_yield,
            "review_cautions": sorted(flags),
            "basic_cap_share_source_not_fully_diluted": True,
            "all_financial_assets_and_claims_reconciled": False,
            "original_review_is_posthoc_not_outcome_blind": True,
            "expected_return": None, "investment_authorized": False,
        })
    report = {
        "schema_version": 1,
        "report_id": "L001-P008-POSTHOC-CROSSPLANE-ECONOMIC-FALSIFICATION-v1",
        "input_source_sha256s": PINS,
        "source_price_captured_at_utc": daily_oct15["original_source_market_captured_at_utc"],
        "oct15_1830_ist_ae001_signal_eligible": False,
        "source_cohort_count": len(companies),
        "historical_priced_company_count": sum(x["original_close_inr_not_fill"] is not None for x in companies),
        "basic_price_share_denominator_ready_count": sum(
            x["historical_basic_cap_cr_issued_share_only"] is not None for x in companies
        ),
        "strictly_comparable_indas_non_nbfc_ratio_count": sum(
            x["cash_proxy_over_historical_basic_cap_pct_not_owner_cash_yield"] is not None
            for x in companies
        ),
        "reported_nbfc_form_cautions": sum(
            "NBFC_FORMAT_NO_INDUSTRIAL_CASH_VALUATION" in x["review_cautions"]
            for x in companies
        ),
        "no_intrinsic_value_or_alpha": True, "capital_eligible": False,
        "source_outcomes_not_used_to_fit_screen": True,
        "research_screen_is_posthoc_and_not_a_preregistered_hg009_factor": True,
        "companies": companies, "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
