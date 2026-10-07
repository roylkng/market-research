from __future__ import annotations

from collections import Counter
from datetime import date, datetime
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

MAPPER_ID = "HG006-P001-v1"
CURRENT_EVIDENCE_CUTOFF = date(2026, 10, 4)

EXPECTED_D004_SHA = "08eddc18599b7dcd86c4a688ef46fc6161a1a52cb49b72cf6695ffbc43ce3084"
EXPECTED_LABEL_SHA = "545532620b409135bd867f633de708cfd441e2c532a5b790afeacef9c7de9874"
EXPECTED_D001_SELECTION_SHA = "9b82b337b02d5aa2c58164bf888f76ce50fcd34680077f87f13b0ff5cfc7c102"
EXPECTED_L001_RUN_SHA = "a402b39a8890cd2fac3218bb94673f8b9c00b1f325315f9ec93863c22d9a1d12"
EXPECTED_L002_SYNTHESIS_SHA = "6bd1a43d29460fc18389dfdcb7241c95d1de0acb80b769a728946ef81c031683"

CONFLICT = "UNRESOLVED_SOURCE_CONFLICT"

STAGE_RANK = {
    "PUBLIC_ANNOUNCEMENT": 1,
    "BOARD_APPROVED": 2,
    "SHAREHOLDER_APPROVED": 3,
    "REGULATORY_OR_COURT_APPROVED": 4,
    "RECORD_DATE_FIXED": 5,
    "OFFER_OPEN": 6,
    "OFFER_CLOSED": 7,
    "ALLOTMENT_COMPLETED": 8,
}

LANE_MAPPING = {
    "DEMERGER_ENTITLEMENT": {
        "family": "SCHEME_REORGANISATION",
        "tracks": ("transaction_completion",),
    },
    "DILUTION_FINANCING": {
        "family": "PREFERENTIAL_WARRANT",
        "tracks": ("issuance_completion", "full_economic_exercise"),
    },
}


def _validate_sources(
    *,
    d001_selection: dict[str, Any],
    l001_run: dict[str, Any],
    l002_synthesis: dict[str, Any],
    d004_panel: dict[str, Any],
    historical_labels: dict[str, Any],
) -> None:
    if d001_selection.get("selection_sha256") != EXPECTED_D001_SELECTION_SHA:
        raise AlphaContractError("HG006 P001 HG004 D001 selection SHA mismatch")
    if l001_run.get("run_sha256") != EXPECTED_L001_RUN_SHA:
        raise AlphaContractError("HG006 P001 HG004 L001 run SHA mismatch")
    if l002_synthesis.get("synthesis_sha256") != EXPECTED_L002_SYNTHESIS_SHA:
        raise AlphaContractError("HG006 P001 HG004 L002 synthesis SHA mismatch")
    if d004_panel.get("base_rate_panel_sha256") != EXPECTED_D004_SHA:
        raise AlphaContractError("HG006 P001 D004 base-rate SHA mismatch")
    if historical_labels.get("label_panel_sha256") != EXPECTED_LABEL_SHA:
        raise AlphaContractError("HG006 P001 historical label SHA mismatch")

    if d001_selection.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 P001 current selection opened returns")
    if l001_run.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 P001 current L001 opened returns")
    if l002_synthesis.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 P001 current L002 opened returns")
    if d004_panel.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 P001 D004 opened returns")
    if historical_labels.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 P001 historical labels opened returns")
    if d004_panel.get("current_company_probabilities_assigned") is not False:
        raise AlphaContractError("HG006 P001 refuses preassigned current probabilities")


def _utc_day(timestamp: object) -> date:
    if not isinstance(timestamp, str) or not timestamp:
        raise AlphaContractError("HG006 P001 event timestamp unavailable")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlphaContractError("HG006 P001 event timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("HG006 P001 event timestamp lacks timezone")
    return parsed.date()


def _event_date_index(selection: dict[str, Any]) -> dict[str, date]:
    rows = selection.get("event_links")
    if not isinstance(rows, list):
        raise AlphaContractError("HG006 P001 event links unavailable")
    result: dict[str, date] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 P001 event link must be object")
        event_id = str(row.get("announcement_id") or "")
        if not event_id or event_id in result:
            raise AlphaContractError("HG006 P001 event IDs must be unique")
        observed = _utc_day(row.get("exchange_published_at_utc"))
        if observed > CURRENT_EVIDENCE_CUTOFF:
            raise AlphaContractError("HG006 P001 current evidence exceeds frozen cutoff")
        result[event_id] = observed
    return result


def _l001_document_index(
    l001_run: dict[str, Any],
    *,
    event_dates: dict[str, date],
) -> dict[str, dict[str, Any]]:
    rows = l001_run.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("HG006 P001 L001 rows unavailable")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 P001 L001 row must be object")
        document_id = str(row.get("document_id") or "")
        if not document_id or document_id in result:
            raise AlphaContractError("HG006 P001 document IDs must be unique")
        extraction = row.get("validated_extraction")
        if not isinstance(extraction, dict):
            raise AlphaContractError("HG006 P001 validated extraction unavailable")
        event_ids = extraction.get("event_ids")
        if not isinstance(event_ids, list) or not event_ids:
            raise AlphaContractError("HG006 P001 extraction event IDs unavailable")
        missing = [event_id for event_id in event_ids if event_id not in event_dates]
        if missing:
            raise AlphaContractError(
                f"HG006 P001 extraction events missing from selection: {missing}"
            )
        result[document_id] = {
            "document_id": document_id,
            "symbols": list(extraction.get("symbols") or []),
            "economic_relevance": extraction.get("economic_relevance"),
            "transaction_families": list(
                extraction.get("transaction_families") or []
            ),
            "transaction_stage": extraction.get("transaction_stage"),
            "event_ids": list(event_ids),
            "observed_date": min(event_dates[event_id] for event_id in event_ids),
        }
    return result


def _d004_stage_index(d004_panel: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    rows = d004_panel.get("stage_surfaces")
    if not isinstance(rows, list):
        raise AlphaContractError("HG006 P001 D004 stage surfaces unavailable")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 P001 D004 stage row must be object")
        key = (
            str(row.get("family") or ""),
            str(row.get("track") or ""),
            str(row.get("stage") or ""),
        )
        if not all(key) or key in result:
            raise AlphaContractError("HG006 P001 D004 stage surface identity invalid")
        result[key] = row
    return result


def _track_terminal(row: dict[str, Any], track: str) -> tuple[str, str | None]:
    if track in {"transaction_completion", "issuance_completion"}:
        return (
            str(row.get("primary_terminal_state") or ""),
            row.get("primary_terminal_date"),
        )
    if track == "full_economic_exercise":
        block = row.get("full_economic_exercise")
        if not isinstance(block, dict):
            raise AlphaContractError("HG006 P001 historical full-exercise track missing")
        return str(block.get("terminal_state") or ""), block.get("terminal_date")
    raise AlphaContractError(f"HG006 P001 unsupported track: {track}")


def _historical_stage_episodes(
    historical_labels: dict[str, Any],
    *,
    family: str,
    track: str,
    stage: str,
) -> list[SurvivalEpisode]:
    rows = historical_labels.get("episodes")
    cutoff = str(historical_labels.get("observation_cutoff") or "")
    if not isinstance(rows, list) or not cutoff:
        raise AlphaContractError("HG006 P001 historical label rows unavailable")
    output: list[SurvivalEpisode] = []
    for row in rows:
        if row.get("family") != family:
            continue
        state, terminal_date = _track_terminal(row, track)
        if state == CONFLICT:
            continue
        if state not in {TERMINAL_COMPLETED, TERMINAL_FAILED, TERMINAL_CENSORED}:
            raise AlphaContractError("HG006 P001 historical terminal state invalid")
        stages = row.get("first_observed_stage_dates")
        if not isinstance(stages, dict):
            raise AlphaContractError("HG006 P001 historical stage dates unavailable")
        stage_date = stages.get(stage)
        if stage_date is None:
            continue
        if state in {TERMINAL_COMPLETED, TERMINAL_FAILED}:
            if terminal_date is None:
                raise AlphaContractError("HG006 P001 historical terminal date missing")
            if date.fromisoformat(str(stage_date)) > date.fromisoformat(str(terminal_date)):
                continue
        output.append(
            episode_from_dates(
                episode_id=str(row["episode_id"]),
                entry_date=str(stage_date),
                terminal_state=state,
                terminal_date=terminal_date,
                observation_cutoff=cutoff,
            )
        )
    return output


def _survivor_condition(
    episodes: list[SurvivalEpisode],
    *,
    elapsed_days: int,
) -> list[SurvivalEpisode]:
    if elapsed_days < 0:
        raise AlphaContractError("HG006 P001 elapsed days cannot be negative")
    output = []
    for row in episodes:
        if row.duration_days <= elapsed_days:
            continue
        output.append(
            SurvivalEpisode(
                episode_id=row.episode_id,
                duration_days=row.duration_days - elapsed_days,
                terminal_state=row.terminal_state,
            )
        )
    return output


def _supported_horizons(episodes: list[SurvivalEpisode]) -> tuple[int, ...]:
    if not episodes:
        return ()
    maximum = max(row.duration_days for row in episodes)
    return tuple(horizon for horizon in HORIZONS if maximum >= horizon)


def _counts(episodes: list[SurvivalEpisode]) -> dict[str, int]:
    counter = Counter(row.terminal_state for row in episodes)
    return {
        "support_count": len(episodes),
        "completed_count": counter[TERMINAL_COMPLETED],
        "failed_count": counter[TERMINAL_FAILED],
        "right_censored_count": counter[TERMINAL_CENSORED],
        "terminal_count": counter[TERMINAL_COMPLETED] + counter[TERMINAL_FAILED],
    }


def _current_lane_cases(
    *,
    l002_synthesis: dict[str, Any],
    document_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = l002_synthesis.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("HG006 P001 L002 rows unavailable")
    cases = []
    for company in rows:
        if not isinstance(company, dict):
            raise TypeError("HG006 P001 L002 company row must be object")
        symbol = str(company.get("symbol") or "")
        lanes = company.get("payoff_model_lanes")
        if not isinstance(lanes, list):
            raise AlphaContractError("HG006 P001 payoff lanes unavailable")
        for lane in lanes:
            if not isinstance(lane, dict):
                raise TypeError("HG006 P001 payoff lane must be object")
            lane_family = str(lane.get("economic_family") or "")
            mapping = LANE_MAPPING.get(lane_family)
            readiness = str(lane.get("readiness_state") or "")
            if mapping is None or not readiness.startswith("READY_"):
                continue
            document_ids = lane.get("evidence_document_ids")
            if not isinstance(document_ids, list) or not document_ids:
                raise AlphaContractError("HG006 P001 eligible lane lacks evidence documents")
            missing = [doc for doc in document_ids if doc not in document_index]
            if missing:
                raise AlphaContractError(
                    f"HG006 P001 lane documents missing from L001: {missing}"
                )
            family = str(mapping["family"])
            family_docs = []
            for document_id in document_ids:
                doc = document_index[str(document_id)]
                if doc["economic_relevance"] != "DIRECT_LISTED_SECURITY":
                    continue
                if family not in doc["transaction_families"]:
                    continue
                if symbol not in doc["symbols"]:
                    continue
                family_docs.append(doc)

            for track in mapping["tracks"]:
                cases.append(
                    {
                        "symbol": symbol,
                        "economic_lane": lane_family,
                        "readiness_state": readiness,
                        "historical_family": family,
                        "historical_track": track,
                        "evidence_document_ids": sorted(str(x) for x in document_ids),
                        "family_confirming_documents": family_docs,
                    }
                )
    return cases


def _terminal_current_state(case: dict[str, Any]) -> str | None:
    docs = case["family_confirming_documents"]
    stages = {str(doc.get("transaction_stage") or "") for doc in docs}
    track = case["historical_track"]
    if "CANCELLED_OR_WITHDRAWN" in stages:
        if "TRANSACTION_COMPLETED" in stages or (
            track == "issuance_completion" and "ALLOTMENT_COMPLETED" in stages
        ):
            return "CURRENT_SOURCE_CONFLICT"
        return "CURRENT_TERMINAL_FAILED_OR_WITHDRAWN"
    if case["historical_family"] == "SCHEME_REORGANISATION":
        if "TRANSACTION_COMPLETED" in stages:
            return "CURRENT_TERMINAL_COMPLETED"
    if (
        case["historical_family"] == "PREFERENTIAL_WARRANT"
        and track == "issuance_completion"
        and "ALLOTMENT_COMPLETED" in stages
    ):
        return "CURRENT_TERMINAL_COMPLETED"
    return None


def _current_stage(case: dict[str, Any]) -> tuple[str | None, date | None]:
    candidates: list[tuple[int, date, str]] = []
    for doc in case["family_confirming_documents"]:
        stage = str(doc.get("transaction_stage") or "")
        rank = STAGE_RANK.get(stage)
        if rank is None:
            continue
        candidates.append((rank, doc["observed_date"], stage))
    if not candidates:
        return None, None
    highest_rank = max(row[0] for row in candidates)
    highest = [row for row in candidates if row[0] == highest_rank]
    stage = highest[0][2]
    observed = min(row[1] for row in highest)
    return stage, observed


def _map_case(
    case: dict[str, Any],
    *,
    historical_labels: dict[str, Any],
    stage_index: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    base = {
        key: case[key]
        for key in (
            "symbol",
            "economic_lane",
            "readiness_state",
            "historical_family",
            "historical_track",
            "evidence_document_ids",
        )
    }
    base["family_confirming_document_ids"] = sorted(
        doc["document_id"] for doc in case["family_confirming_documents"]
    )

    if not case["family_confirming_documents"]:
        return {
            **base,
            "mapping_state": "NO_EXACT_HISTORICAL_FAMILY_MATCH",
            "probability_surface": None,
        }

    terminal = _terminal_current_state(case)
    stage, stage_date = _current_stage(case)
    if terminal is not None:
        return {
            **base,
            "mapping_state": terminal,
            "current_stage": stage,
            "current_stage_observed_date": (
                stage_date.isoformat() if stage_date is not None else None
            ),
            "elapsed_days": (
                (CURRENT_EVIDENCE_CUTOFF - stage_date).days
                if stage_date is not None
                else None
            ),
            "probability_surface": None,
        }

    if stage is None or stage_date is None:
        return {
            **base,
            "mapping_state": "NO_FROZEN_ELIGIBLE_STAGE",
            "probability_surface": None,
        }

    key = (
        case["historical_family"],
        case["historical_track"],
        stage,
    )
    d004_stage = stage_index.get(key)
    if (
        d004_stage is None
        or d004_stage.get("publication_state")
        != "PUBLISHABLE_HISTORICAL_BASE_RATE"
    ):
        return {
            **base,
            "mapping_state": "NO_PUBLISHABLE_EXACT_STAGE_BASE_RATE",
            "current_stage": stage,
            "current_stage_observed_date": stage_date.isoformat(),
            "elapsed_days": (CURRENT_EVIDENCE_CUTOFF - stage_date).days,
            "d004_exact_stage_publication_state": (
                d004_stage.get("publication_state")
                if isinstance(d004_stage, dict)
                else "STAGE_NOT_IN_D004"
            ),
            "probability_surface": None,
        }

    elapsed = (CURRENT_EVIDENCE_CUTOFF - stage_date).days
    historical = _historical_stage_episodes(
        historical_labels,
        family=case["historical_family"],
        track=case["historical_track"],
        stage=stage,
    )
    survivors = _survivor_condition(historical, elapsed_days=elapsed)
    counts = _counts(survivors)
    state = publication_gate(
        support_count=counts["support_count"],
        terminal_count=counts["terminal_count"],
    )
    if state != "PUBLISHABLE_HISTORICAL_BASE_RATE":
        return {
            **base,
            "mapping_state": "INSUFFICIENT_SURVIVOR_CONDITIONED_SUPPORT",
            "current_stage": stage,
            "current_stage_observed_date": stage_date.isoformat(),
            "elapsed_days": elapsed,
            "d004_exact_stage_publication_state": d004_stage[
                "publication_state"
            ],
            "survivor_conditioned_counts": counts,
            "probability_surface": None,
        }

    horizons = _supported_horizons(survivors)
    estimate = estimate_competing_risk_base_rate(
        survivors,
        horizons=horizons,
    )
    horizon_output = {}
    for horizon in HORIZONS:
        key_text = str(horizon)
        if horizon not in horizons:
            horizon_output[key_text] = {
                "state": "INSUFFICIENT_FOLLOW_UP",
                "estimate": None,
            }
        else:
            horizon_output[key_text] = {
                "state": "PUBLISHED",
                "estimate": estimate["aalen_johansen"][key_text],
            }

    return {
        **base,
        "mapping_state": "SURVIVOR_CONDITIONED_BASE_RATE_PUBLISHED",
        "current_stage": stage,
        "current_stage_observed_date": stage_date.isoformat(),
        "current_evidence_cutoff": CURRENT_EVIDENCE_CUTOFF.isoformat(),
        "elapsed_days": elapsed,
        "d004_exact_stage_publication_state": d004_stage["publication_state"],
        "historical_stage_support_before_conditioning": d004_stage[
            "support_count"
        ],
        "survivor_conditioned_counts": counts,
        "probability_surface": {
            "semantic_name": "survivor_conditioned_historical_completion_base_rate",
            "horizons": horizon_output,
            "bootstrap": estimate["bootstrap"],
        },
    }


def build_p001_current_mapping(
    *,
    d001_selection: dict[str, Any],
    l001_run: dict[str, Any],
    l002_synthesis: dict[str, Any],
    d004_panel: dict[str, Any],
    historical_labels: dict[str, Any],
) -> dict[str, Any]:
    _validate_sources(
        d001_selection=d001_selection,
        l001_run=l001_run,
        l002_synthesis=l002_synthesis,
        d004_panel=d004_panel,
        historical_labels=historical_labels,
    )
    event_dates = _event_date_index(d001_selection)
    document_index = _l001_document_index(l001_run, event_dates=event_dates)
    stage_index = _d004_stage_index(d004_panel)
    cases = _current_lane_cases(
        l002_synthesis=l002_synthesis,
        document_index=document_index,
    )
    mapped = [
        _map_case(
            case,
            historical_labels=historical_labels,
            stage_index=stage_index,
        )
        for case in cases
    ]
    state_counts = Counter(row["mapping_state"] for row in mapped)

    output = {
        "schema_version": 1,
        "mapper_id": MAPPER_ID,
        "classification": "CURRENT_TRANSACTION_HISTORICAL_BASE_RATE_MAPPING_NOT_EXPECTED_RETURN",
        "current_evidence_cutoff": CURRENT_EVIDENCE_CUTOFF.isoformat(),
        "source_d004_sha256": EXPECTED_D004_SHA,
        "source_historical_label_sha256": EXPECTED_LABEL_SHA,
        "source_hg004_d001_selection_sha256": EXPECTED_D001_SELECTION_SHA,
        "source_hg004_l001_run_sha256": EXPECTED_L001_RUN_SHA,
        "source_hg004_l002_synthesis_sha256": EXPECTED_L002_SYNTHESIS_SHA,
        "case_count": len(mapped),
        "mapping_state_counts": dict(sorted(state_counts.items())),
        "cases": sorted(
            mapped,
            key=lambda row: (
                row["symbol"],
                row["economic_lane"],
                row["historical_track"],
            ),
        ),
        "current_company_probability_surfaces_published": sum(
            row["mapping_state"] == "SURVIVOR_CONDITIONED_BASE_RATE_PUBLISHED"
            for row in mapped
        ),
        "current_terminal_state_count": sum(
            str(row["mapping_state"]).startswith("CURRENT_TERMINAL_")
            for row in mapped
        ),
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["feasibility_pass"] = len(mapped) > 0
    output["promotion_allowed_to_probability_weighted_payoff"] = any(
        row["mapping_state"]
        in {
            "SURVIVOR_CONDITIONED_BASE_RATE_PUBLISHED",
            "CURRENT_TERMINAL_COMPLETED",
        }
        for row in mapped
    )
    output["mapping_sha256"] = digest(output)
    return output
