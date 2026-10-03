from __future__ import annotations

import pytest

from marketlab.dr001_h021_gate import build_tier_a_h021_gate


def _dossiers() -> dict:
    return {
        "schema_version": 1,
        "pack_id": "TEST-TIER-A-v1",
        "classification": "POINT_IN_TIME_RESEARCH_DOSSIER_NOT_FORECAST",
        "next_common_gate": {"id": "H021_28D_REVISION"},
        "companies": [
            {"symbol": "AAA", "archetype": "A", "research_state": "WATCH"},
            {"symbol": "BBB", "archetype": "B", "research_state": "WATCH"},
            {"symbol": "CCC", "archetype": "C", "research_state": "WATCH"},
            {"symbol": "DDD", "archetype": "D", "research_state": "WATCH"},
            {"symbol": "EEE", "archetype": "E", "research_state": "WATCH"},
        ],
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _row(
    symbol: str,
    revision: float | None,
    *,
    available: bool = True,
    reason: str = "ELIGIBLE",
) -> dict:
    return {
        "symbol": symbol,
        "prior_capture_date": "2026-09-11",
        "current_capture_date": "2026-10-09",
        "capture_interval_days": 28,
        "eps_revision_pct": revision,
        "analyst_count_prior": 8,
        "analyst_count_current": 9,
        "primary_signal_available": available,
        "primary_signal_reason": reason,
    }


def _comparison() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "prior_capture_date_ist": "2026-09-11",
        "current_capture_date_ist": "2026-10-09",
        "capture_interval_days": 28,
        "source_version": "source-v1",
        "universe_path": "research/prospective/universes/u001.json",
        "universe_git_blob_sha": "abc123",
        "primary_signal": "28-35 day same-period consensus EPS revision",
        "primary_top_decile_symbols": ["AAA"],
        "revision_observations": [
            _row("AAA", 5.0),
            _row("BBB", 2.0),
            _row("CCC", 0.0),
            _row("DDD", -3.0),
            _row(
                "EEE",
                None,
                available=False,
                reason="PERIOD_END_MISMATCH",
            ),
        ],
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }


def test_gate_routes_only_positive_primary_top_decile_to_valuation() -> None:
    result = build_tier_a_h021_gate(
        _dossiers(),
        _comparison(),
        dossier_path="dossiers.json",
        comparison_path="comparison.json",
        dossier_sha256="dossier-sha",
        comparison_sha256="comparison-sha",
    )

    rows = {row["symbol"]: row for row in result["companies"]}
    assert rows["AAA"]["gate_state"] == "STRONG_POSITIVE_PRIMARY"
    assert rows["AAA"]["research_action"] == "ADVANCE_TO_VALUATION_AND_RED_TEAM"
    assert rows["AAA"]["valuation_red_team_allowed"] is True

    assert rows["BBB"]["gate_state"] == "POSITIVE_NOT_PRIMARY"
    assert rows["BBB"]["valuation_red_team_allowed"] is False
    assert rows["CCC"]["gate_state"] == "FLAT"
    assert rows["DDD"]["gate_state"] == "NEGATIVE"
    assert rows["EEE"]["gate_state"] == "NO_PRIMARY_SIGNAL"

    assert result["outcomes_opened"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
    assert result["action_counts"]["ADVANCE_TO_VALUATION_AND_RED_TEAM"] == 1


def test_relative_top_decile_cannot_advance_when_revision_is_nonpositive() -> None:
    comparison = _comparison()
    comparison["primary_top_decile_symbols"] = ["DDD"]

    result = build_tier_a_h021_gate(
        _dossiers(),
        comparison,
        dossier_path="dossiers.json",
        comparison_path="comparison.json",
        dossier_sha256="dossier-sha",
        comparison_sha256="comparison-sha",
    )

    rows = {row["symbol"]: row for row in result["companies"]}
    assert rows["DDD"]["gate_state"] == "RELATIVE_TOP_DECILE_NONPOSITIVE"
    assert rows["DDD"]["research_action"] == "THESIS_CHALLENGE_REMAIN_WATCH"
    assert rows["DDD"]["valuation_red_team_allowed"] is False


def test_ineligible_low_coverage_diagnostic_revision_does_not_advance() -> None:
    comparison = _comparison()
    comparison["revision_observations"][-1] = _row(
        "EEE",
        4.0,
        available=False,
        reason="ANALYST_COVERAGE_LT_5",
    )

    result = build_tier_a_h021_gate(
        _dossiers(),
        comparison,
        dossier_path="dossiers.json",
        comparison_path="comparison.json",
        dossier_sha256="dossier-sha",
        comparison_sha256="comparison-sha",
    )

    row = next(row for row in result["companies"] if row["symbol"] == "EEE")
    assert row["eps_revision_pct"] == 4.0
    assert row["gate_state"] == "NO_PRIMARY_SIGNAL"
    assert row["valuation_red_team_allowed"] is False


def test_gate_fails_closed_on_missing_tier_a_symbol() -> None:
    comparison = _comparison()
    comparison["revision_observations"] = [
        row for row in comparison["revision_observations"] if row["symbol"] != "EEE"
    ]

    with pytest.raises(ValueError, match="missing Tier A symbols"):
        build_tier_a_h021_gate(
            _dossiers(),
            comparison,
            dossier_path="dossiers.json",
            comparison_path="comparison.json",
            dossier_sha256="dossier-sha",
            comparison_sha256="comparison-sha",
        )


def test_gate_refuses_portfolio_eligible_dossier_pack() -> None:
    dossiers = _dossiers()
    dossiers["portfolio_eligibility_allowed"] = True

    with pytest.raises(ValueError, match="portfolio_eligibility_allowed=false"):
        build_tier_a_h021_gate(
            dossiers,
            _comparison(),
            dossier_path="dossiers.json",
            comparison_path="comparison.json",
            dossier_sha256="dossier-sha",
            comparison_sha256="comparison-sha",
        )
