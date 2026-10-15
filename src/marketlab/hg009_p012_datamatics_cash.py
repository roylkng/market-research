"""HG009 P012: original NSE Datamatics FY26 cash investing/debt bridge.

The FY26 board-result PDF was retained in HG009-P009 with immutable SHA and
real October 14 retrieval time. This work independently replays exact original
source page rows. It must never invent free cash flow, equity value or returns.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from marketlab.alpha import AlphaContractError, digest

ID = "HG009-P012-DATAMATICS-FY26-ORIGINAL-NSE-CASH-BRIDGE-v1"
ORIGINAL_SOURCE = Path(
    "research/hg009/p009-originals/DATAMATICS/"
    "f96ecf4e698b4ee311126479fa20de0e7021449efc50cffa28a069dde40e8c77.pdf.gz"
)
ORIGINAL_SHA = (
    "f96ecf4e698b4ee311126479fa20de0e7021449efc50cffa28a069dde40e8c77"
)
FIRST_RECEIPT = Path(
    "research/hg009/p009-originals/attempts/"
    "38625037535-1-DATAMATICS-FY26_AUDITED_CONSOLIDATED.json"
)
FIRST_RECEIPT_SHA = (
    "e414800f565fbcf2d1c391f2cb9258a4237edc5d47b41059bccf8772a5dc1efb"
)
SOURCE_URL = (
    "https://nsearchives.nseindia.com/corporate/"
    "DGSL_21052026190445_SEOutcomeUploaded.pdf"
)
P049 = Path("research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json")
P049_PINNED_GIT_BLOB = "706c2dd100a49859b5054323baeddc345531fb59"

# Original first-party FY26 consolidated cashflow column in INR crore,
# never standalone columns or FY25. All item labels are pinned to page 8,
# screenshot-verified 2026-10-15.
CASH_ROWS: dict[str, tuple[tuple[str, ...], str]] = {
    "fy26_cfo": (("net cash flow from operating activities",), "323.99"),
    "fy25_cfo": (("net cash flow from operating activities",), "223.72"),
    "fy26_cash_capex": (("purchase of fixed assets",), "(39.57)"),
    "fy25_cash_capex": (("purchase of fixed assets",), "(35.91)"),
    "fy26_acquisition_cash": (("investment in subsidiaries",), "(33.93)"),
    "fy26_net_investment_purchase": (("sale of investments",), "(262.76)"),
    "fy26_fixed_asset_sales": (("sale of fixed assets",), "1.03"),
    "fy26_dividend_received": (("dividend received from others",), "0.24"),
    "fy26_interest_received": (("interest received",), "18.45"),
    "fy26_net_investing": (("net cash flow used in investing",), "(316.54)"),
    "fy25_net_investing": (("net cash flow used in investing",), "(249.23)"),
    "fy26_new_long_borrowings": (("proceeds from long-term borrowings",), "33.59"),
    "fy26_net_short_borrowing_repayment": (
        ("short-term borrowings",), "(49.99)"
    ),
    "fy26_lease_payment": (("payment of lease liabilities",), "(23.98)"),
    "fy26_dividend_paid": (("dividend paid",), "(29.55)"),
    "fy26_interest_paid": (("interest paid",), "(13.74)"),
    "fy26_net_financing": (("net cash flow used in financing",), "(83.67)"),
    "fy25_net_financing": (("net cash flow used in financing",), "118.91"),
    "fy26_cash_change": (("net cash flow during the year",), "(76.22)"),
    "fy25_cash_change": (("net cash flow during the year",), "93.40"),
    "fy26_cash_beginning": (
        ("cash and cash equivalents at the beginning",), "217.64"
    ),
    "fy26_cash_ending": (
        ("net cash and cash equivalents at the end",), "141.42"
    ),
}
BALANCE_ROWS: dict[str, tuple[tuple[str, ...], str]] = {
    "fy26_cash_balance": (("cash and cash equivalents",), "141.42"),
    "fy26_noncurrent_investments": (("investments",), "228.77"),
    "fy26_current_investments": (("investments",), "410.13"),
    "fy26_noncurrent_borrowings": (("borrowings",), "86.62"),
    "fy26_current_borrowings": (("borrowings",), "54.74"),
    "fy26_noncurrent_lease": (("lease liabilities",), "46.77"),
    "fy26_current_lease": (("lease liabilities",), "32.80"),
    "fy26_goodwill": (("goodwill",), "611.12"),
}


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _original_receipt(root: Path) -> tuple[bytes, dict[str, Any]]:
    data = json.loads((root / FIRST_RECEIPT).read_text("utf-8"))
    unsigned = dict(data)
    signature = unsigned.pop("receipt_sha256", None)
    if (
        signature != FIRST_RECEIPT_SHA
        or signature != digest(unsigned)
        or data.get("original_issuer_publication_date") != "2026-05-21"
        or data.get("source_url") != SOURCE_URL
        or data.get("raw_sha256") != ORIGINAL_SHA
        or data.get("raw_repo_path") != str(ORIGINAL_SOURCE)
        or data.get("actual_retrieved_at_utc", "") < "2026-10-14"
        or data.get("raw_byte_count_if_downloaded") != 4068966
        or data.get("http_status") != 200
        or data.get("state")
        != "RAW_ARCHIVED_NOT_YET_FINANCIALLY_OR_IDENTITY_VALIDATED"
    ):
        raise AlphaContractError("P012 archived original NSE receipt changed")
    try:
        raw = gzip.decompress((root / ORIGINAL_SOURCE).read_bytes())
    except (FileNotFoundError, OSError) as exc:
        raise AlphaContractError("P012 archived original NSE FY26 PDF missing") from exc
    if len(raw) != 4068966 or hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA:
        raise AlphaContractError("P012 NSE original byte SHA/length drift")
    if not raw.startswith(b"%PDF"):
        raise AlphaContractError("P012 source no longer original PDF")
    return raw, data


def _normalize(line: str) -> str:
    return " ".join(line.casefold().split())


def check_row_tokens(
    extracted_page: str,
    rows: dict[str, tuple[tuple[str, ...], str]],
    *,
    source_label: str,
) -> list[str]:
    """Require row-level label + number, not numbers anywhere on PDF page."""
    lines = [_normalize(line) for line in extracted_page.splitlines()]
    matched = []
    for key, (labels, amount) in rows.items():
        if not any(
            any(label in line for label in labels)
            and amount.casefold() in line
            for line in lines
        ):
            raise AlphaContractError(
                f"P012 original {source_label} PDF row absent or ambiguous: {key}"
            )
        matched.append(key)
    return matched


def _pdf_replay(raw: bytes) -> tuple[list[str], list[str], int]:
    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = len(reader.pages)
        if pages != 23:
            raise AlphaContractError("P012 archived NSE board PDF page count drift")
        front = reader.pages[0].extract_text() or ""
        balance = reader.pages[6].extract_text(extraction_mode="layout") or ""
        cash = reader.pages[7].extract_text(extraction_mode="layout") or ""
    except (ValueError, IndexError, TypeError, OSError) as exc:
        raise AlphaContractError("P012 original NSE PDF unreadable") from exc
    if (
        "datamatics" not in front.casefold()
        or "may 21, 2026" not in front.casefold()
        or "consolidated" not in cash.casefold()
        or "consolidated" not in balance.casefold()
        or "cash flow statement" not in cash.casefold()
    ):
        raise AlphaContractError("P012 original issuer/period/page identity changed")
    return (
        check_row_tokens(cash, CASH_ROWS, source_label="cashflow"),
        check_row_tokens(balance, BALANCE_ROWS, source_label="balance sheet"),
        pages,
    )


def _cr(token: str) -> Decimal:
    neg = token.startswith("(") and token.endswith(")")
    cleaned = token.strip("()").replace(",", "")
    result = Decimal(cleaned)
    return -result if neg else result


def build_datamatics_original_cash_bridge(root: Path) -> dict[str, Any]:
    raw, receipt = _original_receipt(root)
    verified_cash, verified_balance, pages = _pdf_replay(raw)
    old_raw = (root / P049).read_bytes()
    if _blob(old_raw) != P049_PINNED_GIT_BLOB:
        raise AlphaContractError("P012 older Datamatics source changed")
    old = json.loads(old_raw)
    old_facts = old["fy26_historical_cash_and_balance_sheet_facts"]
    rows = {key: _cr(token) for key, (_, token) in CASH_ROWS.items()}
    bals = {key: _cr(token) for key, (_, token) in BALANCE_ROWS.items()}
    if (
        rows["fy26_cfo"] != Decimal(str(old_facts["fy26_cfo_inr_crore"]))
        or -rows["fy26_cash_capex"] != Decimal(
            str(old_facts["fy26_fixed_assets_capital_work_advances_cash_inr_crore"])
        )
        or bals["fy26_cash_balance"] != Decimal(
            str(old_facts["fy26_consolidated_cash_and_equivalents_inr_crore"])
        )
    ):
        raise AlphaContractError("P012 prior audited CFO/capex/cash reconciliation drift")
    investing_items = (
        rows["fy26_cash_capex"]
        + rows["fy26_fixed_asset_sales"]
        + rows["fy26_acquisition_cash"]
        + rows["fy26_net_investment_purchase"]
        + rows["fy26_dividend_received"]
        + rows["fy26_interest_received"]
    )
    financing_items = (
        rows["fy26_new_long_borrowings"]
        + rows["fy26_net_short_borrowing_repayment"]
        + rows["fy26_lease_payment"]
        + rows["fy26_dividend_paid"]
        + rows["fy26_interest_paid"]
    )
    after_investing = rows["fy26_cfo"] + rows["fy26_net_investing"]
    after_financing = after_investing + rows["fy26_net_financing"]
    if (
        investing_items != rows["fy26_net_investing"]
        or financing_items != rows["fy26_net_financing"]
        or after_financing != rows["fy26_cash_change"]
        or rows["fy26_cash_beginning"] + rows["fy26_cash_change"]
        != rows["fy26_cash_ending"]
        or rows["fy26_cash_ending"] != bals["fy26_cash_balance"]
    ):
        raise AlphaContractError("P012 original FY26 cash-flow waterfall inconsistent")
    revised = {
        "schema_version": 1,
        "analysis_id": ID,
        "analysis_date": "2026-10-15",
        "symbol": "DATAMATICS",
        "isin": "INE365B01017",
        "reporting_basis": "FY26_CONSOLIDATED_AUDITED_NOT_PARENT_OWNER_EARNINGS",
        "original_nse_report_url": SOURCE_URL,
        "original_report_date": "2026-05-21",
        "original_raw_repo_path": str(ORIGINAL_SOURCE),
        "original_raw_sha256": ORIGINAL_SHA,
        "pinned_receipt_path": str(FIRST_RECEIPT),
        "pinned_receipt_sha256": FIRST_RECEIPT_SHA,
        "receipt_actual_retrieved_at_utc": receipt["actual_retrieved_at_utc"],
        "original_pdf_page_count": pages,
        "page_zero_based_cashflow": 7,
        "page_zero_based_balance_sheet": 6,
        "exact_original_pdf_cashflow_row_labels_and_values_replayed": (
            verified_cash
        ),
        "exact_original_pdf_balance_row_labels_and_values_replayed": (
            verified_balance
        ),
        "original_cashflow_rows_in_cr": {
            key: float(amount) for key, amount in sorted(rows.items())
        },
        "original_balance_rows_in_cr": {
            key: float(amount) for key, amount in sorted(bals.items())
        },
        "fy26_operating_cash_cr": float(rows["fy26_cfo"]),
        "fy26_cfo_less_fixed_asset_cash_cr_not_owner_fcf": float(
            rows["fy26_cfo"] + rows["fy26_cash_capex"]
        ),
        "fy26_net_investing_cash_cr": float(rows["fy26_net_investing"]),
        "fy26_cfo_after_all_investing_cr_not_owner_fcf": float(after_investing),
        "fy26_net_financing_cash_cr": float(rows["fy26_net_financing"]),
        "fy26_annual_cash_change_cr": float(after_financing),
        "fy26_investment_purchase_net_cr_not_expense": float(
            -rows["fy26_net_investment_purchase"]
        ),
        "fy26_acquisition_cash_outflow_cr": float(
            -rows["fy26_acquisition_cash"]
        ),
        "fy26_lease_principal_paid_cr": float(-rows["fy26_lease_payment"]),
        "fy26_interest_paid_cr": float(-rows["fy26_interest_paid"]),
        "fy26_dividend_paid_cr": float(-rows["fy26_dividend_paid"]),
        "fy26_current_plus_noncurrent_investments_cr_not_unrestricted": float(
            bals["fy26_current_investments"]
            + bals["fy26_noncurrent_investments"]
        ),
        "fy26_reported_borrowings_total_cr": float(
            bals["fy26_current_borrowings"]
            + bals["fy26_noncurrent_borrowings"]
        ),
        "fy26_lease_liability_total_cr": float(
            bals["fy26_current_lease"]
            + bals["fy26_noncurrent_lease"]
        ),
        "fy26_goodwill_cr": float(bals["fy26_goodwill"]),
        "investment_purchase_is_not_a_cost_of_goods_or_permanent_cash_loss": True,
        "cash_residual_is_not_sustainable_earnings": True,
        "financial_investments_unrestricted_or_distributable_verified": False,
        "working_capital_through_cycle_verified": False,
        "acquisition_goodwill_and_subsidiary_cash_reconciled": False,
        "latest_fully_diluted_share_count_verified": False,
        "current_stock_price_or_total_return_estimated": False,
        "probability_weighted_shareholder_value_cr": None,
        "expected_net_one_or_three_year_return": None,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    revised["report_sha256"] = digest(revised)
    return revised


def validate_datamatics_original_cash_bridge(
    value: dict[str, Any], *, root: Path
) -> None:
    unsigned = copy.deepcopy(value)
    stored = unsigned.pop("report_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P012 cash research packet hash changed")
    if build_datamatics_original_cash_bridge(root) != value:
        raise AlphaContractError("P012 original archived PDF replay differs")
