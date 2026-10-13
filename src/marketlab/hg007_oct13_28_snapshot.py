"""Official 13 Oct NSE market-source snapshot for all 28 frozen HG002 cases.

Reuse the exact H021 full-market NSE UDiFF already obtained. Preserve the
28 names and their latest source-backed October-9 Vibhav stage. Distinguish
the EQ series from BE or an absent identity, and never infer fill capacity,
returns, corporate-action adjustment, or a new stock-selection ranking.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

from marketlab.alpha_market import DailyEquityObservation, parse_udiff_eq_panel
from marketlab.hg007_28_liquidity import _valid_bar, validate_twenty_day_all_28
from marketlab.hg007_eq_absence_review import _original_full_market_rows
from marketlab.h021_daily_prices import validate_daily_source_observation
from marketlab.marketdata import index_snapshot_url, udiff_url

AUDIT_ID = "HG007-P047-2026-10-13-28-CASE-OFFICIAL-NSE-SOURCE-v1"
DAY = "2026-10-13"
RAW_NSE_SHA256 = "b3aba7f1e20587e4c77a5de2b720cbcd5d8f4c8fe42e1b67f06f0d7deaabbf46"
INR_CRORE = 10_000_000
SOURCES = {
    "current_day_p008": (
        "research/prospective/h021/daily-prices/2026-10-13-v1.json",
        "a0aad217d171313426e00af6d234d5df02a45395",
    ),
    "historical_p041": (
        "research/hg007/twenty-session-liquidity/twenty-session-28-stock-v1.json",
        "a01b9823a29cdfe94f5e2f21e84159b66a949c75",
    ),
    "latest_stage_p046": (
        "research/hg007/hg007-p046-28-case-vibhav-conversion-stage-v1.json",
        "5a2ff4ad542d39a4d75c0cd2d2ab14072d270d40",
    ),
}
RAW_PATH = Path(
    "research/prospective/h021/daily-prices/raw/sha256/"
    + RAW_NSE_SHA256 + ".zip"
)


def _git_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _canonical_hash(packet: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            packet, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _read_sources(
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], bytes, dict[str, dict]]:
    sources = {}
    receipts = {}
    for name, (path, expected_blob) in SOURCES.items():
        raw = (repo_root / path).read_bytes()
        actual = _git_sha(raw)
        if actual != expected_blob:
            raise ValueError(f"{name}: original Git blob changed; do not backfill")
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise TypeError(f"{name}: source must be a JSON mapping")
        sources[name] = obj
        receipts[name] = {
            "path": path, "git_blob_sha": actual,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
        }
    raw_nse = (repo_root / RAW_PATH).read_bytes()
    if hashlib.sha256(raw_nse).hexdigest() != RAW_NSE_SHA256:
        raise ValueError("Oct13 whole-market UDiFF original ZIP SHA changed")
    receipts["nse_original_udiff_zip"] = {
        "path": str(RAW_PATH),
        "source_sha256": RAW_NSE_SHA256, "bytes": len(raw_nse),
        "git_blob_sha": _git_sha(raw_nse),
    }
    return sources, raw_nse, receipts


def _source_identity(
    p008: dict[str, Any],
    p041: dict[str, Any],
    p046: dict[str, Any],
) -> tuple[list[str], dict[str, str], dict[str, dict], dict[str, dict]]:
    validate_daily_source_observation(p008)
    validate_twenty_day_all_28(p041)
    if (
        p008.get("session_date_ist") != DAY
        or p008.get("capture_state") != "SOURCE_COMPLETE"
        or p008.get("observed_stock_count") != 10
        or p008.get("live_capital_allowed") is not False
        or p008.get("horizon_return_calculated") is not False
        or p008.get("stock_source", {}).get("sha256") != RAW_NSE_SHA256
        or p008.get("stock_source", {}).get("url") != udiff_url(date.fromisoformat(DAY))
        or p008.get("index_source", {}).get("url") != index_snapshot_url(date.fromisoformat(DAY))
    ):
        raise ValueError("P008 daily source identity or cutoff changed")
    if (
        p041.get("audit_id")
        != "HG007-P041-28-COMPANY-20-SESSION-ORIGINAL-NSE-TURNOVER-v1"
        or p041.get("original_outside_u001_symbol_count") != 28
        or p041.get("source_window_last_session") != "2026-10-09"
        or p041.get("live_capital_allowed") is not False
    ):
        raise ValueError("P041 original 28-company series/ISIN source changed")
    if (
        p046.get("review_id")
        != "HG007-P046-INOXGREEN-2026-10-09-VEPL-CONVERSION-STATE-v1"
        or p046.get("original_28_company_selection_changed") is not False
        or p046.get("company_completion_probabilities_published") != 0
        or p046.get("expected_returns_calculated") is not False
        or p046.get("live_capital_allowed") is not False
    ):
        raise ValueError("P046 latest source stage/selection changed")
    cases_41 = p041.get("casework")
    cases_46 = p046.get("casework_with_current_vepl_milestone")
    if not isinstance(cases_41, list) or not isinstance(cases_46, list):
        raise TypeError("both original 28-case lists must be present")
    if len(cases_41) != 28 or len(cases_46) != 28:
        raise ValueError("original 28-name selected size changed")
    base_by = {r.get("symbol"): r for r in cases_41 if isinstance(r, dict)}
    stage_by = {r.get("symbol"): r for r in cases_46 if isinstance(r, dict)}
    original_names = p041.get("original_selected_symbol_order")
    if (
        not isinstance(original_names, list)
        or len(set(original_names)) != 28
        or set(original_names) != set(base_by)
        or set(original_names) != set(stage_by)
        or len(base_by) != 28
        or len(stage_by) != 28
    ):
        raise ValueError("P041/P046 selected company identity mismatch")
    by_isin = {}
    for symbol in original_names:
        observed = base_by[symbol].get("observed_isins")
        if not isinstance(observed, list) or len(observed) != 1:
            raise ValueError(f"{symbol}: original ISIN identity cannot be established")
        isin = observed[0]
        if not isinstance(isin, str) or len(isin) != 12:
            raise ValueError(f"{symbol}: original ISIN malformed")
        by_isin[symbol] = isin
    return original_names, by_isin, base_by, stage_by


def build_oct13_market_snapshot(
    sources: dict[str, dict],
    *,
    original_nse_zip: bytes,
    receipts: dict[str, dict],
) -> dict[str, Any]:
    p008 = sources["current_day_p008"]
    p041 = sources["historical_p041"]
    p046 = sources["latest_stage_p046"]
    order, by_isin, base, stage = _source_identity(p008, p041, p046)
    if hashlib.sha256(original_nse_zip).hexdigest() != RAW_NSE_SHA256:
        raise ValueError("current original UDiFF raw bytes no longer match")
    session = date.fromisoformat(DAY)
    official_eq = parse_udiff_eq_panel(original_nse_zip, session_date=session)
    by_symbol: dict[str, list[DailyEquityObservation]] = {}
    for item in official_eq:
        if item.symbol in by_isin:
            by_symbol.setdefault(item.symbol, []).append(item)
    all_series = _original_full_market_rows(
        original_nse_zip, session=DAY, symbols=set(order),
    )

    # The first H021 cohort already has ten independently verified EQ rows.
    # Reconcile those exact whole-market observations to make sure today's
    # market data was not quietly swapped for a different "fresh" feed.
    h021 = {r["symbol"]: r for r in p008["stock_rows"]}
    if len(h021) != 10:
        raise ValueError("H021 independent market source reconciliation missing")
    for symbol, stored in h021.items():
        available = by_symbol.get(symbol, [])
        if (
            len(available) != 1
            or available[0].isin != stored["isin"]
            or stored["status"] != "OFFICIAL_OHLC_NOT_EXECUTABLE_FILL"
            or not math.isclose(available[0].open_price, stored["ohlc"]["open_inr"])
            or not math.isclose(available[0].close_price, stored["ohlc"]["close_inr"])
        ):
            raise ValueError(f"original Oct13 H021 EQ price changed for {symbol}")

    cases: list[dict[str, Any]] = []
    equity_count = 0
    off_series = []
    blocked = []
    volume_alerts = []
    for symbol in order:
        isin = by_isin[symbol]
        eq_rows = by_symbol.get(symbol, [])
        raw_rows = all_series.get(symbol, [])
        eq = None
        series_notes = []
        status = "NO_OFFICIAL_NSE_STOCK_ROW"
        if not raw_rows:
            status = "NO_OFFICIAL_NSE_STOCK_ROW"
        elif any(row["isin"] != isin for row in raw_rows):
            status = "SOURCE_IDENTITY_CONFLICT_DO_NOT_FILL"
            series_notes = sorted({row["exchange_series"] for row in raw_rows})
        elif len(eq_rows) > 1:
            status = "DUPLICATE_EQ_SERIES_BLOCKED"
        elif len(eq_rows) == 1:
            eq = eq_rows[0]
            if eq.isin != isin or not _valid_bar(eq):
                status = "INVALID_NSE_EQ_PRICE_OR_TURNOVER"
                eq = None
            else:
                status = "OFFICIAL_EQ_PRICE_VOLUME_OBSERVED_NOT_FILL"
                equity_count += 1
        else:
            series_notes = sorted({row["exchange_series"] for row in raw_rows})
            if all(
                r["valid_positive_executed_turnover"] for r in raw_rows
            ) and series_notes and series_notes != ["EQ"]:
                status = "NON_EQ_SERIES_OBSERVED_NOT_EQ_SOURCE"
                off_series.append(symbol)
            else:
                status = "OFFICIAL_EQ_ROW_MISSING_NO_SUBSTITUTION"

        past = base[symbol].get("turnover_statistics_if_complete")
        hist_median = past.get("median_daily_traded_value_inr_crore") if isinstance(past, dict) else None
        if hist_median is not None and (
            type(hist_median) not in (int, float)
            or not math.isfinite(hist_median)
            or hist_median <= 0
        ):
            raise ValueError(f"{symbol}: historical turnover median invalid")
        turnover_cr = eq.turnover_inr / INR_CRORE if eq is not None else None
        multiple = (
            turnover_cr / hist_median
            if turnover_cr is not None and hist_median is not None
            else None
        )
        if multiple is not None and multiple >= 5:
            volume_alerts.append(symbol)
        if eq is None and symbol not in off_series:
            blocked.append(symbol)

        current_stage = stage[symbol]
        capital_status = current_stage.get("capital_basis_correction")
        if not isinstance(capital_status, dict):
            raise TypeError("current stage case lacks original capital source context")
        cases.append({
            "symbol": symbol,
            "frozen_isin": isin,
            "observed_session": DAY,
            "source_series_state": status,
            "source_other_series_if_not_equity": series_notes,
            "reported_EQ_open_inr": eq.open_price if eq is not None else None,
            "reported_EQ_high_inr": eq.high_price if eq is not None else None,
            "reported_EQ_low_inr": eq.low_price if eq is not None else None,
            "reported_EQ_close_inr": eq.close_price if eq is not None else None,
            "reported_EQ_previous_close_inr": eq.previous_close if eq is not None else None,
            "reported_EQ_traded_shares": int(eq.volume) if eq is not None else None,
            "reported_EQ_traded_value_inr_crore": turnover_cr,
            "reported_EQ_trade_count": int(eq.trade_count) if eq is not None else None,
            "original_twenty_day_EQ_median_value_inr_crore_if_complete": hist_median,
            "one_day_EQ_value_to_past_median_multiple_not_alpha": multiple,
            "historical_original_source_EQ_sessions": base[symbol]["official_20_session_eq_rows_observed"],
            "frozen_transaction_stage": current_stage["hg003_thread_state"],
            "economic_sensitivity_state": current_stage["economic_sensitivity_state"],
            "historical_capital_basis_status": capital_status["status"],
            "inoxgreen_latest_vepl_oct09_stage_retained": (
                symbol == "INOXGREEN"
                and isinstance(current_stage.get("latest_documented_vepl_milestone"), dict)
            ),
            "original_hg002_selection_modified": False,
            "portfolio_position_created": False,
            "actual_trade_execution_confirmed": False,
            "corporate_action_and_dividend_adjustment_verified": False,
            "equity_expected_return_computed": False,
        })
    if len(cases) != 28 or equity_count + len(off_series) + len(blocked) != 28:
        raise ValueError("NSE Oct13 snapshot did not account for all 28 original companies")

    result = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "POST_SELECTION_SOURCE_ONLY_OCT13_NSE_PRICE_TURNOVER_NOT_ALPHA",
        "market_session_ist": DAY,
        "original_28_company_source_selection_preserved": True,
        "source_provenance": receipts,
        "original_nse_full_market_zip_sha256": RAW_NSE_SHA256,
        "independent_h021_same_source_EQ_rows_reconciled": 10,
        "total_original_cases": 28,
        "official_valid_EQ_company_count": equity_count,
        "non_EQ_series_company_count": len(off_series),
        "non_EQ_series_company_symbols": off_series,
        "absent_or_identity_blocked_company_count": len(blocked),
        "absent_or_identity_blocked_symbols": blocked,
        "one_day_to_past_median_value_multiple_at_least_5x_symbols": volume_alerts,
        "one_day_turnover_multiple_is_return_alpha_or_order_capacity": False,
        "company_source_observations": cases,
        "separate_actual_trade_fills_verified": False,
        "current_stock_fully_diluted_share_counts_verified": False,
        "current_market_capitalizations_recomputed": False,
        "stock_total_returns_or_index_excess_calculated": False,
        "stock_selection_or_research_priority_changed": False,
        "live_capital_allowed": False,
        "portfolio_eligibility_allowed": False,
    }
    result["packet_sha256"] = _canonical_hash(result)
    return result


def validate_oct13_market_snapshot(report: dict[str, Any]) -> None:
    if report.get("audit_id") != AUDIT_ID or report.get("market_session_ist") != DAY:
        raise ValueError("not original October 13 28-company market source")
    sig = report.get("packet_sha256")
    if not isinstance(sig, str) or _canonical_hash(
        {k: v for k, v in report.items() if k != "packet_sha256"}
    ) != sig:
        raise ValueError("HG007 Oct13 market source packet SHA changed")
    cases = report.get("company_source_observations")
    if not isinstance(cases, list) or len(cases) != 28:
        raise ValueError("not complete original 28-name ledger")
    if len({x["symbol"] for x in cases}) != 28:
        raise ValueError("duplicate original company market identity")
    if report.get("independent_h021_same_source_EQ_rows_reconciled") != 10:
        raise ValueError("independent H021 source reconciliation absent")
    for field in (
        "one_day_turnover_multiple_is_return_alpha_or_order_capacity",
        "separate_actual_trade_fills_verified",
        "current_stock_fully_diluted_share_counts_verified",
        "current_market_capitalizations_recomputed",
        "stock_total_returns_or_index_excess_calculated",
        "stock_selection_or_research_priority_changed",
        "live_capital_allowed",
        "portfolio_eligibility_allowed",
    ):
        if report.get(field) is not False:
            raise ValueError(f"snapshot cannot authorize {field}")


def materialize_oct13_28(repo_root: Path) -> dict[str, Any]:
    sources, raw, receipts = _read_sources(repo_root)
    result = build_oct13_market_snapshot(sources, original_nse_zip=raw, receipts=receipts)
    validate_oct13_market_snapshot(result)
    return result
