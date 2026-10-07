from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg006_base_rates import (
    HORIZONS,
    TERMINAL_CENSORED,
    TERMINAL_COMPLETED,
    TERMINAL_FAILED,
    SurvivalEpisode,
    episode_from_dates,
    estimate_competing_risk_base_rate,
    publication_gate,
)

EXECUTION_ID = "HG006-D004-P1-v1"
EXPECTED_LABELER_ID = "HG006-D002-P1-v1"
EXPECTED_LABEL_PANEL_SHA = (
    "545532620b409135bd867f633de708cfd441e2c532a5b790afeacef9c7de9874"
)
EXPECTED_EPISODE_COUNT = 333
CONFLICT = "UNRESOLVED_SOURCE_CONFLICT"

ELIGIBLE_STAGES = (
    "BOARD_APPROVED",
    "SHAREHOLDER_APPROVED",
    "REGULATORY_OR_COURT_APPROVED",
    "PUBLIC_ANNOUNCEMENT",
    "RECORD_DATE_FIXED",
    "OFFER_OPEN",
    "OFFER_CLOSED",
    "ALLOTMENT_COMPLETED",
)

TRACK_SPECS: dict[tuple[str, str], dict[str, Any]] = {
    ("SCHEME_REORGANISATION", "transaction_completion"): {
        "terminal_source": "primary",
        "stages": ELIGIBLE_STAGES,
    },
    ("PREFERENTIAL_WARRANT", "issuance_completion"): {
        "terminal_source": "primary",
        "stages": tuple(
            stage for stage in ELIGIBLE_STAGES if stage != "ALLOTMENT_COMPLETED"
        ),
    },
    ("PREFERENTIAL_WARRANT", "full_economic_exercise"): {
        "terminal_source": "full_economic_exercise",
        "stages": ELIGIBLE_STAGES,
    },
}


def _iso(value: object, field: str) -> date:
    if not isinstance(value, str) or not value:
        raise AlphaContractError(f"HG006 D004 {field} must be ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError(f"HG006 D004 {field} must be ISO date") from exc


def _validate_panel(panel: dict[str, Any]) -> list[dict[str, Any]]:
    if panel.get("labeler_id") != EXPECTED_LABELER_ID:
        raise AlphaContractError("HG006 D004 requires frozen D002-P1 labeler")
    if panel.get("label_panel_sha256") != EXPECTED_LABEL_PANEL_SHA:
        raise AlphaContractError("HG006 D004 label panel SHA mismatch")
    if panel.get("episode_count") != EXPECTED_EPISODE_COUNT:
        raise AlphaContractError("HG006 D004 episode count mismatch")
    if panel.get("historical_terminal_labels_opened") is not True:
        raise AlphaContractError("HG006 D004 requires opened historical terminal labels")
    if panel.get("completion_probabilities_assigned") is not False:
        raise AlphaContractError("HG006 D004 refuses preassigned probabilities")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if panel.get(field) is not False:
            raise AlphaContractError(f"HG006 D004 requires {field}=false")
    rows = panel.get("episodes")
    if not isinstance(rows, list) or len(rows) != EXPECTED_EPISODE_COUNT:
        raise AlphaContractError("HG006 D004 episode rows unavailable")
    ids = [str(row.get("episode_id") or "") for row in rows if isinstance(row, dict)]
    if len(ids) != EXPECTED_EPISODE_COUNT or len(set(ids)) != EXPECTED_EPISODE_COUNT:
        raise AlphaContractError("HG006 D004 episode identities must be unique")
    return rows


def _track_terminal(
    row: dict[str, Any],
    *,
    terminal_source: str,
) -> tuple[str, str | None]:
    if terminal_source == "primary":
        state = row.get("primary_terminal_state")
        terminal_date = row.get("primary_terminal_date")
    elif terminal_source == "full_economic_exercise":
        block = row.get("full_economic_exercise")
        if not isinstance(block, dict):
            raise AlphaContractError("HG006 D004 warrant full-exercise track missing")
        state = block.get("terminal_state")
        terminal_date = block.get("terminal_date")
    else:
        raise AlphaContractError("HG006 D004 unknown terminal source")
    if state not in {
        TERMINAL_COMPLETED,
        TERMINAL_FAILED,
        TERMINAL_CENSORED,
        CONFLICT,
    }:
        raise AlphaContractError(f"HG006 D004 invalid terminal state: {state}")
    if terminal_date is not None and not isinstance(terminal_date, str):
        raise AlphaContractError("HG006 D004 terminal date must be string or null")
    return str(state), terminal_date


def _track_rows(
    rows: list[dict[str, Any]],
    *,
    family: str,
) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("family") == family]


def _supported_horizons(episodes: list[SurvivalEpisode]) -> tuple[int, ...]:
    if not episodes:
        return ()
    max_duration = max(row.duration_days for row in episodes)
    return tuple(horizon for horizon in HORIZONS if max_duration >= horizon)


def _horizon_surface(
    estimator: dict[str, Any],
    *,
    supported_horizons: tuple[int, ...],
    publication_state: str,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    supported = set(supported_horizons)
    for horizon in HORIZONS:
        key = str(horizon)
        if publication_state != "PUBLISHABLE_HISTORICAL_BASE_RATE":
            output[key] = {
                "state": "NOT_PUBLISHED_SUPPORT",
                "estimate": None,
            }
        elif horizon not in supported:
            output[key] = {
                "state": "INSUFFICIENT_FOLLOW_UP",
                "estimate": None,
            }
        else:
            output[key] = {
                "state": "PUBLISHED",
                "estimate": estimator["aalen_johansen"][key],
            }
    return output


def _counts(episodes: list[SurvivalEpisode]) -> dict[str, int]:
    counter = Counter(row.terminal_state for row in episodes)
    return {
        "support_count": len(episodes),
        "completed_count": counter[TERMINAL_COMPLETED],
        "failed_count": counter[TERMINAL_FAILED],
        "right_censored_count": counter[TERMINAL_CENSORED],
        "terminal_count": counter[TERMINAL_COMPLETED] + counter[TERMINAL_FAILED],
    }


def _family_surface(
    rows: list[dict[str, Any]],
    *,
    family: str,
    track_name: str,
    terminal_source: str,
    observation_cutoff: str,
) -> dict[str, Any]:
    source_rows = _track_rows(rows, family=family)
    conflicts = []
    episodes: list[SurvivalEpisode] = []
    for row in source_rows:
        state, terminal_date = _track_terminal(row, terminal_source=terminal_source)
        if state == CONFLICT:
            conflicts.append(str(row["episode_id"]))
            continue
        episodes.append(
            episode_from_dates(
                episode_id=str(row["episode_id"]),
                entry_date=str(row["entry_date"]),
                terminal_state=state,
                terminal_date=terminal_date,
                observation_cutoff=observation_cutoff,
            )
        )

    counts = _counts(episodes)
    publication_state = (
        "PUBLISHABLE_HISTORICAL_BASE_RATE"
        if counts["support_count"] >= 30
        else "INSUFFICIENT_HISTORICAL_SUPPORT"
    )
    supported_horizons = _supported_horizons(episodes)
    estimator = (
        estimate_competing_risk_base_rate(
            episodes,
            horizons=supported_horizons,
        )
        if publication_state == "PUBLISHABLE_HISTORICAL_BASE_RATE"
        else None
    )
    return {
        "family": family,
        "track": track_name,
        "source_episode_count": len(source_rows),
        "conflict_excluded_count": len(conflicts),
        "conflict_episode_ids": sorted(conflicts),
        **counts,
        "publication_state": publication_state,
        "supported_horizons": list(supported_horizons),
        "resolved_completion_fraction": (
            estimator["resolved_completion_fraction"] if estimator else None
        ),
        "resolved_completion_wilson95": (
            estimator["resolved_completion_wilson95"] if estimator else None
        ),
        "horizons": _horizon_surface(
            estimator or {"aalen_johansen": {}},
            supported_horizons=supported_horizons,
            publication_state=publication_state,
        ),
        "bootstrap": (
            estimator["bootstrap"]
            if estimator
            else {
                "resamples": 2000,
                "seed": 606001,
                "method": "EPISODE_LEVEL_NONPARAMETRIC_PERCENTILE",
            }
        ),
    }


def _stage_surface(
    rows: list[dict[str, Any]],
    *,
    family: str,
    track_name: str,
    terminal_source: str,
    stage: str,
    observation_cutoff: str,
) -> dict[str, Any]:
    source_rows = _track_rows(rows, family=family)
    conflicts = 0
    episodes: list[SurvivalEpisode] = []
    cutoff = _iso(observation_cutoff, "observation_cutoff")

    for row in source_rows:
        state, terminal_date = _track_terminal(row, terminal_source=terminal_source)
        if state == CONFLICT:
            conflicts += 1
            continue
        stage_dates = row.get("first_observed_stage_dates")
        if not isinstance(stage_dates, dict):
            raise AlphaContractError("HG006 D004 stage dates unavailable")
        stage_date_raw = stage_dates.get(stage)
        if stage_date_raw is None:
            continue
        stage_day = _iso(stage_date_raw, f"{stage}.stage_date")
        entry_day = _iso(row.get("entry_date"), "entry_date")
        if stage_day < entry_day or stage_day > cutoff:
            raise AlphaContractError("HG006 D004 stage date outside observed interval")

        if state in {TERMINAL_COMPLETED, TERMINAL_FAILED}:
            if terminal_date is None:
                raise AlphaContractError("HG006 D004 terminal episode missing date")
            terminal_day = _iso(terminal_date, "terminal_date")
            if stage_day > terminal_day:
                continue

        episodes.append(
            episode_from_dates(
                episode_id=str(row["episode_id"]),
                entry_date=stage_day.isoformat(),
                terminal_state=state,
                terminal_date=terminal_date,
                observation_cutoff=observation_cutoff,
            )
        )

    counts = _counts(episodes)
    publication_state = publication_gate(
        support_count=counts["support_count"],
        terminal_count=counts["terminal_count"],
    )
    supported_horizons = _supported_horizons(episodes)
    estimator = (
        estimate_competing_risk_base_rate(
            episodes,
            horizons=supported_horizons,
        )
        if publication_state == "PUBLISHABLE_HISTORICAL_BASE_RATE"
        else None
    )
    return {
        "family": family,
        "track": track_name,
        "stage": stage,
        "source_family_episode_count": len(source_rows),
        "conflict_excluded_count": conflicts,
        **counts,
        "publication_state": publication_state,
        "supported_horizons": list(supported_horizons),
        "resolved_completion_fraction": (
            estimator["resolved_completion_fraction"] if estimator else None
        ),
        "resolved_completion_wilson95": (
            estimator["resolved_completion_wilson95"] if estimator else None
        ),
        "horizons": _horizon_surface(
            estimator or {"aalen_johansen": {}},
            supported_horizons=supported_horizons,
            publication_state=publication_state,
        ),
        "bootstrap": (
            estimator["bootstrap"]
            if estimator
            else {
                "resamples": 2000,
                "seed": 606001,
                "method": "EPISODE_LEVEL_NONPARAMETRIC_PERCENTILE",
            }
        ),
    }


def build_d004_base_rates(label_panel: dict[str, Any]) -> dict[str, Any]:
    rows = _validate_panel(label_panel)
    observation_cutoff = str(label_panel["observation_cutoff"])
    family_surfaces = []
    stage_surfaces = []

    for (family, track_name), spec in TRACK_SPECS.items():
        terminal_source = str(spec["terminal_source"])
        family_surfaces.append(
            _family_surface(
                rows,
                family=family,
                track_name=track_name,
                terminal_source=terminal_source,
                observation_cutoff=observation_cutoff,
            )
        )
        for stage in spec["stages"]:
            stage_surfaces.append(
                _stage_surface(
                    rows,
                    family=family,
                    track_name=track_name,
                    terminal_source=terminal_source,
                    stage=stage,
                    observation_cutoff=observation_cutoff,
                )
            )

    output = {
        "schema_version": 1,
        "estimator_id": EXECUTION_ID,
        "classification": "HISTORICAL_STAGE_CONDITIONED_BASE_RATES_NOT_CURRENT_PROBABILITIES",
        "source_label_panel_sha256": EXPECTED_LABEL_PANEL_SHA,
        "observation_cutoff": observation_cutoff,
        "bootstrap_resamples": 2000,
        "bootstrap_seed": 606001,
        "candidate_horizons_days": list(HORIZONS),
        "family_surfaces": sorted(
            family_surfaces,
            key=lambda row: (row["family"], row["track"]),
        ),
        "stage_surfaces": sorted(
            stage_surfaces,
            key=lambda row: (row["family"], row["track"], row["stage"]),
        ),
        "threshold_passes": {
            "exact_333_episode_source": len(rows) == EXPECTED_EPISODE_COUNT,
            "conflicts_excluded_not_failed": all(
                surface["support_count"] + surface["conflict_excluded_count"]
                == surface["source_episode_count"]
                for surface in family_surfaces
            ),
            "warrant_tracks_distinct": {
                surface["track"]
                for surface in family_surfaces
                if surface["family"] == "PREFERENTIAL_WARRANT"
            }
            == {"issuance_completion", "full_economic_exercise"},
            "no_current_probability_assigned": True,
            "return_outcomes_remain_closed": True,
        },
        "historical_base_rates_opened": True,
        "current_company_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["feasibility_pass"] = all(output["threshold_passes"].values())
    output["promotion_allowed_to_current_probability_mapping"] = output[
        "feasibility_pass"
    ]
    output["base_rate_panel_sha256"] = digest(output)
    return output
