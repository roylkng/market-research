"""HG009 P010: independently replay MAYURUNIQ FY26 cash-use statement.

Uses one pinned original NSE HTML *byte version* and its signed actual
retrieval receipt. Other versions are not silently substituted. Reported
long-term asset flows may be recoverable deposits/investments, so the
arithmetic cash residual is emphatically NOT normalized owner FCF.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p009_originals import source_specifications

ANALYSIS_ID = "HG009-P010-MAYUR-FY26-INVESTING-CASH-BRIDGE-v1"
SYMBOL = "MAYURUNIQ"
ISIN = "INE040D01038"
PERIOD_END = "2026-03-31"
FIRST_RETAINED_RECEIPT = (
    "research/hg009/p009-originals/attempts/"
    "38624670429-1-MAYURUNIQ-FY26_AUDITED_CONSOLIDATED.json"
)
SOURCE_RAW_SHA256 = (
    "e75e5e60976e25f2573904883784598a027d506ca64414f2b04e5ee003def85b"
)
SOURCE_RAW = (
    "research/hg009/p009-originals/MAYURUNIQ/"
    + SOURCE_RAW_SHA256 + ".html.gz"
)
PINNED_RECEIPT_SHA256 = (
    "9b43c059256ddce5513d7a94236bcf9c0f40a4342b8deb5c13cc3faddbb3eb44"
)

# Exactly the original FY26 consolidated reported INR-lakh cells.
# These are auditable financial statement rows, not an owner-cash definition.
CASH_ROWS_LAKH: dict[str, tuple[str, str]] = {
    "pretax_profit": ("Profit before tax", "25,898.23"),
    "net_operating_cash": (
        "Net cash flows from (used in) operating activities", "13,315.27"
    ),
    "ppe_cash_purchase": ("Purchase of property, plant and equipment", "2,420.71"),
    "other_long_asset_purchase": (
        "Purchase of other long-term assets", "26,624.41"
    ),
    "other_long_asset_sale_proceeds": (
        "Proceeds from sales of other long-term assets", "16,038.42"
    ),
    "net_investing_cash": (
        "Net cash flows from (used in) investing activities", "(11,504.71)"
    ),
    "net_financing_cash": (
        "Net cash flows from (used in) financing activities", "(2,377.29)"
    ),
    "dividends_paid": ("Dividends paid", "2,170.70"),
    "interest_paid_financing": ("Interest paid", "81.29"),
    "net_cash_change_before_fx": (
        (
            "Net increase (decrease) in cash and cash equivalents "
            "before effect of exchange rate changes"
        ),
        "(566.73)",
    ),
    "exchange_effect_on_cash": (
        "Effect of exchange rate changes on cash and cash equivalents", "170.20"
    ),
    "net_cash_change_after_fx": (
        "Net increase (decrease) in cash and cash equivalents", "(396.53)"
    ),
    "cash_beginning": (
        "Cash and cash equivalents cash flow statement at beginning of period",
        "8,310.03"
    ),
    "cash_end": (
        "Cash and cash equivalents cash flow statement at end of period",
        "7,913.50"
    ),
}
OTHER_ASSET_BALANCE_ROWS = {
    "current_investments": ("Current investments", "17,687.23"),
    "noncurrent_investments": ("Non-current investments", "10,807.28"),
    "noncurrent_long_deposits": (
        "Deposits with more than 12 months maturity as at reporting date",
        "7,355.00"
    ),
}


def _money(value: str) -> Decimal:
    data = value.strip()
    neg = data.startswith("(") and data.endswith(")")
    number = data[1:-1] if neg else data
    try:
        result = Decimal(number.replace(",", ""))
    except ArithmeticError as exc:
        raise AlphaContractError("P010 unparseable original cash amount") from exc
    return -result if neg else result


def _cr(value: Decimal) -> float:
    return float((value / Decimal(100)).quantize(Decimal("0.0001")))


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def extract_original_financial_rows(
    raw: bytes, *,
    expected_cash: dict[str, tuple[str, str]] = CASH_ROWS_LAKH,
    expected_balance: dict[str, tuple[str, str]] = OTHER_ASSET_BALANCE_ROWS,
) -> dict[str, Decimal]:
    if not raw or len(raw) > 2_000_000:
        raise AlphaContractError("P010 invalid original NSE issuer size")
    soup = BeautifulSoup(raw, "html.parser")
    document = _normalize(soup.get_text(" ", strip=True))
    for text in ("mayuruniq", ISIN.casefold(), "31-03-2026",
                 "consolidated", "audited"):
        if text not in document:
            raise AlphaContractError(f"P010 issuer/period mismatch: {text}")
    source_rows = [
        _normalize(tr.get_text(" ", strip=True))
        for tr in soup.find_all("tr")
    ]
    if len(source_rows) < 25:
        raise AlphaContractError("P010 incomplete NSE original tabular document")
    amounts: dict[str, Decimal] = {}
    for name, (label, reported) in {
        **expected_cash, **expected_balance
    }.items():
        target = _normalize(label)
        expected_token = reported.casefold()
        # Match a financial fact in a single table row, never an arbitrary
        # occurrence somewhere on a page. Allow multiple same-value audited
        # rows but reject missing amount or mismatched financial basis.
        matches = [
            line for line in source_rows
            if target in line and expected_token in line
        ]
        if not matches:
            raise AlphaContractError(
                f"P010 expected row/amount absent in archived issuer: {name}"
            )
        amounts[name] = _money(reported)
    return amounts


def _original_bytes(root: Path) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    original = next(
        (
            x for x in source_specifications(root)
            if x["symbol"] == SYMBOL
            and x["accounting_period"] == "FY26_AUDITED_CONSOLIDATED"
        ),
        None,
    )
    if original is None or original["isin"] != ISIN:
        raise AlphaContractError("P010 original registrar symbol/ISIN mismatch")
    receipt = json.loads((root / FIRST_RETAINED_RECEIPT).read_text("utf-8"))
    unsigned = copy.deepcopy(receipt)
    signature = unsigned.pop("receipt_sha256", None)
    if (
        signature != PINNED_RECEIPT_SHA256
        or signature != digest(unsigned)
        or receipt.get("source_url") != original["source_url"]
        or receipt.get("raw_sha256") != SOURCE_RAW_SHA256
        or receipt.get("raw_repo_path") != SOURCE_RAW
        or receipt.get("state") != "RAW_ARCHIVED_NOT_YET_FINANCIALLY_OR_IDENTITY_VALIDATED"
        or receipt.get("http_status") != 200
        or receipt.get("cashflow_values_reconciled_to_original_bytes") is not False
        or receipt.get("issuer_and_period_content_verified") is not False
        or receipt.get("actual_retrieved_at_utc", "") <
        original["original_issuer_publication_date"]
    ):
        raise AlphaContractError("P010 original first accepted source receipt drift")
    try:
        raw = gzip.decompress((root / SOURCE_RAW).read_bytes())
    except (FileNotFoundError, OSError) as exc:
        raise AlphaContractError("P010 original NSE source bytes unreadable") from exc
    # The first P009 acquisition used v1 receipt fields and did not retain a
    # byte-count field. Its content SHA and signed receipt *are* immutable.
    # Do not invent a retrospective count in the original receipt.
    old_count = receipt.get("raw_byte_count_if_downloaded")
    if (
        hashlib.sha256(raw).hexdigest() != SOURCE_RAW_SHA256
        or (old_count is not None and len(raw) != old_count)
    ):
        raise AlphaContractError("P010 archived NSE issuer bytes changed")
    return raw, receipt, original


def build_mayur_cash_use_bridge(root: Path) -> dict[str, Any]:
    raw, receipt, original = _original_bytes(root)
    rows = extract_original_financial_rows(raw)
    cfo = rows["net_operating_cash"]
    ppe = rows["ppe_cash_purchase"]
    asset_net = (
        rows["other_long_asset_purchase"] - rows["other_long_asset_sale_proceeds"]
    )
    residual = cfo - ppe - asset_net
    after_investing = cfo + rows["net_investing_cash"]
    after_financing = after_investing + rows["net_financing_cash"]
    if (
        after_financing != rows["net_cash_change_before_fx"]
        or after_financing + rows["exchange_effect_on_cash"]
        != rows["net_cash_change_after_fx"]
        or rows["cash_beginning"] + rows["net_cash_change_after_fx"]
        != rows["cash_end"]
        or residual != Decimal("308.57")
    ):
        raise AlphaContractError("P010 original cashflow arithmetic fails reconciliation")
    other_assets = {
        key: _cr(rows[key]) for key in OTHER_ASSET_BALANCE_ROWS
    }
    result: dict[str, Any] = {
        "schema_version": 1,
        "analysis_id": ANALYSIS_ID,
        "analysis_date": "2026-10-15",
        "company_symbol": SYMBOL,
        "company_isin": ISIN,
        "original_exchange_document_url": original["source_url"],
        "original_period_end": PERIOD_END,
        "reporting_basis": "FY26_CONSOLIDATED_AUDITED_NOT_OWNER_EARNINGS",
        "pinned_first_retained_retrieval_receipt": FIRST_RETAINED_RECEIPT,
        "pinned_first_retained_retrieval_utc": receipt["actual_retrieved_at_utc"],
        "pinned_original_byte_sha256": SOURCE_RAW_SHA256,
        "pinned_original_byte_path": SOURCE_RAW,
        "number_of_source_row_values_matched": len(rows),
        "verified_original_source_rows_in_lakh": {
            name: float(value) for name, value in sorted(rows.items())
        },
        "source_row_value_provenance": {
            name: {"label": label, "original_value": value}
            for name, (label, value) in sorted({
                **CASH_ROWS_LAKH, **OTHER_ASSET_BALANCE_ROWS
            }.items())
        },
        "fy26_cfo_cr": _cr(cfo),
        "fy26_ppe_cash_purchase_cr": _cr(ppe),
        "fy26_cfo_less_ppe_cr_not_fcf": _cr(cfo - ppe),
        "other_long_term_assets_purchase_cr": _cr(rows["other_long_asset_purchase"]),
        "other_long_term_assets_proceeds_cr": _cr(
            rows["other_long_asset_sale_proceeds"]
        ),
        "other_long_term_assets_net_cash_placement_cr": _cr(asset_net),
        "residual_cfo_less_ppe_less_net_asset_placement_cr_not_owner_fcf": (
            _cr(residual)
        ),
        "fy26_cash_after_all_investing_cr": _cr(after_investing),
        "fy26_cash_after_all_investing_and_financing_before_fx_cr": (
            _cr(after_financing)
        ),
        "reported_cash_fx_effect_cr": _cr(rows["exchange_effect_on_cash"]),
        "reported_change_cash_after_fx_cr": _cr(rows["net_cash_change_after_fx"]),
        "cashflow_beginning_cash_cr": _cr(rows["cash_beginning"]),
        "cashflow_ending_cash_cr": _cr(rows["cash_end"]),
        "original_balance_sheet_investments_and_deposits_cr": other_assets,
        "other_long_term_asset_placement_is_an_irreversible_expense": False,
        "asset_buy_and_sell_proceeds_are_full_bank_reconciliation": False,
        "reported_residual_is_normalized_owner_free_cash": False,
        "restricted_vs_unrestricted_investments_verified": False,
        "future_cash_return_from_long_term_asset_purchases_established": False,
        "receivables_and_inventory_multi_year_reversal_verified": False,
        "balance_sheet_asset_note_crosswalk_verified": False,
        "current_equity_share_capital_and_dilution_verified": False,
        "source_has_any_prospective_equity_price_or_return": False,
        "investor_valuation_ready": False,
        "expected_return": None,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def validate_mayur_cash_use_bridge(value: dict, root: Path) -> None:
    unsigned = copy.deepcopy(value)
    signature = unsigned.pop("report_sha256", None)
    if signature != digest(unsigned):
        raise AlphaContractError("P010 cash bridge report hash mismatch")
    if value != build_mayur_cash_use_bridge(root):
        raise AlphaContractError("P010 report no longer replays original NSE source")
