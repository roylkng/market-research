"""HG009 P013: original-NSE FY26 cash-use reconciliation for three issuers.

Replays the three first-byte-attested original issuer iXBRL files from P009.
Unlike CFO-minus-PPE, it reconciles *all* reported investing and financing
cash, dividends, leases and large investment purchases to closing cash.

Numbers are issuer-reported cash classifications, not normalized owner cash,
economic expense, equity intrinsic value, or predicted shareholder return.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p008_underwriting import load_sources
from marketlab.hg009_p009_attestation import (
    SOURCES,
    _original_receipt,
    build_original_attestation,
)

ID = "HG009-P013-20261016-THREE-FY26-ORIGINAL-CASH-USE-BRIDGES-v1"
END = "2026-03-31"
# All explicitly from the original FY26 *consolidated* cashflow statement.
# Amounts are INR lakh; positive flow labels for purchases/lease payments
# mean outflow and are subtracted only when constructing sign-adjusted flows.
FIELDS = {
    "cfo": ("operating", "net cash flows from (used in) operating activities"),
    "net_investing": ("investing", "net cash flows from (used in) investing activities"),
    "net_financing": ("financing", "net cash flows from (used in) financing activities"),
    "cash_begin": ("financing", "cash and cash equivalents cash flow statement at beginning of period"),
    "cash_end": ("financing", "cash and cash equivalents cash flow statement at end of period"),
    "cash_change": ("financing", "net increase (decrease) in cash and cash equivalents"),
    "ppe_purchase": ("investing", "purchase of property, plant and equipment"),
    "investments_sold": ("investing", "other cash receipts from sales of equity or debt instruments of other entities"),
    "investments_bought": ("investing", "other cash payments to acquire equity or debt instruments of other entities"),
    "lease_paid": ("financing", "payments of lease liabilities"),
    "interest_paid": ("financing", "interest paid"),
    "dividends_paid": ("financing", "dividends paid"),
    "borrowings_drawn": ("financing", "proceeds from borrowings"),
    "borrowings_repaid": ("financing", "repayments of borrowings"),
    "change_in_inventory": ("operating", "adjustments for decrease (increase) in inventories"),
    "change_in_trade_receivables": ("operating", "adjustments for decrease (increase) in trade receivables, current"),
    "change_in_trade_payables": ("operating", "adjustments for increase (decrease) in trade payables, current"),
}
# Original NSE source cells individually checked before this review.
EXPECTED_LAKH = {
    "ACUTAAS": {
        "cfo": "29217.36", "net_investing": "-26594.30",
        "net_financing": "409.62", "cash_begin": "18522.43",
        "cash_end": "21555.11", "cash_change": "3032.68",
        "ppe_purchase": "32797.88", "investments_sold": "0",
        "investments_bought": "0", "lease_paid": "66.30",
        "interest_paid": "127.80", "dividends_paid": "1228.03",
        "borrowings_drawn": "1830.65", "borrowings_repaid": "0",
        "change_in_inventory": "-5138.35",
        "change_in_trade_receivables": "-5549.08",
        "change_in_trade_payables": "-213.90",
    },
    "ACE": {
        "cfo": "41727.00", "net_investing": "-34989.00",
        "net_financing": "-5191.00", "cash_begin": "4884.00",
        "cash_end": "6431.00", "cash_change": "1547.00",
        "ppe_purchase": "9326.00", "investments_sold": "50832.00",
        "investments_bought": "83107.00", "lease_paid": "145.00",
        "interest_paid": "1261.00", "dividends_paid": "2380.00",
        "borrowings_drawn": "69169.00", "borrowings_repaid": "70637.00",
        "change_in_inventory": "-9028.00",
        "change_in_trade_receivables": "-2985.00",
        "change_in_trade_payables": "9611.00",
    },
    "TRAVELFOOD": {
        "cfo": "39296.80", "net_investing": "-14980.70",
        "net_financing": "-22073.70", "cash_begin": "2529.60",
        "cash_end": "4772.00", "cash_change": "2242.40",
        "ppe_purchase": "3853.20", "investments_sold": "78914.20",
        "investments_bought": "93363.70", "lease_paid": "12370.40",
        "interest_paid": "3005.60", "dividends_paid": "6004.60",
        "borrowings_drawn": "0", "borrowings_repaid": "0",
        "change_in_inventory": "-364.00",
        "change_in_trade_receivables": "-17674.20",
        "change_in_trade_payables": "2527.00",
    },
}
SECTIONS = {
    "cash flows from used in operating activities": "operating",
    "cash flows from used in investing activities": "investing",
    "cash flows from used in financing activities": "financing",
}

def _to_lakh(text: str) -> Decimal:
    t = text.strip().replace(",", "").replace("\u00a0", "")
    negative = t.startswith("(") and t.endswith(")")
    if negative:
        t = t[1:-1]
    try:
        value = Decimal(t)
    except InvalidOperation as exc:
        raise AlphaContractError("P013 original NSE cash-flow cell not numeric") from exc
    if not value.is_finite():
        raise AlphaContractError("P013 nonfinite original issuer cash") 
    return -value if negative else value

def _row_values(raw: bytes) -> dict[tuple[str, str], list[Decimal]]:
    html = BeautifulSoup(raw, "html.parser")
    entered = False
    section = None
    values: dict[tuple[str, str], list[Decimal]] = {}
    for tr in html.find_all("tr"):
        if tr.find("tr") is not None:
            continue
        cells = [
            " ".join(td.get_text(" ", strip=True).split()).casefold()
            for td in tr.find_all(["td", "th"], recursive=False)
        ]
        if len(cells) < 2:
            continue
        label = cells[-2]
        entry = cells[-1]
        if label == "statement of cash flows":
            entered = True
            continue
        if not entered:
            continue
        if label in SECTIONS:
            section = SECTIONS[label]
            continue
        if section is not None and entry:
            try:
                number = _to_lakh(entry)
            except AlphaContractError:
                continue  # nonfinancial original header, never matched as a value
            values.setdefault((section, label), []).append(number)
    return values

def extract_exact_fy26_cells(raw: bytes, symbol: str) -> dict[str, Decimal]:
    if symbol not in EXPECTED_LAKH:
        raise AlphaContractError("P013 unexpected original NSE company")
    found = _row_values(raw)
    result = {}
    for key, (section, label) in FIELDS.items():
        hits = found.get((section, label), [])
        if len(hits) != 1:
            raise AlphaContractError(
                f"P013 missing or duplicated original FY26 cash row: {symbol}/{key}"
            )
        expected = Decimal(EXPECTED_LAKH[symbol][key])
        if hits[0] != expected:
            raise AlphaContractError(
                f"P013 source FY26 number differs: {symbol}/{key}"
            )
        result[key] = hits[0]
    return result

def _crore(amount_lakh: Decimal) -> float:
    return float((amount_lakh / Decimal(100)).quantize(Decimal("0.0001")))

def _company(
    root: Path, symbol: str, facts: dict[str, Any], attested: dict[str, Any]
) -> dict[str, Any]:
    pin = SOURCES[symbol]
    evidence = _original_receipt(root, facts, pin)
    if attested != evidence:
        raise AlphaContractError("P013 first NSE issuer byte-attestation drift")
    archive = root / evidence["original_archive_path"]
    try:
        raw = gzip.decompress(archive.read_bytes())
    except (OSError, FileNotFoundError) as exc:
        raise AlphaContractError("P013 original FY26 NSE cash archive absent") from exc
    if hashlib.sha256(raw).hexdigest() != pin["raw_sha256"]:
        raise AlphaContractError("P013 original NSE source SHA changed")
    rows = extract_exact_fy26_cells(raw, symbol)
    cfo = rows["cfo"]
    ni = rows["net_investing"]
    nf = rows["net_financing"]
    first = rows["cash_begin"]
    last = rows["cash_end"]
    net_change = cfo + ni + nf
    if net_change != rows["cash_change"] or first + net_change != last:
        raise AlphaContractError("P013 original cashflow sources do not reconcile")
    frozen = load_sources(root)[0]["new_fy26"]["numeric_facts"]
    old = next(x for x in frozen if x["symbol"] == symbol)
    if (
        rows["cfo"] != Decimal(str(old["operating_cfo"]))
        or rows["ppe_purchase"] != Decimal(str(old["ppe_purchase"]))
        or rows["interest_paid"] != Decimal(str(old["financing_interest_paid"]))
        or rows["lease_paid"] != Decimal(str(old["financing_lease_principal"]))
        or rows["cash_end"] != Decimal(str(old["cash_equivalents"]))
    ):
        raise AlphaContractError("P013 older FY26 source cash facts changed")
    row_values = {k: _crore(v) for k,v in rows.items()}
    if any(key not in row_values for key in FIELDS):
        raise AlphaContractError("P013 cashflow source lacks required fields")
    return {
        "symbol": symbol,
        "original_nse_isin": facts["isin"],
        "FY26_consolidated_period_end": END,
        "actual_original_nse_html_first_capture_utc": (
            evidence["first_verified_capture_utc"]
        ),
        "original_nse_full_html_sha256": evidence["original_nse_sha256"],
        "original_source_receipt_sha256": evidence["first_verified_receipt_sha256"],
        "original_source_path": evidence["original_archive_path"],
        "verified_original_cash_flow_cell_count": len(FIELDS),
        "original_values_in_inr_crore": row_values,
        "cashflow_after_all_investing_cr_not_owner_fcf": _crore(cfo + ni),
        "cashflow_after_investing_and_financing_cr_not_owner_fcf": (
            _crore(net_change)
        ),
        "source_CFO_less_PPE_cash_proxy_cr_not_owner_fcf": (
            _crore(cfo - rows["ppe_purchase"])
        ),
        "purchased_less_sold_financial_securities_cr_not_expense": (
            _crore(rows["investments_bought"] - rows["investments_sold"])
        ),
        "financing_lease_dividend_interest_paid_total_cr_not_recurring_FCF": (
            _crore(
                rows["lease_paid"] + rows["dividends_paid"]
                + rows["interest_paid"]
            )
        ),
        "selected_inventory_receivables_payables_cash_movement_cr_not_total_WC": (
            _crore(
                rows["change_in_inventory"]
                + rows["change_in_trade_receivables"]
                + rows["change_in_trade_payables"]
            )
        ),
        "cash_begin_to_end_reconciles_to_CFO_investing_financing": True,
        "corporate_actions_and_current_shares_verified": False,
        "investments_are_fully_distributable_cash": False,
        "financing_cashflow_equals_sustainable_owner_cash": False,
        "incremental_ROIC_and_maintenance_capex_verified": False,
        "probability_weighted_equity_value": None,
        "expected_3y_after_cost_share_return": None,
        "portfolio_eligible": False,
        "live_capital_allowed": False,
    }

def build_original_fy26_cash_use(root: Path) -> dict[str, Any]:
    attestation = build_original_attestation(root)
    if (
        attestation.get("issuer_byte_attestation_successful_count") != 3
        or attestation.get("historical_fiscal_period_end") != END
    ):
        raise AlphaContractError("P013 source FY26 attestation incomplete")
    source = load_sources(root)[0]["new_fy26"]
    old = {x["symbol"]: x for x in source["numeric_facts"]}
    attested = {
        x["symbol"]: x for x in attestation["original_nse_filing_sources"]
    }
    if set(old) != set(EXPECTED_LAKH) or set(attested) != set(EXPECTED_LAKH):
        raise AlphaContractError("P013 frozen three NSE source identities altered")
    records = [
        _company(root, symbol, old[symbol], attested[symbol])
        for symbol in sorted(EXPECTED_LAKH)
    ]
    report = {
        "schema_version": 1,
        "research_id": ID,
        "as_of_research_day": "2026-10-16",
        "issuer_financial_year_end": END,
        "archived_full_original_fy26_cashflow_source_count": 3,
        "individually_row_replayed_source_cash_fields": len(FIELDS) * 3,
        "original_three_source_attestation_sha256": (
            attestation["attestation_sha256"]
        ),
        "symbol_records": records,
        "all_three_cashflow_open_close_arithmetics_reconcile": True,
        "owner_cashflow_models_validated_count": 0,
        "current_parent_fully_diluted_and_balance_value_verified_count": 0,
        "repeatable_FY27_incremental_return_on_investment_verified_count": 0,
        "investable_company_count": 0,
        "all_equity_return_predictions_remain_null": True,
        "price_outcomes_opened_for_issuer_selection": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report

def verify_original_fy26_cash_use(
    report: dict[str, Any], *, root: Path
) -> None:
    unsigned = copy.deepcopy(report)
    sig = unsigned.pop("report_sha256", None)
    if sig != digest(unsigned):
        raise AlphaContractError("P013 source cash report signature changed")
    if report != build_original_fy26_cash_use(root):
        raise AlphaContractError("P013 source cash bridge fails original raw replay")
