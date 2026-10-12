"""Retrospective original NSE 20-session turnover for *all 28* frozen HG002 names.

The existing P036 five-company study already retained whole-market UDiFF
ZIPs for 20 sessions ending October 9, 2026. Reuse exactly these raw bytes.
Liquidity diagnostics do not forecast fills, exits, capacity, alpha or returns.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import date
from pathlib import Path
from typing import Any

from marketlab.alpha_market import DailyEquityObservation, parse_udiff_eq_panel
from marketlab.hg007_liquidity_history import (
    FIRST_SESSION,
    HISTORY_ID,
    LAST_SESSION,
    REQUIRED_SESSIONS,
    SOURCE_SHA,
    _nearest_rank,
    pinned_window_and_context,
    validate_twenty_session_liquidity,
    validated_historical_source,
)

AUDIT_ID = "HG007-P041-28-COMPANY-20-SESSION-ORIGINAL-NSE-TURNOVER-v1"
ORIGINAL_COHORT_PATH = Path("research/hg002-d001-result-v1.json")
ORIGINAL_COHORT_BLOB = "e4313bd333595fce068dc8fd0882dec16f2ec8b6"
ORIGINAL_FIVE_HISTORY_PATH = Path(
    "research/hg007/twenty-session-liquidity/twenty-session-liquidity-v1.json"
)
ORIGINAL_FIVE_HISTORY_BLOB = "f2e3d33288a432326235bd72db1911bc17b742ea"
TICKET_REFERENCE_INR = (100_000, 1_000_000)
TURNOVER_DENOMINATOR_FRACTION = 0.01
INR_CRORE = 10_000_000
ORIGINAL_FIVE = frozenset({"ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV"})


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _digest(packet: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            packet, sort_keys=True, separators=(",", ":"),
            allow_nan=False, ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _pinned_json(root: Path, path: Path, expected_blob: str) -> tuple[dict, dict]:
    raw = (root / path).read_bytes()
    if _blob(raw) != expected_blob:
        raise ValueError(f"{path}: original research Git blob changed")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError(f"{path}: original research source must be JSON object")
    return data, {
        "path": str(path),
        "git_blob_sha": expected_blob,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _valid_bar(bar: DailyEquityObservation) -> bool:
    """Reject rows that do not establish actual nonzero turnover."""
    values = (
        bar.open_price, bar.high_price, bar.low_price, bar.close_price,
        bar.volume, bar.turnover_inr, bar.trade_count,
    )
    if not all(math.isfinite(v) and v > 0 for v in values):
        return False
    if not bar.volume.is_integer() or not bar.trade_count.is_integer():
        return False
    observed_vwap = bar.turnover_inr / bar.volume
    return bar.low_price <= observed_vwap <= bar.high_price


def _one_day(
    raw: bytes, *,
    session: str, original_symbols: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, DailyEquityObservation]]:
    universe = set(original_symbols)
    bars = parse_udiff_eq_panel(raw, session_date=date.fromisoformat(session))
    by_symbol: dict[str, list[DailyEquityObservation]] = {}
    for bar in bars:
        if bar.symbol in universe:
            by_symbol.setdefault(bar.symbol, []).append(bar)

    matched: dict[str, DailyEquityObservation] = {}
    rows: dict[str, dict[str, Any]] = {}
    for symbol in original_symbols:
        entries = by_symbol.get(symbol, [])
        state = "OFFICIAL_EQ_ROW_MISSING_NO_SUBSTITUTION"
        row: dict[str, Any] = {
            "symbol": symbol,
            "state": state,
            "isin": None,
            "traded_value_inr": None,
            "traded_shares": None,
            "reported_trade_count": None,
        }
        if len(entries) > 1:
            row["state"] = "MULTIPLE_EQ_ISIN_ROWS_IDENTITY_UNRESOLVED"
            row["candidate_isins"] = sorted(item.isin for item in entries)
        elif len(entries) == 1:
            bar = entries[0]
            row["isin"] = bar.isin
            if not _valid_bar(bar):
                row["state"] = "SOURCE_FIELDS_ZERO_OR_INCONSISTENT"
            else:
                row.update({
                    "state": "EXACT_NSE_EQ_OHLC_AND_TURNOVER_OBSERVED",
                    "traded_value_inr": bar.turnover_inr,
                    "traded_shares": int(bar.volume),
                    "reported_trade_count": int(bar.trade_count),
                })
                matched[symbol] = bar
        rows[symbol] = row
    return rows, matched


def _check_original_five(
    *,
    original_row: dict[str, Any],
    parsed: dict[str, DailyEquityObservation],
    expected_isin: dict[str, str],
) -> None:
    old = original_row.get("five_equity_rows")
    if not isinstance(old, list) or len(old) != 5:
        raise ValueError("original P036 five-company daily rows missing")
    if {row.get("symbol") for row in old} != ORIGINAL_FIVE:
        raise ValueError("P036 original five-company identities have changed")
    for item in old:
        symbol = item["symbol"]
        bar = parsed.get(symbol)
        if bar is None or bar.isin != expected_isin[symbol]:
            raise ValueError(f"{symbol}: original five-company source row changed")
        if (
            not math.isclose(bar.turnover_inr, item["traded_value_inr"], rel_tol=0, abs_tol=0.02)
            or not math.isclose(bar.close_price, item["close_inr"], rel_tol=0, abs_tol=1e-8)
            or int(bar.volume) != item["traded_shares"]
            or int(bar.trade_count) != item["reported_executed_trade_count"]
        ):
            raise ValueError(f"{symbol}: original P036 official source turnover differs")


def build_twenty_day_all_28(root: Path) -> dict[str, Any]:
    cohort, cohort_receipt = _pinned_json(
        root, ORIGINAL_COHORT_PATH, ORIGINAL_COHORT_BLOB
    )
    symbols = cohort.get("symbols")
    if (
        cohort.get("cohort_id") != "HG002-D001-v1"
        or cohort.get("cohort_count") != 28
        or not isinstance(symbols, list)
        or len(symbols) != 28
        or len(set(symbols)) != 28
        or cohort.get("live_capital_allowed") is not False
    ):
        raise ValueError("original HG002 selection must be exactly 28 frozen symbols")

    previous, previous_receipt = _pinned_json(
        root, ORIGINAL_FIVE_HISTORY_PATH, ORIGINAL_FIVE_HISTORY_BLOB
    )
    validate_twenty_session_liquidity(previous)
    if (
        previous.get("audit_id") != HISTORY_ID
        or previous.get("source_status")
        != "COMPLETE_ORIGINAL_20_SESSION_EQUITY_EVIDENCE"
        or previous.get("observed_complete_session_count") != REQUIRED_SESSIONS
        or previous.get("source_cutoff_session") != LAST_SESSION
    ):
        raise ValueError("source original five-company liquidity is not complete")

    dates, five_isins, _p035, raw_last, calendar_provenance = (
        pinned_window_and_context(root)
    )
    if not set(five_isins) == ORIGINAL_FIVE or not ORIGINAL_FIVE.issubset(symbols):
        raise ValueError("five original HG005 source identities no longer belong to HG002")
    if [row["session_date"] for row in previous["source_session_rows"]] != [
        row["date"] for row in dates
    ]:
        raise ValueError("P036 historical source sessions differ from frozen NSE calendar")

    by_symbol: dict[str, list[dict[str, Any]]] = {name: [] for name in symbols}
    original_days = []
    for previous_row, period in zip(previous["source_session_rows"], dates, strict=True):
        day = period["date"]
        if day == LAST_SESSION:
            raw = raw_last
            proof = {
                "date": day,
                "state": "PINNED_OCT09_OFFICIAL_SOURCE",
                "original_sha256": SOURCE_SHA,
                "captured_at_utc": None,
            }
        else:
            raw, proof = validated_historical_source(
                root, day, period["close_utc"]
            )
            if raw is None:
                raise ValueError(f"{day}: expected P036 original whole-market ZIP missing")
            proof = {
                "date": day,
                "state": proof["state"],
                "original_sha256": proof["source_sha256"],
                "captured_at_utc": proof["captured_at_utc"],
            }
        if previous_row["original_source"]["source_sha256"] != proof["original_sha256"]:
            raise ValueError(f"{day}: original prior five-company UDiFF SHA drifted")
        rows, parsed = _one_day(raw, session=day, original_symbols=symbols)
        _check_original_five(
            original_row=previous_row, parsed=parsed, expected_isin=five_isins,
        )
        original_days.append(proof)
        for symbol in symbols:
            by_symbol[symbol].append({"session": day, **rows[symbol]})

    if len(original_days) != REQUIRED_SESSIONS:
        raise ValueError("20 original exchange trading dates required")
    casework = []
    for symbol in symbols:
        observations = by_symbol[symbol]
        acceptable = [
            observation
            for observation in observations
            if observation["state"] == "EXACT_NSE_EQ_OHLC_AND_TURNOVER_OBSERVED"
        ]
        mismatches = [
            {"session": observation["session"], "state": observation["state"]}
            for observation in observations
            if observation["state"] != "EXACT_NSE_EQ_OHLC_AND_TURNOVER_OBSERVED"
        ]
        observed_isins = sorted({
            observation["isin"] for observation in acceptable if observation["isin"]
        })
        identity_consistent = len(observed_isins) == 1
        ready = len(acceptable) == REQUIRED_SESSIONS and identity_consistent
        if len(observed_isins) > 1:
            state = "MULTIPLE_IDENTITIES_CORPORATE_ACTION_REVIEW_REQUIRED"
        elif len(acceptable) == 0:
            state = "NO_VERIFIED_EQ_TRADING_ROWS"
        elif not ready:
            state = "PARTIAL_OR_INVALID_TWENTY_SESSION_EQUITY_HISTORY"
        else:
            state = "EXACT_20_SESSION_OFFICIAL_HISTORICAL_TURNOVER_OBSERVED"

        reference = None
        if ready:
            daily_values = [item["traded_value_inr"] for item in acceptable]
            median = statistics.median(daily_values)
            p10 = _nearest_rank(daily_values, 10)
            p25 = _nearest_rank(daily_values, 25)
            if not 0 < p10 <= p25 <= median <= max(daily_values):
                raise ValueError("historical 20-session source turnover quantiles invalid")
            reference = {
                "median_daily_traded_value_inr_crore": median / INR_CRORE,
                "p10_daily_traded_value_inr_crore": p10 / INR_CRORE,
                "p25_daily_traded_value_inr_crore": p25 / INR_CRORE,
                "minimum_daily_traded_value_inr_crore": min(daily_values) / INR_CRORE,
                "maximum_daily_traded_value_inr_crore": max(daily_values) / INR_CRORE,
                "oct09_daily_traded_value_inr_crore": daily_values[-1] / INR_CRORE,
                "ticket_to_one_percent_of_median_turnover": {
                    str(ticket): ticket / (TURNOVER_DENOMINATOR_FRACTION * median)
                    for ticket in TICKET_REFERENCE_INR
                },
                "one_percent_of_median_turnover_is_executable_capacity": False,
                "quotients_are_fill_days_or_slippage_predictions": False,
            }
            if symbol in five_isins:
                old_case = next(
                    item for item in previous["company_distribution"]
                    if item["symbol"] == symbol
                )
                if (
                    observed_isins != [five_isins[symbol]]
                    or not math.isclose(
                        reference["median_daily_traded_value_inr_crore"],
                        old_case["twenty_session_traded_value_median_inr_crore"],
                        abs_tol=1e-8, rel_tol=0,
                    )
                    or not math.isclose(
                        reference["p10_daily_traded_value_inr_crore"],
                        old_case["twenty_session_traded_value_p10_nearest_rank_inr_crore"],
                        abs_tol=1e-8, rel_tol=0,
                    )
                ):
                    raise ValueError(f"{symbol}: new 28-stock liquidity differs from original P036")

        casework.append({
            "symbol": symbol,
            "state": state,
            "official_20_session_eq_rows_observed": len(acceptable),
            "exact_20_session_coverage_complete": ready,
            "observed_isins": observed_isins,
            "identity_continuous_in_original_window": identity_consistent and ready,
            "missing_or_invalid_session_rows": mismatches,
            "daily_source_rows": observations,
            "turnover_statistics_if_complete": reference,
            "reported_source_traded_value_is_bid_ask_depth": False,
            "current_real_position_capacity_verified": False,
            "buy_sell_signals_or_market_returns_computed": False,
            "live_capital_allowed": False,
        })

    packet = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "ORIGINAL_NSE_28_HG002_HISTORICAL_LIQUIDITY_NOT_ALPHA_OR_EXECUTION",
        "original_selection_id": "HG002-D001-v1",
        "original_outside_u001_symbol_count": 28,
        "original_selected_symbol_order": symbols,
        "source_window_first_session": FIRST_SESSION,
        "source_window_last_session": LAST_SESSION,
        "original_completed_sessions": REQUIRED_SESSIONS,
        "complete_20_session_equity_company_count": sum(
            case["exact_20_session_coverage_complete"] for case in casework
        ),
        "incomplete_or_changed_identity_company_count": sum(
            not case["exact_20_session_coverage_complete"] for case in casework
        ),
        "source_input_receipts": {
            "frozen_hg002_selection": cohort_receipt,
            "original_five_company_p036": previous_receipt,
            "calendar_and_oct09": calendar_provenance,
        },
        "twenty_original_nse_whole_market_source_receipts": original_days,
        "casework": casework,
        "measurement_is_posthoc_historical_not_prospective": True,
        "only_five_prior_p036_cases_used_for_reconciliation": True,
        "selection_or_hg005_payoff_amended": False,
        "source_returns_or_alpha_computed": False,
        "future_liquidity_representativeness_proven": False,
        "spread_depth_and_price_impact_verified": False,
        "current_company_capital_fully_verified": False,
        "investment_recommendations_generated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = _digest(packet)
    return packet


def validate_twenty_day_all_28(packet: dict[str, Any]) -> None:
    if packet.get("audit_id") != AUDIT_ID:
        raise ValueError("unrecognized HG007 28-stock liquidity contract")
    packet_hash = packet.get("packet_sha256")
    if not isinstance(packet_hash, str) or _digest({
        k: v for k, v in packet.items() if k != "packet_sha256"
    }) != packet_hash:
        raise ValueError("HG007 28-stock source packet digest changed")
    if (
        packet.get("original_outside_u001_symbol_count") != 28
        or packet.get("original_completed_sessions") != REQUIRED_SESSIONS
        or len(packet.get("casework", [])) != 28
        or len(packet.get("twenty_original_nse_whole_market_source_receipts", []))
        != REQUIRED_SESSIONS
    ):
        raise ValueError("28 companies and 20 exact daily sources must remain accounted")
    identities = [item["symbol"] for item in packet["casework"]]
    if identities != packet.get("original_selected_symbol_order") or len(set(identities)) != 28:
        raise ValueError("the frozen HG002 28-company membership was modified")
    for case in packet["casework"]:
        if len(case.get("daily_source_rows", [])) != REQUIRED_SESSIONS:
            raise ValueError("individual company has incomplete daily source accounting")
        if case.get("exact_20_session_coverage_complete") is False and (
            case.get("turnover_statistics_if_complete") is not None
        ):
            raise ValueError("incomplete original NSE source cannot publish a median")
        if case.get("current_real_position_capacity_verified") is not False:
            raise ValueError("historical traded-value fraction cannot certify capacity")
    for field in (
        "selection_or_hg005_payoff_amended",
        "source_returns_or_alpha_computed",
        "future_liquidity_representativeness_proven",
        "spread_depth_and_price_impact_verified",
        "current_company_capital_fully_verified",
        "investment_recommendations_generated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(field) is not False:
            raise ValueError(f"posthoc historical turnover cannot authorize {field}")
