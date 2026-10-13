"""Pre-registered H021S001 signed-EPS revision *challenger*, not H021 rewrite.

Score = 100 * (current EPS - prior EPS) / max(abs(prior EPS), INR 1).
The INR 1 floor, unchanged original H021 primary coverage, top-decile
selection (including ties), and 20/60 NSE-session horizons are immutable
before the first permissible 16-Oct-2026 signal. All outcomes stay sealed.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from typing import Any

from marketlab.h021 import PRIMARY_MIN_ANALYST_COUNT
from marketlab.h021_future_intent import (
    EXPECTED_CALENDAR_GIT_BLOB,
    EXPECTED_UNIVERSE_GIT_BLOB,
)

TRIAL_ID = "H021S001"
RULE_ID = "H021S001-SIGNED-EPS-REVISION-ONE-INR-FLOOR-v1"
FIRST_PROSPECTIVE_CAPTURE = date(2026, 10, 16)
MIN_PRIOR_ABS_EPS_INR = 1.0
OUTCOME_SESSIONS = (20, 60)


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("source/intent timestamp must be a string")
    value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        raise ValueError("source/intent timestamp must include timezone")
    return value.astimezone(UTC)


def _canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, ensure_ascii=False,
            allow_nan=False, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _symbols(rows: object, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) != 100:
        raise ValueError(f"{label}: original H021 requires exactly 100 rows")
    mapped = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError(f"{label}: source row must be object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in mapped:
            raise ValueError(f"{label}: symbol missing or duplicated")
        mapped[symbol] = row
    return mapped


def _numeric(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise ValueError(f"{label}: finite EPS required")
    return float(value)


def _next_open(calendar: dict, capture_date: str) -> tuple[str, str, str]:
    if calendar.get("version") != "NSE-CM-FY27Q2-v1":
        raise ValueError("H021S001 cannot replace frozen NSE calendar version")
    sessions = calendar.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise TypeError("original official NSE session list missing")
    dates = [r.get("session_date") for r in sessions if isinstance(r, dict)]
    if (
        len(dates) != len(sessions) or len(set(dates)) != len(dates)
        or dates != sorted(dates)
    ):
        raise ValueError("invalid/duplicated official NSE trading sessions")
    matches = [s for s in sessions if s["session_date"] == capture_date]
    upcoming = [s for s in sessions if s["session_date"] > capture_date]
    if len(matches) != 1 or not upcoming:
        raise ValueError("decision/next-open session not official-calendar verified")
    special = calendar.get("unresolved_special_dates")
    if not isinstance(special, list):
        raise TypeError("unresolved special NSE date list missing")
    for unknown in special:
        if capture_date < unknown < upcoming[0]["session_date"]:
            raise ValueError("unresolved Muhurat/special NSE session crosses next entry open")
    return (
        matches[0]["close_timestamp_utc"],
        upcoming[0]["session_date"],
        upcoming[0]["open_timestamp_utc"],
    )


def build_signed_challenger_intent(
    *,
    comparison: dict[str, Any],
    prior: dict[str, Any],
    current: dict[str, Any],
    manifest: dict[str, Any],
    universe: dict[str, Any],
    calendar: dict[str, Any],
    prepared_at_utc: str,
    original_source_hashes: dict[str, str],
) -> dict[str, Any]:
    capture_str = comparison.get("current_capture_date_ist")
    prior_str = comparison.get("prior_capture_date_ist")
    if not isinstance(capture_str, str) or not isinstance(prior_str, str):
        raise TypeError("H021 comparison capture dates missing")
    capture = date.fromisoformat(capture_str)
    previous = date.fromisoformat(prior_str)
    if capture < FIRST_PROSPECTIVE_CAPTURE:
        raise ValueError("signed EPS challenger cannot backdate to 9 October original trial")
    if (
        comparison.get("hypothesis_id") != "H021"
        or comparison.get("schema_version") != 1
        or comparison.get("primary_signal") != (
            "28-35 day same-period consensus EPS revision"
        )
        or comparison.get("primary_coverage_rule") != (
            "analyst_count >= 5 at both captures"
        )
        or comparison.get("outcomes_opened") is not False
        or comparison.get("live_capital_allowed") is not False
        or comparison.get("universe_git_blob_sha") != EXPECTED_UNIVERSE_GIT_BLOB
        or comparison.get("capture_interval_days") != (capture - previous).days
        or not 28 <= (capture - previous).days <= 35
    ):
        raise ValueError("original H021 frozen comparison/interval/source changed")
    if (
        prior.get("capture_date_ist") != prior_str
        or current.get("capture_date_ist") != capture_str
        or manifest.get("schema_version") != 2
        or manifest.get("capture_date_ist") != capture_str
        or manifest.get("universe_git_blob_sha") != EXPECTED_UNIVERSE_GIT_BLOB
        or manifest.get("source_version") != comparison.get("source_version")
        or manifest.get("outcomes_opened") is not False
        or manifest.get("live_capital_allowed") is not False
        or prior.get("outcomes_opened") is not False
        or current.get("outcomes_opened") is not False
        or prior.get("live_capital_allowed") is not False
        or current.get("live_capital_allowed") is not False
    ):
        raise ValueError("H021 source snapshots/manifests not original outcome-blind captures")
    if manifest.get("logical_capture_id") != f"{capture_str}-full-u001-v1":
        raise ValueError("original H021 current logical capture ID changed")
    if (
        manifest.get("source_version") != prior.get("source_version")
        or manifest.get("source_version") != current.get("source_version")
    ):
        raise ValueError("H021 analyst data source-version switch forbidden")
    for key in ("comparison", "prior_gzip", "prior_manifest", "current_gzip",
                "current_manifest"):
        sha = original_source_hashes.get(key)
        if (
            not isinstance(sha, str) or len(sha) != 64
            or any(ch not in "0123456789abcdef" for ch in sha)
        ):
            raise ValueError(f"missing original H021 SHA-256 source: {key}")
    if universe.get("cohort_id") != "FY27-Q2-2026-09-06":
        raise ValueError("unexpected frozen H021 universe cohort")

    close, next_session, open_utc = _next_open(calendar, capture_str)
    capture_time = _utc(manifest.get("captured_at_utc"))
    preparation = _utc(prepared_at_utc)
    if not (_utc(close) <= capture_time <= preparation < _utc(open_utc)):
        raise ValueError("signed challenger was not frozen after capture but before next open")
    if preparation < _utc(current.get("captured_at_utc")):
        raise ValueError("source snapshot observed after challenger preparation")
    universe_map = _symbols(universe.get("members"), "U001 universe")
    a = _symbols(prior.get("observations"), "prior snapshot")
    b = _symbols(current.get("observations"), "current snapshot")
    rows = _symbols(comparison.get("revision_observations"), "original H021 comparison")
    if not (set(a) == set(b) == set(rows) == set(universe_map)):
        raise ValueError("original H021 100-member panel identity differs")
    original_selection = comparison.get("primary_top_decile_symbols")
    if (
        not isinstance(original_selection, list)
        or len(original_selection) != len(set(original_selection))
        or len(original_selection) != comparison.get("primary_top_decile_count")
    ):
        raise ValueError("incumbent H021 top decile is ambiguous")

    covered = []
    missing = []
    for symbol in sorted(rows):
        base, recent, old_row = a[symbol], b[symbol], rows[symbol]
        if old_row.get("prior_capture_date") != prior_str or old_row.get(
            "current_capture_date"
        ) != capture_str:
            raise ValueError("comparison row was not from exact historical source dates")
        if old_row.get("primary_signal_available") is False:
            if symbol in original_selection:
                raise ValueError("incumbent H021 includes coverage-ineligible symbol")
            missing.append({"symbol": symbol, "reason": old_row.get("primary_signal_reason")})
            continue
        if old_row.get("primary_signal_available") is not True:
            raise ValueError("H021 primary eligibility is missing")
        eps_prev = _numeric(base.get("consensus_eps"), f"{symbol} prior")
        eps_now = _numeric(recent.get("consensus_eps"), f"{symbol} current")
        if eps_prev == 0:
            raise ValueError("original eligible H021 primary denominator cannot be zero")
        n0, n1 = base.get("analyst_count"), recent.get("analyst_count")
        if (
            type(n0) is not int or type(n1) is not int
            or n0 < PRIMARY_MIN_ANALYST_COUNT or n1 < PRIMARY_MIN_ANALYST_COUNT
            or old_row.get("analyst_count_prior") != n0
            or old_row.get("analyst_count_current") != n1
        ):
            raise ValueError("source EPS analyst contributor coverage mismatch")
        period = recent.get("fiscal_period")
        ending = recent.get("period_ending")
        currency = recent.get("eps_currency")
        if (
            base.get("fiscal_period") != period
            or base.get("period_ending") != ending
            or base.get("eps_currency") != currency
            or old_row.get("period_compatible") is not True
            or old_row.get("eps_currency_compatible") is not True
            or old_row.get("source_compatible") is not True
            or currency != "INR"
        ):
            raise ValueError("signed INR EPS would mix incompatible periods/currencies")
        frozen_pct = _numeric(old_row.get("eps_revision_pct"), f"{symbol} H021 ratio")
        old_pct = 100 * (eps_now / eps_prev - 1)
        if not math.isclose(frozen_pct, old_pct, rel_tol=1e-9, abs_tol=1e-8):
            raise ValueError("original H021 ratio does not match source EPS")
        signed = 100 * (eps_now - eps_prev) / max(
            abs(eps_prev), MIN_PRIOR_ABS_EPS_INR
        )
        covered.append({
            "symbol": symbol,
            "isin": universe_map[symbol]["isin"],
            "original_h021_ratio_pct": frozen_pct,
            "signed_eps_floor_revision_pct": signed,
            "prior_eps_inr": eps_prev,
            "current_eps_inr": eps_now,
            "original_h021_selected": symbol in original_selection,
            "negative_prior_eps": eps_prev < 0,
            "floor_applied": abs(eps_prev) < MIN_PRIOR_ABS_EPS_INR,
            "source_period_ending": ending,
            "source_analyst_count_prior": n0,
            "source_analyst_count_current": n1,
        })

    if len(covered) != comparison.get("primary_signal_available_count"):
        raise ValueError("original analyst-covered H021 panel changed")
    original_sorted = sorted(covered, key=lambda r: (-r["original_h021_ratio_pct"], r["symbol"]))
    original_cutoff = (
        original_sorted[math.ceil(len(covered) * 0.1) - 1]["original_h021_ratio_pct"]
        if covered else None
    )
    recomputed_incumbent = {
        row["symbol"] for row in covered
        if row["original_h021_ratio_pct"] >= original_cutoff
    } if covered else set()
    if recomputed_incumbent != set(original_selection):
        raise ValueError("incumbent H021 selected cohort is inconsistent")
    ranked = sorted(covered, key=lambda r: (-r["signed_eps_floor_revision_pct"], r["symbol"]))
    cutoff = (
        ranked[math.ceil(len(ranked) * 0.1) - 1]["signed_eps_floor_revision_pct"]
        if ranked else None
    )
    selected = [
        r for r in ranked if r["signed_eps_floor_revision_pct"] >= cutoff
    ] if cutoff is not None else []
    for row in selected:
        row["selected_by_signed_challenger"] = True

    output: dict[str, Any] = {
        "schema_version": 1,
        "trial_id": TRIAL_ID,
        "rule_id": RULE_ID,
        "intent_id": f"{TRIAL_ID}-{capture_str}-PRIMARY-PAPER-v1",
        "classification": "NEW_PREREGISTERED_PROSPECTIVE_CHALLENGER_NOT_REWRITTEN_H021",
        "registered_before_first_valid_capture": True,
        "prepared_at_utc": preparation.isoformat().replace("+00:00", "Z"),
        "source_comparison_current_date_ist": capture_str,
        "source_comparison_prior_date_ist": prior_str,
        "source_capture_interval_days": (capture - previous).days,
        "source_family": comparison["source_version"],
        "source_original_sha256": original_source_hashes,
        "original_u001_git_blob": EXPECTED_UNIVERSE_GIT_BLOB,
        "original_calendar_git_blob": EXPECTED_CALENDAR_GIT_BLOB,
        "cohort_frozen_universe_size": 100,
        "eligible_h021_comparator_count": len(covered),
        "covered_negative_prior_eps_count": sum(x["negative_prior_eps"] for x in covered),
        "covered_eps_floor_applied_count": sum(x["floor_applied"] for x in covered),
        "ineligible_rows_retained": missing,
        "signal_unit": "SIGNED_INR_EPS_PERCENT_NORMALIZED_WITH_1_INR_FLOOR",
        "preregistered_eps_denominator_floor_inr": MIN_PRIOR_ABS_EPS_INR,
        "incumbent_h021_frozen_symbols_unchanged": original_selection,
        "challenger_top_decile_tie_cutoff_score": cutoff,
        "challenger_selected_count": len(selected),
        "challenger_selected": [
            {
                "symbol": r["symbol"],
                "isin": r["isin"],
                "signed_eps_floor_revision_pct": r["signed_eps_floor_revision_pct"],
                "prior_eps_inr": r["prior_eps_inr"],
                "current_eps_inr": r["current_eps_inr"],
                "negative_prior_eps": r["negative_prior_eps"],
                "floor_applied": r["floor_applied"],
                "entry_price_inr": None,
                "capital_weight": None,
                "actual_execution_verified": False,
            } for r in selected
        ],
        "paired_h021_and_challenger_overlap_count": len(
            set(original_selection) & {r["symbol"] for r in selected}
        ),
        "planned_entry_session_ist": next_session,
        "planned_entry_open_utc": _utc(open_utc).isoformat().replace("+00:00", "Z"),
        "secondary_horizon_completed_sessions": OUTCOME_SESSIONS[0],
        "primary_horizon_completed_sessions": OUTCOME_SESSIONS[1],
        "frozen_benchmark_family": "NIFTY_500",
        "same_entry_holding_and_benchmark_as_original_h021": True,
        "future_return_prices_observed": False,
        "corporate_actions_dividends_costs_verified": False,
        "historical_oct09_cohort_backtested_or_promoted": False,
        "alpha_significance_or_completion_probability_estimated": False,
        "separate_rta001_multiple_testing_registration_required": True,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["packet_sha256"] = _canonical_hash(output)
    return output


def validate_challenger_intent(intent: dict[str, Any]) -> None:
    if intent.get("rule_id") != RULE_ID or intent.get("trial_id") != TRIAL_ID:
        raise ValueError("not a frozen H021 signed challenger")
    checksum = intent.get("packet_sha256")
    if not isinstance(checksum, str) or checksum != _canonical_hash(
        {k: v for k, v in intent.items() if k != "packet_sha256"}
    ):
        raise ValueError("signed challenger immutable intent was modified")
    if (
        intent.get("future_return_prices_observed") is not False
        or intent.get("historical_oct09_cohort_backtested_or_promoted") is not False
        or intent.get("portfolio_eligibility_allowed") is not False
        or intent.get("live_capital_allowed") is not False
    ):
        raise ValueError("signed EPS experiment crossed a prohibited outcome/capital boundary")
