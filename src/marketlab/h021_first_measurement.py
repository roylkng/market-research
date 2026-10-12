"""H021 first prospective entry: point-in-time, no-return measurement audit.

Reconcile source-frozen 9 Oct H021 EPS top decile, the original 12 Oct
after-close verified stock OHLC in the *first partial NSE attempt*, the
pre-entry original VEDL dividend announcement, and the frozen P007 negative
EPS denominator warning. This is an evidence overlay, NOT a backtest,
trading signal, benchmark replacement, or portfolio fill.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h021_entry_observation import validate_entry_observation
from marketlab.h021_first_entry_intent import git_blob_sha

AUDIT_ID = "H021-P017-FIRST-ENTRY-MEASUREMENT-CAVEATS-v1"
FIRST_DATE = "2026-10-12"
ORIGINAL_PACKET_SHA = "c314c0f001476f9ff221ca5055fb6b185702f862d4a455c5f0bb0e2f151dacbd"
ORIGINAL_STOCK_ZIP_SHA = "818f673b3cdb96ae8ec4e466c7c4fd3a28d035482173a675dd24f9437a3ecd99"
VEDL_ORIGINAL_PDF_SHA = "abdd026339469b9e51ab75fb2a37551be23812dcc037c875759cd79a8e6cb364"
INDEX_URL = "https://archives.nseindia.com/content/indices/ind_close_all_12102026.csv"
SOURCE_FILES: dict[str, tuple[str, str]] = {
    "frozen_u001_original_universe": (
        "research/prospective/universes/FY27-Q2-2026-09-06.json",
        "8026e81faee3e913d2fba1dba72d60603b69fa07",
    ),
    "original_preentry_intent": (
        "research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json",
        "e25f77e1c845456473e624899d4748e306b1225b",
    ),
    "original_eps_comparison": (
        "research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json",
        "99c94c9d98284076bf1a7c34ee43e602b741b15b",
    ),
    "original_first_entry_source_attempt": (
        "research/prospective/h021/entry-observations/attempts/38246531921-1.json",
        "",  # P004 event-specific receipt; its original packet SHA is validated below.
    ),
    "independent_original_source_replay": (
        (
            "research/prospective/h021/entry-observations/reconstructed-attempts/"
            "38246531921-1.json"
        ),
        "4c85a6a053ffcdb6d28456163464e63a463f9511",
    ),
    "original_preentry_eps_sign_audit": (
        "research/h021-p007-result-v1.json",
        "b7bbfd81422ceb519df0b80a3a54de07079ed992",
    ),
    "original_vedl_dividend_risk": (
        "research/prospective/h021/pre-entry-risk/2026-10-09-vedl-dividend-alert-v1.json",
        "968ade0e2275107b0e5ab760ba111110497224a6",
    ),
    "original_vedl_nse_pdf_receipt": (
        (
            "research/prospective/h021/dividend-evidence/vedl-2026-10-08/"
            "source-receipt-v1.json"
        ),
        "de2d9889ec303067404ba62c136cd221288ac0ad",
    ),
}
VEDL_PDF_FILE = (
    "research/prospective/h021/dividend-evidence/vedl-2026-10-08/"
    "original/sha256/" + VEDL_ORIGINAL_PDF_SHA + ".pdf"
)
EXPECTED_NAMES = (
    "VEDL",
    "ETERNAL",
    "DMART",
    "IDEA",
    "ADANIENSOL",
    "JSWSTEEL",
    "COALINDIA",
    "INFY",
    "GAIL",
    "POWERGRID",
)


def _read_source(root: Path, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    path, expected_blob = SOURCE_FILES[key]
    raw = (root / path).read_bytes()
    observed_blob = git_blob_sha(raw)
    if expected_blob and observed_blob != expected_blob:
        raise ValueError(f"{key}: immutable Git source blob changed")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError(f"{key}: source must be a JSON object")
    return value, {
        "path": path,
        "git_blob_sha": observed_blob,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw),
    }


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("source chronology timestamp missing")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("chronology requires an offset-aware timestamp")
    return parsed.astimezone(UTC)


def _float(value: object, description: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(float(value)):
        raise ValueError(f"{description}: missing or nonfinite source number")
    return float(value)


def build_measurement_record(
    *,
    intent: dict[str, Any],
    universe: dict[str, Any],
    comparison: dict[str, Any],
    original_attempt: dict[str, Any],
    first_replay: dict[str, Any],
    eps_sign: dict[str, Any],
    original_risk: dict[str, Any],
    vedl_receipt: dict[str, Any],
    source_provenance: dict[str, Any],
) -> dict[str, Any]:
    validate_entry_observation(first_replay)
    if (
        intent.get("intent_id") != "H021-P003-2026-10-09-FIRST-COHORT-v1"
        or intent.get("live_capital_allowed") is not False
        or intent.get("portfolio_eligibility_allowed") is not False
        or intent.get("frozen_primary_selection_unchanged") is not True
    ):
        raise ValueError("original first prospective decision intent changed")
    observations = intent.get("selected_observations")
    if not isinstance(observations, list) or len(observations) != 10:
        raise ValueError("H021 ten original selected source observations required")
    selections = tuple(row.get("symbol") for row in observations)
    if selections != EXPECTED_NAMES:
        raise ValueError("first 10 original cohort names/order changed")
    members = universe.get("members")
    if (
        universe.get("cohort_id") != "FY27-Q2-2026-09-06"
        or not isinstance(members, list)
        or len(members) != 100
    ):
        raise ValueError("frozen U001 ISIN source cohort identity changed")
    frozen_isins = {item["symbol"]: item["isin"] for item in members}
    if len(frozen_isins) != 100 or any(
        not isinstance(isin, str) or len(isin) != 12
        for isin in frozen_isins.values()
    ):
        raise ValueError("original frozen U001 universe symbol/ISIN identity invalid")
    if (
        comparison.get("hypothesis_id") != "H021"
        or comparison.get("current_capture_date_ist") != "2026-10-09"
        or comparison.get("primary_signal_available_count") != 97
        or comparison.get("primary_top_decile_symbols") != list(EXPECTED_NAMES)
        or comparison.get("outcomes_opened") is not False
        or comparison.get("live_capital_allowed") is not False
    ):
        raise ValueError("original 28-day H021 source selection changed")
    rows = comparison.get("revision_observations")
    if not isinstance(rows, list) or len(rows) != 100:
        raise ValueError("full 100-name source-comparison denominator required")
    indexed = {row["symbol"]: row for row in rows}
    if len(indexed) != 100:
        raise ValueError("H021 source comparisons duplicated symbols")
    if (
        original_attempt.get("intent_id") != intent["intent_id"]
        or original_attempt.get("session_date_ist") != FIRST_DATE
        or original_attempt.get("packet_sha256") != ORIGINAL_PACKET_SHA
        or original_attempt.get("observed_official_stock_open_count") != 10
        or original_attempt.get("source_observation_status")
        != "PARTIAL_OR_BLOCKED_SOURCE_OBSERVATION"
        or original_attempt.get("live_capital_allowed") is not False
    ):
        raise ValueError("original Git-sealed first source attempt changed")
    if (
        first_replay.get("packet_sha256") != ORIGINAL_PACKET_SHA
        or first_replay.get("session_date_ist") != FIRST_DATE
        or first_replay.get("source_intent_id") != intent["intent_id"]
        or first_replay.get("observed_official_stock_open_count") != 10
        or first_replay.get("selected_symbol_count") != 10
        or first_replay.get("source_observation_status")
        != "PARTIAL_OR_BLOCKED_SOURCE_OBSERVATION"
    ):
        raise ValueError("first complete-stock source reconstruction changed")
    if first_replay.get("source_receipts") != original_attempt.get("source_receipts"):
        raise ValueError("first source-replay original NSE receipts changed")
    if (
        first_replay.get("entry_trades_executed") is not False
        or first_replay.get("return_outcomes_opened") is not False
        or first_replay.get("live_capital_allowed") is not False
    ):
        raise ValueError("first market observation cannot imply execution or future returns")
    sources = first_replay["source_receipts"]
    stock = sources["udiff"]
    index = sources["index"]
    if (
        stock.get("status") != "OK"
        or stock.get("http_status") != 200
        or stock.get("raw_sha256") != ORIGINAL_STOCK_ZIP_SHA
        or index.get("status") != "NOT_PUBLISHED"
        or index.get("http_status") != 404
        or index.get("official_source_url") != INDEX_URL
        or index.get("raw_sha256") is not None
        or first_replay.get("benchmark_observation", {}).get("open_index_value") is not None
        or first_replay.get("benchmark_observation", {}).get("close_index_value") is not None
        or first_replay.get("benchmark_observation", {}).get("basis") != "PRICE_INDEX_NOT_TRI"
    ):
        raise ValueError("initial official stock-only or missing-index evidence altered")

    if (
        eps_sign.get("audit_id") != "H021-P007-2026-10-09-EPS-SIGN-SEMANTICS-v1"
        or eps_sign.get("eligible_eps_observations") != 97
        or eps_sign.get("direction_inversion_top_decile_count") != 1
        or eps_sign.get("original_top_decile_inverted_symbols") != ["IDEA"]
        or eps_sign.get("predefined_primary_selection_changed") is not False
        or eps_sign.get("return_outcomes_opened") is not False
    ):
        raise ValueError("first original negative-denominator audit changed")
    negative = [row for row in eps_sign["negative_prior_eps_cases"]
                if row["in_original_primary_top_decile"]]
    if len(negative) != 1 or negative[0]["symbol"] != "IDEA":
        raise ValueError("expected one selected negative-EPS source case")
    idea = negative[0]
    if not (
        idea["prior_eps"] == -1.73
        and idea["current_eps"] == -1.81
        and idea["absolute_eps_change"] < 0
        and idea["original_ratio_revision_pct"] > 0
        and idea["economic_direction"] == "LOSS_WORSENING"
    ):
        raise ValueError("frozen IDEA source earnings direction changed")
    if (
        original_risk.get("risk_id") != "H021-P011-FIRST-ENTRY-KNOWN-DIVIDEND-BOUNDARY-v1"
        or original_risk.get("publicly_identified_pre_entry_dividend_symbols") != ["VEDL"]
        or original_risk.get("original_h021_selection_unchanged") is not True
        or original_risk.get("return_outcomes_opened") is not False
    ):
        raise ValueError("original pre-entry corporate-action awareness changed")
    first_risk = original_risk["source_risk_rows"][0]
    if first_risk.get("symbol") != "VEDL":
        raise ValueError("VEDL pre-entry alert identity changed")
    if (
        vedl_receipt.get("source_id") != "H021-P012-VEDL-2026-10-08-ORIGINAL-NSE-DIVIDEND-v1"
        or vedl_receipt.get("symbol") != "VEDL"
        or vedl_receipt.get("isin") != "INE205A01025"
        or vedl_receipt.get("state")
        != "OFFICIAL_PDF_BYTES_AND_ISSUER_TEXT_CAPTURED_NOT_ENTITLEMENT_AUDITED"
        or vedl_receipt.get("original_pdf_sha256") != VEDL_ORIGINAL_PDF_SHA
        or vedl_receipt.get("actual_h021_trade_and_entitlement_proven") is not False
        or vedl_receipt.get("h021_return_basis_total_return_certified") is not False
        or vedl_receipt.get("live_capital_allowed") is not False
    ):
        raise ValueError("original NSE VEDL payout source provenance changed")
    payout = vedl_receipt["issuer_reported_dividend_terms"]
    if (
        payout.get("issuer_reported_dividend_per_share_inr") != 5
        or payout.get("issuer_reported_record_date_ist") != "2026-10-14"
        or payout.get("hypothetical_entry_holder_dividend_entitlement_proven") is not False
        or payout.get("ex_date_confirmed_by_this_pdf") is not False
        or payout.get("cash_dividend_payable_or_received_proven") is not False
    ):
        raise ValueError("original issuer VEDL payout amount/entitlement semantics changed")
    posted = _parse_utc(
        vedl_receipt["first_original_announcement_provenance"][
            "source_public_broadcast_at_utc"
        ]
    )
    planned = _parse_utc(intent["entry_plan"]["calendar_open_timestamp_utc"])
    retrieved = _parse_utc(vedl_receipt["original_pdf_fetched_at_utc"])
    observed_at = _parse_utc(first_replay["recorded_at_utc"])
    if not (posted < planned < retrieved < observed_at):
        raise ValueError("pre-entry VEDL disclosure and after-entry retrieval chronology changed")

    positions = first_replay["stock_observations"]
    if tuple(row.get("symbol") for row in positions) != EXPECTED_NAMES:
        raise ValueError("first observed NSE ten-name order changed")
    by_intent = {row["symbol"]: row for row in observations}
    selected_records = []
    for row in positions:
        symbol = row["symbol"]
        source = indexed[symbol]
        open_inr = _float(row.get("open_price_inr"), f"{symbol} opening price")
        close_inr = _float(row.get("close_price_inr"), f"{symbol} observed close")
        original_eps = _float(source.get("eps_revision_pct"), f"{symbol} EPS revision")
        if (
            open_inr <= 0 or close_inr <= 0
            or row.get("status") != "OFFICIAL_OHLC_OBSERVED_NOT_EXECUTABLE_FILL"
            or row.get("source_sha256") != ORIGINAL_STOCK_ZIP_SHA
            or row.get("isin") != frozen_isins[symbol]
            or row.get("actual_trade_fill_confirmed") is not False
            or source.get("primary_signal_available") is not True
            or original_eps != by_intent[symbol].get("eps_revision_pct")
        ):
            raise ValueError(f"{symbol}: original signal/OHLC identity or execution changed")
        caution = []
        special: dict[str, Any] | None = None
        if symbol == "IDEA":
            caution.append("NEGATIVE_PRIOR_EPS_REVERSES_PERCENTAGE_REVISION_DIRECTION")
            if not math.isclose(
                original_eps, idea["original_ratio_revision_pct"],
                rel_tol=1e-12, abs_tol=1e-12
            ):
                raise ValueError("IDEA actual frozen revision differs from source case")
            special = {
                "prior_eps_inr": idea["prior_eps"],
                "current_eps_inr": idea["current_eps"],
                "absolute_eps_change": idea["absolute_eps_change"],
                "loss_trend": "FORECAST_LOSS_WORSENING_DESPITE_POSITIVE_RATIO",
            }
        if symbol == "VEDL":
            caution.append("ANNOUNCED_DIVIDEND_RETURN_BASIS_AND_ENTITLEMENT_UNRESOLVED")
            special = {
                "original_pdf_sha256": VEDL_ORIGINAL_PDF_SHA,
                "announced_cash_dividend_per_share_inr": 5.0,
                "original_issuer_reported_record_date_ist": "2026-10-14",
                "dividend_to_observed_open_magnitude_pct_not_yield_or_return": (
                    100.0 * 5.0 / open_inr
                ),
                "ex_date_independently_verified": False,
                "observed_hypothetical_position_dividend_entitlement_verified": False,
                "actual_cash_receipt_verified": False,
            }
        selected_records.append({
            "symbol": symbol,
            "isin": row["isin"],
            "frozen_2026_10_09_eps_ratio_revision_pct": original_eps,
            "2026_10_12_official_equity_open_inr": open_inr,
            "2026_10_12_official_equity_close_inr": close_inr,
            "open_observation_is_real_fill": False,
            "measurement_warnings": caution,
            "source_bound_special_notice": special,
            "benchmark_excess_computable_from_this_packet": False,
        })
    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "H021_ORIGINAL_FIRST_ENTRY_SOURCE_AND_MEASUREMENT_RISK_NOT_RETURNS",
        "original_selection_date_ist": "2026-10-09",
        "first_source_session_date_ist": FIRST_DATE,
        "source_first_attempt_recorded_at_utc": first_replay["recorded_at_utc"],
        "source_provenance": source_provenance,
        "original_first_attempt_packet_sha256": ORIGINAL_PACKET_SHA,
        "first_nse_stock_raw_sha256": ORIGINAL_STOCK_ZIP_SHA,
        "first_source_attempt_nifty500_index_state": "HTTP_404_NOT_PUBLISHED_AT_FIRST_CAPTURE",
        "benchmark_may_become_available_on_later_source_attempt": True,
        "index_value_from_other_dates_or_providers_inserted": False,
        "first_source_stock_open_count": len(selected_records),
        "original_top_decile_unchanged": True,
        "selected_stock_observations": selected_records,
        "original_selected_negative_eps_inversion_symbols": ["IDEA"],
        "original_selected_preentry_dividend_notice_symbols": ["VEDL"],
        "fully_verified_20_60_session_stock_index_comparable_returns": False,
        "independent_full_interval_corporate_action_census_verified": False,
        "cash_dividend_entitlement_verified": False,
        "nifty500_total_return_index_basis_verified": False,
        "actual_next_open_execution_and_slippage_verified": False,
        "return_outcomes_opened": False,
        "benchmark_excess_calculated": False,
        "original_h021_investment_selection_changed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def source_pinned_first_measurement(root: Path) -> dict[str, Any]:
    sources = {}
    provenance = {}
    for key in SOURCE_FILES:
        sources[key], provenance[key] = _read_source(root, key)
    dividend_pdf = (root / VEDL_PDF_FILE).read_bytes()
    if hashlib.sha256(dividend_pdf).hexdigest() != VEDL_ORIGINAL_PDF_SHA:
        raise ValueError("original public VEDL dividend PDF source bytes were modified")
    provenance["vedl_original_pdf"] = {
        "path": VEDL_PDF_FILE,
        "sha256": VEDL_ORIGINAL_PDF_SHA,
        "byte_count": len(dividend_pdf),
    }
    return build_measurement_record(
        intent=sources["original_preentry_intent"],
        universe=sources["frozen_u001_original_universe"],
        comparison=sources["original_eps_comparison"],
        original_attempt=sources["original_first_entry_source_attempt"],
        first_replay=sources["independent_original_source_replay"],
        eps_sign=sources["original_preentry_eps_sign_audit"],
        original_risk=sources["original_vedl_dividend_risk"],
        vedl_receipt=sources["original_vedl_nse_pdf_receipt"],
        source_provenance=provenance,
    )
