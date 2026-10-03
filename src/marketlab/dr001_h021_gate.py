from __future__ import annotations

from collections import Counter
from typing import Any


GATE_ID = "DR001-H021-TIER-A-GATE-v1"
EXPECTED_H021_SIGNAL = "28-35 day same-period consensus EPS revision"


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_false(payload: dict[str, Any], field: str, label: str) -> None:
    if payload.get(field) is not False:
        raise ValueError(f"{label} requires {field}=false")


def _validate_dossier_pack(dossiers: dict[str, Any]) -> list[dict[str, Any]]:
    if dossiers.get("schema_version") != 1:
        raise ValueError("dossier pack schema_version must equal 1")
    if dossiers.get("classification") != "POINT_IN_TIME_RESEARCH_DOSSIER_NOT_FORECAST":
        raise ValueError("unexpected dossier classification")
    _require_false(dossiers, "portfolio_eligibility_allowed", "DR001 Tier A gate")
    _require_false(dossiers, "live_capital_allowed", "DR001 Tier A gate")

    next_gate = dossiers.get("next_common_gate")
    if not isinstance(next_gate, dict) or next_gate.get("id") != "H021_28D_REVISION":
        raise ValueError("dossier pack must name H021_28D_REVISION as next_common_gate")

    companies = dossiers.get("companies")
    if not isinstance(companies, list) or not companies:
        raise ValueError("dossier pack companies must be a non-empty list")

    symbols: list[str] = []
    for company in companies:
        if not isinstance(company, dict):
            raise ValueError("each dossier company must be an object")
        symbol = company.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("each dossier company requires a non-empty symbol")
        symbols.append(symbol)
    if len(symbols) != len(set(symbols)):
        raise ValueError("dossier symbols must be unique")
    return companies


def _validate_comparison(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    if comparison.get("schema_version") != 1:
        raise ValueError("H021 comparison schema_version must equal 1")
    if comparison.get("hypothesis_id") != "H021":
        raise ValueError("comparison hypothesis_id must equal H021")
    if comparison.get("primary_signal") != EXPECTED_H021_SIGNAL:
        raise ValueError("comparison primary_signal does not match frozen H021 contract")
    _require_false(comparison, "outcomes_opened", "DR001 Tier A gate")
    _require_false(comparison, "live_capital_allowed", "DR001 Tier A gate")

    observations = comparison.get("revision_observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("comparison revision_observations must be a non-empty list")

    symbols: list[str] = []
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError("each revision observation must be an object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("each revision observation requires a symbol")
        symbols.append(symbol)
    if len(symbols) != len(set(symbols)):
        raise ValueError("comparison revision symbols must be unique")

    top_decile = comparison.get("primary_top_decile_symbols")
    if not isinstance(top_decile, list) or not all(
        isinstance(symbol, str) and symbol for symbol in top_decile
    ):
        raise ValueError("primary_top_decile_symbols must be a list of symbols")
    if not set(top_decile).issubset(set(symbols)):
        raise ValueError("primary_top_decile_symbols must exist in revision_observations")

    return observations


def _classify(row: dict[str, Any], *, in_primary_top_decile: bool) -> tuple[str, str]:
    available = row.get("primary_signal_available")
    reason = row.get("primary_signal_reason")
    revision = row.get("eps_revision_pct")

    if available is not True:
        if revision is not None:
            raise ValueError("ineligible H021 row must not carry eps_revision_pct")
        if not isinstance(reason, str) or not reason:
            raise ValueError("ineligible H021 row requires primary_signal_reason")
        return "NO_PRIMARY_SIGNAL", "REMAIN_WATCH_DATA_INCOMPATIBLE"

    if reason != "ELIGIBLE":
        raise ValueError("eligible H021 row must use primary_signal_reason=ELIGIBLE")
    if not _is_number(revision):
        raise ValueError("eligible H021 row requires numeric eps_revision_pct")

    revision_value = float(revision)
    if revision_value > 0 and in_primary_top_decile:
        return "STRONG_POSITIVE_PRIMARY", "ADVANCE_TO_VALUATION_AND_RED_TEAM"
    if revision_value > 0:
        return "POSITIVE_NOT_PRIMARY", "REMAIN_WATCH_POSITIVE_NOT_PRIMARY"
    if revision_value == 0:
        return "FLAT", "THESIS_CHALLENGE_REMAIN_WATCH"
    if in_primary_top_decile:
        return "RELATIVE_TOP_DECILE_NONPOSITIVE", "THESIS_CHALLENGE_REMAIN_WATCH"
    return "NEGATIVE", "THESIS_CHALLENGE_REMAIN_WATCH"


def build_tier_a_h021_gate(
    dossiers: dict[str, Any],
    comparison: dict[str, Any],
    *,
    dossier_path: str,
    comparison_path: str,
    dossier_sha256: str,
    comparison_sha256: str,
) -> dict[str, Any]:
    companies = _validate_dossier_pack(dossiers)
    observations = _validate_comparison(comparison)

    observation_by_symbol = {row["symbol"]: row for row in observations}
    target_symbols = [company["symbol"] for company in companies]
    missing = [symbol for symbol in target_symbols if symbol not in observation_by_symbol]
    if missing:
        raise ValueError(f"H021 comparison is missing Tier A symbols: {missing}")

    top_decile = set(comparison["primary_top_decile_symbols"])
    output_rows: list[dict[str, Any]] = []
    for company in companies:
        symbol = company["symbol"]
        row = observation_by_symbol[symbol]
        in_primary_top_decile = symbol in top_decile
        gate_state, research_action = _classify(
            row, in_primary_top_decile=in_primary_top_decile
        )
        output_rows.append(
            {
                "symbol": symbol,
                "archetype": company.get("archetype"),
                "prior_research_state": company.get("research_state"),
                "prior_capture_date": row.get("prior_capture_date"),
                "current_capture_date": row.get("current_capture_date"),
                "capture_interval_days": row.get("capture_interval_days"),
                "eps_revision_pct": row.get("eps_revision_pct"),
                "analyst_count_prior": row.get("analyst_count_prior"),
                "analyst_count_current": row.get("analyst_count_current"),
                "primary_signal_available": row.get("primary_signal_available"),
                "primary_signal_reason": row.get("primary_signal_reason"),
                "primary_top_decile": in_primary_top_decile,
                "gate_state": gate_state,
                "research_action": research_action,
                "valuation_red_team_allowed": (
                    research_action == "ADVANCE_TO_VALUATION_AND_RED_TEAM"
                ),
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    state_counts = Counter(row["gate_state"] for row in output_rows)
    action_counts = Counter(row["research_action"] for row in output_rows)

    return {
        "schema_version": 1,
        "gate_id": GATE_ID,
        "classification": "RESEARCH_ROUTING_ONLY_NOT_RETURN_FORECAST",
        "dossier_pack_id": dossiers["pack_id"],
        "dossier_path": dossier_path,
        "dossier_sha256": dossier_sha256,
        "comparison_path": comparison_path,
        "comparison_sha256": comparison_sha256,
        "prior_capture_date_ist": comparison.get("prior_capture_date_ist"),
        "current_capture_date_ist": comparison.get("current_capture_date_ist"),
        "capture_interval_days": comparison.get("capture_interval_days"),
        "source_version": comparison.get("source_version"),
        "universe_path": comparison.get("universe_path"),
        "universe_git_blob_sha": comparison.get("universe_git_blob_sha"),
        "frozen_rule": {
            "strong_positive_primary": (
                "primary H021 signal is eligible, EPS revision is strictly positive, "
                "and symbol is in the H021 primary top decile"
            ),
            "positive_not_primary": (
                "eligible EPS revision is strictly positive but symbol is not in the "
                "H021 primary top decile"
            ),
            "nonpositive": "eligible EPS revision is zero or negative",
            "no_primary_signal": "H021 primary signal is unavailable or incompatible",
            "routing": (
                "only STRONG_POSITIVE_PRIMARY advances to valuation and red-team review; "
                "all other states remain research WATCH/challenge states"
            ),
        },
        "state_counts": dict(sorted(state_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "companies": output_rows,
        "outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
