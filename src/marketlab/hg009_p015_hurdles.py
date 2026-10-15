"""HG009 P015: ACE/ACUTAAS dated reverse owner-cash hurdles, not targets.

Reference NSE Q1 FY27 original parent share capital and actual October 15
original EQ closes against audited FY26 consolidated operating cashflows.
It is NOT a current fully diluted equity value or a forecast that a chosen
terminal cash multiple will occur.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_daily import validate_hg009_daily_snapshot

REPORT_ID = "HG009-P015-20261016-ACE-ACUTAAS-REVERSE-CASH-HURDLES-v1"
SOURCE_MAP = {
    "audited": (
        "research/hg009/hg009-p013-fy26-cash-use-bridge-v1.json",
        "2b2891b1d5c38a570bd492b4eb822fabf9fd9f36",
        "report_sha256",
    ),
    "equity": (
        "registry/hg009_p015_ace_acutaas_q1_sources.json",
        "eab274ece7d40e65cf1cb69db7632c1e92206f69",
        None,
    ),
    "market": (
        "research/hg009/daily/2026-10-15-v1.json",
        "187fa19e8c2e8384dfc82b1fc3814e4768f0644e",
        "packet_sha256",
    ),
}
SYMBOLS = ("ACE", "ACUTAAS")
MULTIPLES = (12, 16, 20)
UPLIFT_50_PCT = 1.5
THREE_YEAR_50_PCT_PER_YEAR = 1.5 ** 3


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _amount(x: Any, label: str) -> float:
    if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
        raise AlphaContractError(f"P015 invalid financial amount: {label}")
    return float(x)


def load_sources(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    result, receipts = {}, {}
    for key, (path, original_blob, signature) in SOURCE_MAP.items():
        original = (root / path).read_bytes()
        if _blob(original) != original_blob:
            raise AlphaContractError(f"P015 original NSE packet drift: {key}")
        obj = json.loads(original)
        if not isinstance(obj, dict):
            raise AlphaContractError("P015 original source must be an object")
        if signature is not None:
            unsigned = copy.deepcopy(obj)
            sealed = unsigned.pop(signature, None)
            if sealed != digest(unsigned):
                raise AlphaContractError(f"P015 signed source invalid: {key}")
        result[key] = obj
        receipts[key] = {
            "path": path, "original_git_blob": original_blob,
            "raw_json_sha256": hashlib.sha256(original).hexdigest(),
        }
    validate_hg009_daily_snapshot(result["market"])
    if result["market"].get("date_ist") != "2026-10-15":
        raise AlphaContractError("P015 Oct15 original market day changed")
    if (
        result["equity"].get("retained_original_HTML_bytes") is not False
        or result["equity"].get("raw_source_validation_pending") is not True
    ):
        raise AlphaContractError("P015 manual source cannot self-authorize receipt")
    return result, receipts


def build_reverse_cash_hurdles(
    originals: dict[str, dict], receipts: dict[str, dict]
) -> dict:
    # Fail closed even when a caller alters source objects after reading their
    # original Git blob. Keep every one of the 300 market identities protected.
    for key in ("audited", "market"):
        source = copy.deepcopy(originals[key])
        sha_key = SOURCE_MAP[key][2]
        sealed = source.pop(sha_key, None)
        if sealed != digest(source):
            raise AlphaContractError(f"P015 original signed source drift: {key}")
    validate_hg009_daily_snapshot(originals["market"])
    if originals["market"].get("date_ist") != "2026-10-15":
        raise AlphaContractError("P015 incorrect source-market observation date")
    if originals["equity"].get("retained_original_HTML_bytes") is not False:
        raise AlphaContractError("P015 cannot claim unarchived Q1 issuer evidence")
    if len(originals["market"]["source_identity_rows"]) != 300:
        raise AlphaContractError("P015 original market identity denominator changed")
    bank = {
        x["symbol"]: x for x in originals["audited"]["symbol_records"]
    }
    parent = {
        x["symbol"]: x for x in originals["equity"]["issuer_rows"]
    }
    market = {
        (x["symbol"], x["frozen_isin"]): x
        for x in originals["market"]["source_identity_rows"]
    }
    if set(parent) != set(SYMBOLS) or not set(parent).issubset(bank):
        raise AlphaContractError("P015 original fixed listed company names changed")
    records = []
    for symbol in SYMBOLS:
        p = parent[symbol]
        a = bank[symbol]
        q = market.get((symbol, p["isin"]))
        if not q or q["state"] != "ORIGINAL_NSE_EQ_OHLC_OBSERVED_NOT_FILL":
            raise AlphaContractError(f"P015 original Oct15 {symbol} EQ not priceable")
        if (
            p["accounting_basis"] != "STANDALONE_UNAUDITED_Q1FY27"
            or p["period_end"] != "2026-06-30"
            or a["FY26_consolidated_period_end"] != "2026-03-31"
            or a["original_nse_isin"] != p["isin"]
            or not p["original_url"].startswith(
                "https://nsearchives.nseindia.com/corporate/ixbrl/"
            )
        ):
            raise AlphaContractError("P015 mixed source/ISIN/period evidence")
        cells = p["amounts_in_lakh"]
        for name in (
            "paid_up_equity_capital", "face_value_per_share_inr",
            "revenue", "other_income", "pbt", "pat",
        ):
            _amount(cells[name], name)
        face = cells["face_value_per_share_inr"]
        if face <= 0:
            raise AlphaContractError("P015 zero face value")
        shares_crore = cells["paid_up_equity_capital"] / face / 100
        price = _amount(q["ohlcv"]["close_inr"], "Oct15 NSE close")
        if price <= 0:
            raise AlphaContractError("P015 original market price must be positive")
        capitalization = shares_crore * price
        cfo = _amount(a["original_values_in_inr_crore"]["cfo"], "FY26 CFO")
        ppe = _amount(a["original_values_in_inr_crore"]["ppe_purchase"], "FY26 PPE")
        proxy = cfo - ppe
        if not math.isclose(
            proxy, a["source_CFO_less_PPE_cash_proxy_cr_not_owner_fcf"],
            abs_tol=0.00011, rel_tol=0,
        ):
            raise AlphaContractError("P015 CFO-to-PPE original source conflict")
        quarter_pbt = cells["pbt"] / 100
        other = cells["other_income"] / 100
        if quarter_pbt <= 0 or other > quarter_pbt:
            raise AlphaContractError("P015 original other income invalid")
        records.append({
            "symbol": symbol,
            "original_isin": p["isin"],
            "original_nse_q1_filing": p["original_url"],
            "reporting_basis": p["accounting_basis"],
            "reported_share_capital_period": "2026-06-30",
            "dated_market_price_period": "2026-10-15",
            "dated_price_EQ_close_inr": round(price, 4),
            "reported_June_basic_shares_crore_not_Oct_diluted": round(
                shares_crore, 7
            ),
            "cross_date_illustrative_basic_market_cap_cr": round(
                capitalization, 2
            ),
            "q1_standalone_reported_PBT_cr": round(quarter_pbt, 4),
            "q1_standalone_other_income_cr": round(other, 4),
            "other_income_as_percent_of_Q1_standalone_PBT": round(
                100 * other / quarter_pbt, 2
            ),
            "q1_PBT_less_other_income_not_owner_earnings_cr": round(
                quarter_pbt - other, 4
            ),
            "fy26_CONSOLIDATED_CFO_cr": round(cfo, 4),
            "fy26_CONSOLIDATED_PPE_cash_spend_cr": round(ppe, 4),
            "fy26_CFO_less_PPE_cr_not_owner_FCF": round(proxy, 4),
            "CFO_yield_on_cross_date_basic_cap_pct_not_owner_yield": round(
                100 * cfo / capitalization, 3
            ),
            "CFO_less_PPE_yield_pct_not_owner_yield": round(
                100 * proxy / capitalization, 3
            ),
            "cross_date_cap_to_FY26_CFO_less_PPE_if_positive": (
                round(capitalization / proxy, 3) if proxy > 0 else None
            ),
            "reverse_cash_at_12x_16x_20x_unadjusted_market_cap_cr": {
                str(multiple): round(capitalization / multiple, 2)
                for multiple in MULTIPLES
            },
            "reverse_cash_for_50pct_ONE_TIME_gross_price_lift_at_16x_cr": (
                round(capitalization * UPLIFT_50_PCT / 16, 2)
            ),
            "reverse_cash_for_50pct_CAGR_3Y_at_16x_cr": (
                round(capitalization * THREE_YEAR_50_PCT_PER_YEAR / 16, 2)
            ),
            "these_multiples_are_unsupported_assumptions": True,
            "future_50pct_return_is_probable": False,
            "investment_assets_and_financing_not_adjusted": True,
            "fiscal_period_mismatch_fy26_consolidated_vs_q1_standalone": True,
            "issuer_q1_raw_HTML_retained_and_replayed": False,
            "current_fully_diluted_shares_verified": False,
            "share_action_benchmark_and_transaction_costs_normalized": False,
            "current_owner_cash_equity_value_validated": False,
            "future_price_target_inr": None,
            "expected_1y_or_3y_net_return": None,
            "capital_eligible": False,
        })
    result = {
        "schema_version": 1,
        "review_id": REPORT_ID,
        "review_date": "2026-10-16",
        "prior_original_source_receipts": receipts,
        "fixed_companies": list(SYMBOLS),
        "analysis_is_original_Q1_company_vs_dated_Oct15_price": True,
        "published_after_first_market_outcome_not_first_day_preregistration": True,
        "two_case_records": records,
        "realizable_equity_valuations_complete": 0,
        "confidence_in_future_50pct_returns_established": False,
        "investment_price_targets_created": 0,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = digest(result)
    return result


def materialize(root: Path) -> dict:
    documents, receipts = load_sources(root)
    return build_reverse_cash_hurdles(documents, receipts)


def validate_result(result: dict[str, Any], root: Path) -> None:
    unsigned = copy.deepcopy(result)
    sig = unsigned.pop("packet_sha256", None)
    if sig != digest(unsigned):
        raise AlphaContractError("P015 signed original cash hurdle review changed")
    if result != materialize(root):
        raise AlphaContractError("P015 source-bound reverse hurdle not reproducible")
