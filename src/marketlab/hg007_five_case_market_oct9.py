"""Official 9 Oct 2026 five-case price context, not investable returns.

Each output is derived from the *same original NSE CM UDiFF ZIP* that
underpinned the previously source-sealed SS002-P007 October 9 eight-company
panel. Original five HG005 payoff cases and P033 underwriting readiness
are immutable. No selection, revaluation, post-event inference, pricing
forecast, or investment trading is performed.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.marketdata import udiff_url

CASE_ID = "HG007-P034-2026-10-09-FIVE-CASE-OFFICIAL-EQ-PRICE-CONTEXT-v1"
SOURCE_DAY = "2026-10-09"
SOURCE_URL = udiff_url(date.fromisoformat(SOURCE_DAY))
EXPECTED_NAMES = ("ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV")
SOURCES = {
    "HG005": (
        "research/hg005-d001-result-v1.json",
        "2dbbc3055d1aacec8a37dd510a1a75a3c7868006",
    ),
    "SS002_P007": (
        "research/ss002-p007-result-v1.json",
        "ac8384ea4dfc2642411881165a3255e2553dd6fb",
    ),
    "HG007_P033": (
        "research/hg007/hg007-p033-five-case-sambhv-source-timing-v1.json",
        "3b0caf8f0fa763528d5b37b218935f848c9f100a",
    ),
}
PINNED_ORIGINAL_NSE_SHA256 = (
    "8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c"
)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("source capture timestamp must be an offset-aware ISO string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid source UTC timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("source capture timestamp must include timezone")
    return parsed.astimezone(UTC)


def load_frozen_five_sources(root: Path) -> tuple[dict, dict, dict, dict]:
    cases = {}
    receipts = {}
    for label, (name, git_blob) in SOURCES.items():
        raw = (root / name).read_bytes()
        if _git_blob(raw) != git_blob:
            raise ValueError(f"{label}: original research source Git blob changed")
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise TypeError(f"{label}: original source is not a JSON object")
        if obj.get("live_capital_allowed") is not False:
            raise ValueError(f"{label}: original source cannot enable capital")
        cases[label] = obj
        receipts[label] = {
            "path": name,
            "git_blob_sha": git_blob,
            "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    hg005 = cases["HG005"]
    ss002 = cases["SS002_P007"]
    p033 = cases["HG007_P033"]
    if (
        hg005.get("price_session") != "2026-10-01"
        or hg005.get("context_id") != "HG005-D001-v1"
        or tuple(hg005.get("symbols", ())) != EXPECTED_NAMES
        or set(hg005.get("key_mechanical_context", {})) != set(EXPECTED_NAMES)
    ):
        raise ValueError("frozen original HG005 five-case cohort changed")
    if (
        ss002.get("diagnostic_id") != "SS002-P007-v1"
        or ss002.get("price_session") != SOURCE_DAY
        or ss002.get("official_bhavcopy_sha256") != PINNED_ORIGINAL_NSE_SHA256
        or ss002.get("expected_returns_calculated") is not False
        or ss002.get("share_action_clearance_proven") is not False
    ):
        raise ValueError("SS002-P007 original October 9 NSE price source changed")
    if (
        p033.get("overlay_id") != "HG007-P033-FIVE-CASE-UNDERWRITING-LATEST-SAMBHV-v1"
        or p033.get("as_of_ist") != "2026-10-11"
        or p033.get("original_five_case_count") != 5
        or tuple(x.get("symbol") for x in p033.get("casework", ())) != EXPECTED_NAMES
        or p033.get("source_probabilities_or_expected_returns_published") != 0
    ):
        raise ValueError("current five-case underwriting source membership changed")
    return hg005, ss002, p033, receipts


def build_five_case_price_context(
    hg005: dict[str, Any],
    ss002: dict[str, Any],
    p033: dict[str, Any],
    *,
    udiff_raw: bytes,
    captured_at_utc: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    recorded = _utc(captured_at_utc)
    if recorded < datetime.fromisoformat("2026-10-09T10:00:00Z"):
        raise ValueError("original Oct 9 official NSE data cannot predate session close")
    if not isinstance(udiff_raw, bytes) or not udiff_raw:
        raise ValueError("official original NSE UDiFF ZIP missing")
    actual_digest = hashlib.sha256(udiff_raw).hexdigest()
    if actual_digest != ss002.get("official_bhavcopy_sha256"):
        raise ValueError("Oct 9 UDiFF original bytes differ from source-sealed SS002-P007")
    panel = parse_udiff_eq_panel(udiff_raw, session_date=date(2026, 10, 9))
    picked: dict[str, Any] = {}
    for record in panel:
        if record.symbol not in EXPECTED_NAMES:
            continue
        if record.symbol in picked:
            raise ValueError(f"ambiguous official EQ symbol/ISIN row for {record.symbol}")
        picked[record.symbol] = record
    if set(picked) != set(EXPECTED_NAMES):
        raise ValueError(
            "original NSE 9 Oct full market UDiFF missing original five-case symbols"
        )
    for symbol in ("INOXGREEN", "SAMBHV"):
        if not math.isclose(
            picked[symbol].close_price,
            ss002["case_prices_inr"][symbol],
            rel_tol=0.0,
            abs_tol=1e-8,
        ):
            raise ValueError(f"{symbol}: NSE official close differs from original P007 panel")

    frozen = hg005.get("key_mechanical_context")
    if not isinstance(frozen, dict):
        raise TypeError("HG005 historical market context unavailable")
    result_rows = []
    for symbol in EXPECTED_NAMES:
        bar = picked[symbol]
        legacy = frozen[symbol]
        prior_close = legacy.get("close_price_inr")
        older_cap = legacy.get("reported_fd_market_cap_inr_crore")
        if any(
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value <= 0
            for value in (prior_close, older_cap)
        ):
            raise ValueError(f"{symbol}: invalid original October 1 historical context")
        result_rows.append({
            "symbol": symbol,
            "official_nse_eq_isin_observed": bar.isin,
            "symbol_to_prior_issuer_isin_independently_bound": False,
            "observed_source_date": SOURCE_DAY,
            "source_original_zip_sha256": actual_digest,
            "official_oct9_open_inr": bar.open_price,
            "official_oct9_high_inr": bar.high_price,
            "official_oct9_low_inr": bar.low_price,
            "official_oct9_close_inr": bar.close_price,
            "official_oct9_total_traded_shares": bar.volume,
            "official_oct9_total_traded_value_inr": bar.turnover_inr,
            "official_oct9_number_of_executed_transactions": bar.trade_count,
            "frozen_hg005_oct1_close_inr_not_current": prior_close,
            "frozen_hg005_oct1_reported_fd_cap_inr_crore_not_current": older_cap,
            "oct1_to_oct9_unadjusted_price_reference_change_pct": (
                100.0 * (bar.close_price / prior_close - 1.0)
            ),
            "company_current_fully_diluted_share_count_verified": False,
            "company_oct9_adjusted_enterprise_value_computed": False,
            "share_action_dividend_adjusted_total_return_computed": False,
            "price_a_tradable_close_fill": False,
            "independent_share_identity_review_complete": False,
            "probability_weighted_expected_return_calculated": False,
        })
    return {
        "schema_version": 1,
        "price_context_id": CASE_ID,
        "classification": "SOURCE_VERIFIED_OCT9_EQ_CONTEXT_NOT_RETURN_OR_FD_VALUATION",
        "original_price_session": "2026-10-01",
        "new_official_reference_price_session": SOURCE_DAY,
        "captured_at_utc": recorded.isoformat().replace("+00:00", "Z"),
        "source_original_url": SOURCE_URL,
        "source_original_zip_sha256": actual_digest,
        "original_full_market_eq_row_count": len(panel),
        "source_git_blob_receipts": provenance,
        "original_hg005_five_case_selection_unchanged": True,
        "original_p033_latest_underwriting_status_unchanged": True,
        "five_case_count": 5,
        "price_context_rows": result_rows,
        "stock_current_fd_capital_approved": False,
        "corporate_action_share_identity_approved": False,
        "NIFTY500_benchmark_excess_return_calculated": False,
        "expected_returns_calculated": False,
        "company_completion_probabilities_published": 0,
        "investment_recommendations_created": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def validate_five_case_price_context(result: dict[str, Any]) -> None:
    if (
        result.get("price_context_id") != CASE_ID
        or result.get("source_original_zip_sha256") != PINNED_ORIGINAL_NSE_SHA256
        or result.get("new_official_reference_price_session") != SOURCE_DAY
        or result.get("five_case_count") != 5
        or tuple(row["symbol"] for row in result.get("price_context_rows", ())) != EXPECTED_NAMES
    ):
        raise ValueError("not a source-approved five-case NSE Oct9 price context")
    for flag in (
        "stock_current_fd_capital_approved",
        "corporate_action_share_identity_approved",
        "NIFTY500_benchmark_excess_return_calculated",
        "expected_returns_calculated",
        "investment_recommendations_created",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if result.get(flag) is not False:
            raise ValueError(f"market-context diagnostic may not authorize {flag}")
