"""Pre-entry research-only intent for every future H021 valid revision cohort.

Never edits H021's selected names, frozen rule, pricing, returns or PF001.
The first 2026-10-09 P003 intent remains authoritative and immutable.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from typing import Any

from marketlab.h021 import PRIMARY_MIN_ANALYST_COUNT

RULE_ID = "H021-P005-GENERIC-ENTRY-INTENT-v1"
EXPECTED_PRIMARY_SIGNAL = "28-35 day same-period consensus EPS revision"
EXPECTED_UNIVERSE_GIT_BLOB = "8026e81faee3e913d2fba1dba72d60603b69fa07"
EXPECTED_CALENDAR_GIT_BLOB = "9ac614820a67b0f7b20d8170d15b84df3c996b62"


def _utc(value: object, description: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{description} must be a UTC timestamp")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{description} must be ISO timestamp") from exc
    if result.tzinfo is None:
        raise ValueError(f"{description} must include timezone")
    return result.astimezone(UTC)


def _sha(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def build_future_h021_intent(
    comparison: dict[str, Any],
    manifest: dict[str, Any],
    calendar: dict[str, Any],
    universe: dict[str, Any],
    *,
    prepared_at_utc: str,
    comparison_raw_sha256: str,
    manifest_raw_sha256: str,
) -> dict[str, Any]:
    if comparison.get("schema_version") != 1 or comparison.get("hypothesis_id") != "H021":
        raise ValueError("invalid H021 primary comparison identity")
    if comparison.get("primary_signal") != EXPECTED_PRIMARY_SIGNAL:
        raise ValueError("primary H021 rule changed")
    if comparison.get("outcomes_opened") is not False:
        raise ValueError("return outcomes must stay unopened")
    if comparison.get("live_capital_allowed") is not False:
        raise ValueError("live capital must stay disabled")
    if comparison.get("universe_git_blob_sha") != EXPECTED_UNIVERSE_GIT_BLOB:
        raise ValueError("H021 source universe changed")
    if comparison.get("capture_interval_days") not in range(28, 36):
        raise ValueError("frozen 28-35-day comparison interval missing")
    if not all(
        isinstance(value, str) and len(value) == 64 and
        all(c in "0123456789abcdef" for c in value)
        for value in (comparison_raw_sha256, manifest_raw_sha256)
    ):
        raise ValueError("real source SHA-256 hashes are required")

    current_day = comparison.get("current_capture_date_ist")
    prior_day = comparison.get("prior_capture_date_ist")
    if not isinstance(current_day, str) or not isinstance(prior_day, str):
        raise TypeError("both H021 capture dates required")
    current_date = date.fromisoformat(current_day)
    prior_date = date.fromisoformat(prior_day)
    if (current_date - prior_date).days != comparison["capture_interval_days"]:
        raise ValueError("comparison capture interval is inconsistent")
    if current_day < "2026-10-09":
        raise ValueError("H021 prospective cohort cannot predate first valid comparison")

    if manifest.get("schema_version") != 2:
        raise ValueError("current capture requires sealed H021 manifest v2")
    if manifest.get("capture_date_ist") != current_day:
        raise ValueError("comparison/capture manifest date differs")
    if manifest.get("logical_capture_id") != f"{current_day}-full-u001-v1":
        raise ValueError("comparison/capture identity mismatch")
    if manifest.get("source_version") != comparison.get("source_version"):
        raise ValueError("source-version switch is not allowed")
    if manifest.get("universe_git_blob_sha") != EXPECTED_UNIVERSE_GIT_BLOB:
        raise ValueError("manifest/source universe changed")
    if manifest.get("outcomes_opened") is not False:
        raise ValueError("manifest must remain outcome blind")
    if manifest.get("live_capital_allowed") is not False:
        raise ValueError("manifest cannot authorize capital")

    if calendar.get("version") != "NSE-CM-FY27Q2-v1":
        raise ValueError("not the frozen official 2026 calendar")
    sessions = calendar.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise TypeError("NSE calendar sessions missing")
    session_dates = [r.get("session_date") for r in sessions if isinstance(r, dict)]
    if len(session_dates) != len(sessions) or len(session_dates) != len(set(session_dates)):
        raise ValueError("NSE calendar sessions duplicated or malformed")
    if session_dates != sorted(session_dates):
        raise ValueError("NSE calendar sessions not ordered")
    current_sessions = [row for row in sessions if row["session_date"] == current_day]
    future_sessions = [row for row in sessions if row["session_date"] > current_day]
    if len(current_sessions) != 1:
        raise ValueError("capture day not a completed NSE calendar session")
    if not future_sessions:
        raise ValueError("no verified next NSE session; require official calendar extension")
    # A holiday flagged as a possible special trading session must not be
    # discarded simply because it falls outside the weekday session list.
    # That would select an incorrect next-open date before price observation.
    unresolved_dates = calendar.get("unresolved_special_dates")
    if not isinstance(unresolved_dates, list):
        raise TypeError("frozen NSE calendar unresolved special dates missing")
    next_regular_date = date.fromisoformat(future_sessions[0]["session_date"])
    for raw_day in unresolved_dates:
        if not isinstance(raw_day, str):
            raise TypeError("unresolved special date must be ISO string")
        special_date = date.fromisoformat(raw_day)
        if current_date < special_date < next_regular_date:
            raise ValueError(
                "unresolved NSE special session before next regular open; "
                "cannot freeze a guessed entry date"
            )
    current_close = _utc(current_sessions[0]["close_timestamp_utc"], "market close")
    next_open = _utc(future_sessions[0]["open_timestamp_utc"], "next session open")
    captured_at = _utc(manifest.get("captured_at_utc"), "source capture")
    prepared = _utc(prepared_at_utc, "intent preparation")
    if not (current_close <= captured_at <= prepared < next_open):
        raise ValueError("capture or intent occurred after next open or before source close")

    members = universe.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise ValueError("frozen 100-name U001 required")
    by_symbol: dict[str, dict[str, Any]] = {}
    for member in members:
        if not isinstance(member, dict):
            raise TypeError("U001 universe members must be objects")
        symbol, isin = member.get("symbol"), member.get("isin")
        if (
            not isinstance(symbol, str) or not symbol or symbol in by_symbol
            or not isinstance(isin, str) or len(isin) != 12
        ):
            raise ValueError("invalid or duplicate frozen universe identity")
        by_symbol[symbol] = member

    observations = comparison.get("revision_observations")
    if not isinstance(observations, list) or len(observations) != 100:
        raise ValueError("exactly 100 H021 comparison rows required")
    by_observation: dict[str, dict[str, Any]] = {}
    for row in observations:
        if not isinstance(row, dict):
            raise TypeError("H021 comparison rows must be objects")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in by_observation:
            raise ValueError("missing or duplicate H021 comparison symbol")
        if row.get("current_capture_date") != current_day:
            raise ValueError("H021 comparison row current date changed")
        if row.get("prior_capture_date") != prior_day:
            raise ValueError("H021 comparison row prior date changed")
        by_observation[symbol] = row
    if set(by_observation) != set(by_symbol):
        raise ValueError("comparison symbol set differs from frozen universe")
    selected_symbols = comparison.get("primary_top_decile_symbols")
    if not isinstance(selected_symbols, list) or len(selected_symbols) != len(set(selected_symbols)):
        raise ValueError("invalid H021 primary top-decile symbols")
    if comparison.get("primary_top_decile_count") != len(selected_symbols):
        raise ValueError("H021 top-decile count disagrees with membership")
    eligible = []
    for row in observations:
        if row.get("primary_signal_available") is True:
            if row.get("primary_signal_reason") != "ELIGIBLE":
                raise ValueError("inconsistent H021 eligibility reason")
            if min(
                row.get("analyst_count_prior") or 0,
                row.get("analyst_count_current") or 0,
            ) < PRIMARY_MIN_ANALYST_COUNT:
                raise ValueError("frozen analyst primary threshold changed")
            value = row.get("eps_revision_pct")
            if type(value) not in (float, int) or not math.isfinite(value):
                raise ValueError("eligible EPS revision must be finite")
            eligible.append(row)
        elif row.get("primary_signal_available") is not False:
            raise ValueError("missing primary eligibility status")
    if len(eligible) != comparison.get("primary_signal_available_count"):
        raise ValueError("H021 eligible observation count changed")
    expected_base = math.ceil(0.1 * len(eligible)) if eligible else 0
    if not expected_base:
        if selected_symbols:
            raise ValueError("top decile cannot exist without eligible EPS")
    else:
        cutoff = sorted((row["eps_revision_pct"] for row in eligible), reverse=True)[
            expected_base - 1
        ]
        expected_symbols = {
            row["symbol"] for row in eligible if row["eps_revision_pct"] >= cutoff
        }
        if expected_symbols != set(selected_symbols):
            raise ValueError("primary EPS top-decile/tie rule changed")
        if comparison.get("primary_top_decile_cutoff_eps_revision_pct") != cutoff:
            raise ValueError("frozen top-decile cutoff changed")
    if not set(selected_symbols).issubset(by_observation):
        raise ValueError("selected H021 symbol is missing")

    packet: dict[str, Any] = {
        "schema_version": 1,
        "rule_id": RULE_ID,
        "intent_id": f"H021-P005-{current_day}-PRIMARY-ENTRY-v1",
        "classification": "NEXT_OPEN_OUTCOME_BLIND_RESEARCH_INTENT_NOT_PORTFOLIO",
        "prepared_at_utc": prepared.isoformat().replace("+00:00", "Z"),
        "source": {
            "comparison_date_ist": current_day,
            "prior_capture_date_ist": prior_day,
            "capture_interval_days": comparison["capture_interval_days"],
            "comparison_raw_sha256": comparison_raw_sha256,
            "capture_manifest_raw_sha256": manifest_raw_sha256,
            "source_version": comparison["source_version"],
            "universe_git_blob_sha": EXPECTED_UNIVERSE_GIT_BLOB,
            "calendar_git_blob_sha": EXPECTED_CALENDAR_GIT_BLOB,
        },
        "universe_symbol_count": 100,
        "eligible_count": len(eligible),
        "selected_count": len(selected_symbols),
        "selected_observations": [
            {
                "symbol": symbol,
                "isin": by_symbol[symbol]["isin"],
                "eps_revision_pct": by_observation[symbol]["eps_revision_pct"],
                "entry_price": None,
                "entry_status": "UNOBSERVED",
                "capital_weight": None,
            }
            for symbol in selected_symbols
        ],
        "planned_entry": {
            "session_date_ist": future_sessions[0]["session_date"],
            "open_timestamp_utc": next_open.isoformat().replace("+00:00", "Z"),
            "price_proxy": "NEXT_COMPLETED_SESSION_FIRST_EXECUTABLE_OPEN",
            "actual_execution_verified": False,
        },
        "primary_horizon_completed_sessions": 60,
        "secondary_horizon_completed_sessions": 20,
        "benchmark_family": "NIFTY_500",
        "stock_corporate_actions_audited": False,
        "benchmark_total_return_basis_audited": False,
        "return_outcomes_opened": False,
        "trades_executed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = _sha(packet)
    return packet
