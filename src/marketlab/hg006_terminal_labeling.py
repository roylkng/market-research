from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest

LABELER_ID = "HG006-D002-P1-v1"
EXPECTED_THREADING_SHA = (
    "4d4a58bf7179305ee134a098bd063436bef060077b785056e499d9c885a8d250"
)
EXPECTED_INGESTION_SHA = (
    "2188bf803f2088cd10f26892f92f1a82fc810543ad9679c4fc20534e2a3e59e6"
)
EXPECTED_S002_SHA = (
    "e99f270bf48b76bb72f3e2734abddd34bcc580cb1583086cc73e50759e23766e"
)
EXPECTED_EPISODE_COUNT = 333
OBSERVATION_CUTOFF = date(2026, 9, 30)

PRIMARY_COMPLETED = "COMPLETED"
PRIMARY_FAILED = "FAILED_OR_WITHDRAWN"
PRIMARY_CENSORED = "RIGHT_CENSORED"
PRIMARY_CONFLICT = "UNRESOLVED_SOURCE_CONFLICT"

STAGE_FIELDS = (
    "BOARD_APPROVED",
    "SHAREHOLDER_APPROVED",
    "REGULATORY_OR_COURT_APPROVED",
    "PUBLIC_ANNOUNCEMENT",
    "RECORD_DATE_FIXED",
    "OFFER_OPEN",
    "OFFER_CLOSED",
    "ALLOTMENT_COMPLETED",
    "WARRANT_EXERCISE_OR_CONVERSION_COMPLETED",
    "TRANSACTION_COMPLETED",
    "CANCELLED_OR_WITHDRAWN",
)


def _iso_day_from_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise AlphaContractError(f"{field} must be a non-empty ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError(f"{field} must be ISO datetime") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError(f"{field} must be timezone-aware")
    day = parsed.date()
    if day > OBSERVATION_CUTOFF:
        raise AlphaContractError(f"{field} exceeds frozen observation cutoff")
    return day.isoformat()


def _validate_sources(
    threading: dict[str, Any],
    ingestion: dict[str, Any],
    evidence_pack: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if threading.get("threading_sha256") != EXPECTED_THREADING_SHA:
        raise AlphaContractError("HG006 D002 P1 threading SHA mismatch")
    if threading.get("feasibility_pass") is not True:
        raise AlphaContractError("HG006 D002 P1 requires passed D003 threading")
    if threading.get("episode_count") != EXPECTED_EPISODE_COUNT:
        raise AlphaContractError("HG006 D002 P1 episode count mismatch")
    if threading.get("historical_terminal_labels_opened") is not False:
        raise AlphaContractError("HG006 D002 P1 refuses pre-opened terminal labels")
    if threading.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 D002 P1 refuses opened return outcomes")

    if ingestion.get("ingestion_sha256") != EXPECTED_INGESTION_SHA:
        raise AlphaContractError("HG006 D002 P1 ingestion SHA mismatch")
    if ingestion.get("full_ingestion_pass") is not True:
        raise AlphaContractError("HG006 D002 P1 requires passed full ingestion")
    if ingestion.get("historical_terminal_labels_opened") is not False:
        raise AlphaContractError("HG006 D002 P1 ingestion labels must remain closed")
    if ingestion.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 D002 P1 ingestion returns must remain closed")

    if evidence_pack.get("pack_sha256") != EXPECTED_S002_SHA:
        raise AlphaContractError("HG006 D002 P1 S002 pack SHA mismatch")
    if evidence_pack.get("historical_terminal_labels_opened") is not False:
        raise AlphaContractError("HG006 D002 P1 S002 labels must remain closed")
    if evidence_pack.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 D002 P1 S002 returns must remain closed")

    episodes = threading.get("episodes")
    rows = ingestion.get("rows")
    chronologies = evidence_pack.get("chronologies")
    if not isinstance(episodes, list) or len(episodes) != EXPECTED_EPISODE_COUNT:
        raise AlphaContractError("HG006 D002 P1 episode rows unavailable")
    if not isinstance(rows, list) or len(rows) != 1448:
        raise AlphaContractError("HG006 D002 P1 ingestion rows unavailable")
    if not isinstance(chronologies, list) or len(chronologies) != 300:
        raise AlphaContractError("HG006 D002 P1 chronology rows unavailable")
    return episodes, rows, chronologies


def _chronology_document_dates(
    chronologies: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for chronology in chronologies:
        if not isinstance(chronology, dict):
            raise TypeError("HG006 D002 P1 chronology must be object")
        chronology_id = str(chronology.get("chronology_id") or "")
        if not chronology_id or chronology_id in result:
            raise AlphaContractError("HG006 D002 P1 chronology IDs must be unique")
        documents = chronology.get("retained_documents")
        if not isinstance(documents, list):
            raise AlphaContractError("HG006 D002 P1 retained documents unavailable")
        by_document: dict[str, str] = {}
        for document in documents:
            if not isinstance(document, dict):
                raise TypeError("HG006 D002 P1 retained document must be object")
            document_id = str(document.get("document_id") or "")
            observed = str(document.get("chronology_timestamp_utc") or "")
            if not document_id or not observed:
                raise AlphaContractError("HG006 D002 P1 document identity incomplete")
            day = _iso_day_from_timestamp(
                observed,
                "chronology_timestamp_utc",
            )
            previous = by_document.get(document_id)
            if previous is not None and previous != day:
                raise AlphaContractError(
                    "HG006 D002 P1 document has conflicting observation dates"
                )
            by_document[document_id] = day
        result[chronology_id] = by_document
    return result


def _validated_extractions(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "VALIDATED":
            raise AlphaContractError("HG006 D002 P1 requires VALIDATED ingestion rows")
        chronology_id = str(row.get("chronology_id") or "")
        document_id = str(row.get("document_id") or "")
        symbol = str(row.get("symbol") or "")
        family = str(row.get("family") or "")
        response = row.get("validated_response")
        if (
            not chronology_id
            or not document_id
            or not symbol
            or not family
            or not isinstance(response, dict)
        ):
            raise AlphaContractError("HG006 D002 P1 ingestion envelope incomplete")
        extraction = response.get("validated_extraction")
        if not isinstance(extraction, dict):
            raise AlphaContractError("HG006 D002 P1 validated extraction unavailable")
        if str(extraction.get("document_id") or "") != document_id:
            raise AlphaContractError("HG006 D002 P1 document envelope mismatch")
        if str(extraction.get("symbol") or "") != symbol:
            raise AlphaContractError("HG006 D002 P1 symbol envelope mismatch")
        if str(extraction.get("family") or "") != family:
            raise AlphaContractError("HG006 D002 P1 family envelope mismatch")
        trusted = dict(extraction)
        trusted["chronology_id"] = chronology_id
        result.append(trusted)
    return result


def _stage_rows(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    stages = extraction.get("stage_observations")
    if not isinstance(stages, list):
        raise AlphaContractError("HG006 D002 P1 stage observations unavailable")
    return [row for row in stages if isinstance(row, dict)]


def _anchor_rows(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    anchors = extraction.get("transaction_anchors")
    if not isinstance(anchors, list):
        raise AlphaContractError("HG006 D002 P1 transaction anchors unavailable")
    return [row for row in anchors if isinstance(row, dict)]


def _has_stage(extraction: dict[str, Any], stage: str) -> bool:
    return any(str(row.get("stage") or "") == stage for row in _stage_rows(extraction))


def _stage_evidence(
    extraction: dict[str, Any],
    stage: str,
) -> list[str]:
    result = []
    for row in _stage_rows(extraction):
        if str(row.get("stage") or "") != stage:
            continue
        evidence = row.get("evidence_segment_ids")
        if not isinstance(evidence, list):
            raise AlphaContractError("HG006 D002 P1 stage evidence unavailable")
        result.extend(str(value) for value in evidence)
    return sorted(set(result))


def _has_anchor(extraction: dict[str, Any], anchor_type: str) -> bool:
    return any(
        str(row.get("anchor_type") or "") == anchor_type
        and row.get("value") not in (None, "")
        for row in _anchor_rows(extraction)
    )


def _anchor_evidence(
    extraction: dict[str, Any],
    anchor_type: str,
) -> list[str]:
    result = []
    for row in _anchor_rows(extraction):
        if str(row.get("anchor_type") or "") != anchor_type:
            continue
        evidence = row.get("evidence_segment_ids")
        if not isinstance(evidence, list):
            raise AlphaContractError("HG006 D002 P1 anchor evidence unavailable")
        result.extend(str(value) for value in evidence)
    return sorted(set(result))


def _terminal_evidence(extraction: dict[str, Any]) -> list[str]:
    evidence = extraction.get("terminal_evidence_segment_ids")
    if not isinstance(evidence, list):
        raise AlphaContractError("HG006 D002 P1 terminal evidence unavailable")
    return sorted(set(str(value) for value in evidence))


def _signal(
    *,
    extraction: dict[str, Any],
    observed_date: str,
    signal: str,
    evidence_segment_ids: list[str],
) -> dict[str, Any]:
    if not evidence_segment_ids:
        raise AlphaContractError("HG006 D002 P1 terminal signal requires evidence")
    return {
        "document_id": str(extraction["document_id"]),
        "observed_date": observed_date,
        "signal": signal,
        "evidence_segment_ids": sorted(set(evidence_segment_ids)),
    }


def _episode_extractions(
    *,
    episode: dict[str, Any],
    extractions: list[dict[str, Any]],
    document_dates: dict[str, dict[str, str]],
) -> tuple[list[tuple[dict[str, Any], str]], list[str]]:
    episode_ids = {str(value) for value in episode.get("event_ids") or []}
    document_ids = {str(value) for value in episode.get("document_ids") or []}
    chronology_id = str(episode.get("chronology_id") or "")
    symbol = str(episode.get("symbol") or "")
    family = str(episode.get("family") or "")
    if not episode_ids or not document_ids or not chronology_id or not symbol or not family:
        raise AlphaContractError("HG006 D002 P1 episode identity incomplete")

    chronology_dates = document_dates.get(chronology_id)
    if chronology_dates is None:
        raise AlphaContractError("HG006 D002 P1 chronology date map missing")

    retained = []
    excluded = []
    for extraction in extractions:
        if str(extraction.get("chronology_id") or "") != chronology_id:
            continue
        extraction_ids = {
            str(value) for value in extraction.get("event_ids") or []
        }
        if not extraction_ids or not extraction_ids.intersection(episode_ids):
            continue
        document_id = str(extraction.get("document_id") or "")
        if (
            str(extraction.get("symbol") or "") != symbol
            or str(extraction.get("family") or "") != family
        ):
            raise AlphaContractError("HG006 D002 P1 episode extraction identity mismatch")
        if document_id not in document_ids:
            raise AlphaContractError("HG006 D002 P1 episode document mismatch")
        if not extraction_ids.issubset(episode_ids):
            excluded.append(document_id)
            continue
        observed_date = chronology_dates.get(document_id)
        if observed_date is None:
            raise AlphaContractError("HG006 D002 P1 document observation date missing")
        retained.append((extraction, observed_date))

    if not retained:
        raise AlphaContractError("HG006 D002 P1 episode has no attributable extraction")
    return retained, sorted(set(excluded))


def _first_stage_dates(
    retained: list[tuple[dict[str, Any], str]],
) -> dict[str, str]:
    dates: dict[str, list[str]] = defaultdict(list)
    for extraction, observed_date in retained:
        for row in _stage_rows(extraction):
            stage = str(row.get("stage") or "")
            if stage in STAGE_FIELDS:
                evidence = row.get("evidence_segment_ids")
                if not isinstance(evidence, list) or not evidence:
                    raise AlphaContractError("HG006 D002 P1 explicit stage lacks evidence")
                dates[stage].append(observed_date)
    return {
        stage: min(values)
        for stage, values in sorted(dates.items())
        if values
    }


def _conflict_signal(
    retained: list[tuple[dict[str, Any], str]],
) -> list[dict[str, Any]]:
    result = []
    for extraction, observed_date in retained:
        if extraction.get("family_semantic_conflict") is not None:
            conflict = extraction["family_semantic_conflict"]
            evidence = (
                conflict.get("evidence_segment_ids")
                if isinstance(conflict, dict)
                else []
            )
            if not isinstance(evidence, list) or not evidence:
                raise AlphaContractError(
                    "HG006 D002 P1 family semantic conflict lacks evidence"
                )
            result.append(
                _signal(
                    extraction=extraction,
                    observed_date=observed_date,
                    signal="FAMILY_SEMANTIC_CONFLICT",
                    evidence_segment_ids=[str(value) for value in evidence],
                )
            )
        if extraction.get("explicit_terminal_language") == (
            "CONFLICTING_TERMINAL_LANGUAGE"
        ):
            result.append(
                _signal(
                    extraction=extraction,
                    observed_date=observed_date,
                    signal="CONFLICTING_TERMINAL_LANGUAGE",
                    evidence_segment_ids=_terminal_evidence(extraction),
                )
            )
    return result


def _failure_signals(
    retained: list[tuple[dict[str, Any], str]],
) -> list[dict[str, Any]]:
    result = []
    for extraction, observed_date in retained:
        if _has_stage(extraction, "CANCELLED_OR_WITHDRAWN"):
            result.append(
                _signal(
                    extraction=extraction,
                    observed_date=observed_date,
                    signal="CANCELLED_OR_WITHDRAWN_STAGE",
                    evidence_segment_ids=_stage_evidence(
                        extraction, "CANCELLED_OR_WITHDRAWN"
                    ),
                )
            )
        if extraction.get("explicit_terminal_language") == (
            "EXPLICIT_FAILURE_OR_WITHDRAWAL_LANGUAGE"
        ):
            result.append(
                _signal(
                    extraction=extraction,
                    observed_date=observed_date,
                    signal="EXPLICIT_FAILURE_OR_WITHDRAWAL_LANGUAGE",
                    evidence_segment_ids=_terminal_evidence(extraction),
                )
            )
    return result


def _scheme_completion_signals(
    retained: list[tuple[dict[str, Any], str]],
) -> list[dict[str, Any]]:
    result = []
    for extraction, observed_date in retained:
        if _has_stage(extraction, "TRANSACTION_COMPLETED"):
            result.append(
                _signal(
                    extraction=extraction,
                    observed_date=observed_date,
                    signal="TRANSACTION_COMPLETED_STAGE",
                    evidence_segment_ids=_stage_evidence(
                        extraction, "TRANSACTION_COMPLETED"
                    ),
                )
            )
            continue
        if (
            extraction.get("explicit_terminal_language")
            == "EXPLICIT_COMPLETION_LANGUAGE"
            and _has_anchor(extraction, "EFFECTIVE_DATE")
        ):
            result.append(
                _signal(
                    extraction=extraction,
                    observed_date=observed_date,
                    signal="EXPLICIT_COMPLETION_WITH_EFFECTIVE_DATE",
                    evidence_segment_ids=(
                        _terminal_evidence(extraction)
                        + _anchor_evidence(extraction, "EFFECTIVE_DATE")
                    ),
                )
            )
    return result


def _warrant_completion_signals(
    retained: list[tuple[dict[str, Any], str]],
    *,
    stage: str,
) -> list[dict[str, Any]]:
    result = []
    for extraction, observed_date in retained:
        if _has_stage(extraction, stage):
            result.append(
                _signal(
                    extraction=extraction,
                    observed_date=observed_date,
                    signal=f"{stage}_STAGE",
                    evidence_segment_ids=_stage_evidence(extraction, stage),
                )
            )
    return result


def _resolve_track(
    *,
    completion: list[dict[str, Any]],
    failure: list[dict[str, Any]],
    conflict: list[dict[str, Any]],
) -> dict[str, Any]:
    if conflict or (completion and failure):
        return {
            "terminal_state": PRIMARY_CONFLICT,
            "terminal_date": None,
            "terminal_evidence": sorted(
                conflict + completion + failure,
                key=lambda row: (
                    row["observed_date"],
                    row["document_id"],
                    row["signal"],
                ),
            ),
        }
    if completion:
        return {
            "terminal_state": PRIMARY_COMPLETED,
            "terminal_date": min(row["observed_date"] for row in completion),
            "terminal_evidence": sorted(
                completion,
                key=lambda row: (
                    row["observed_date"],
                    row["document_id"],
                    row["signal"],
                ),
            ),
        }
    if failure:
        return {
            "terminal_state": PRIMARY_FAILED,
            "terminal_date": min(row["observed_date"] for row in failure),
            "terminal_evidence": sorted(
                failure,
                key=lambda row: (
                    row["observed_date"],
                    row["document_id"],
                    row["signal"],
                ),
            ),
        }
    return {
        "terminal_state": PRIMARY_CENSORED,
        "terminal_date": None,
        "terminal_evidence": [],
    }


def label_episode(
    *,
    episode: dict[str, Any],
    extractions: list[dict[str, Any]],
    document_dates: dict[str, dict[str, str]],
) -> dict[str, Any]:
    retained, excluded_documents = _episode_extractions(
        episode=episode,
        extractions=extractions,
        document_dates=document_dates,
    )
    entry_date = _iso_day_from_timestamp(
        episode.get("earliest_observed_at_utc"),
        "earliest_observed_at_utc",
    )
    stage_dates = _first_stage_dates(retained)
    family = str(episode["family"])
    conflict = _conflict_signal(retained)
    failure = _failure_signals(retained)

    if family == "SCHEME_REORGANISATION":
        primary = _resolve_track(
            completion=_scheme_completion_signals(retained),
            failure=failure,
            conflict=conflict,
        )
        secondary = None
    elif family == "PREFERENTIAL_WARRANT":
        primary = _resolve_track(
            completion=_warrant_completion_signals(
                retained,
                stage="ALLOTMENT_COMPLETED",
            ),
            failure=failure,
            conflict=conflict,
        )
        secondary = _resolve_track(
            completion=_warrant_completion_signals(
                retained,
                stage="WARRANT_EXERCISE_OR_CONVERSION_COMPLETED",
            ),
            failure=failure,
            conflict=conflict,
        )
    else:
        raise AlphaContractError(f"HG006 D002 P1 unsupported family: {family}")

    for track in [primary] + ([secondary] if secondary is not None else []):
        terminal_date = track["terminal_date"]
        if track["terminal_state"] in {PRIMARY_COMPLETED, PRIMARY_FAILED}:
            if terminal_date is None or terminal_date < entry_date:
                raise AlphaContractError(
                    "HG006 D002 P1 terminal date outside observed risk interval"
                )
            if not track["terminal_evidence"]:
                raise AlphaContractError(
                    "HG006 D002 P1 terminal state lacks evidence"
                )
        elif track["terminal_state"] == PRIMARY_CENSORED:
            if terminal_date is not None or track["terminal_evidence"]:
                raise AlphaContractError(
                    "HG006 D002 P1 censored state carries terminal evidence"
                )
        elif track["terminal_state"] == PRIMARY_CONFLICT:
            if terminal_date is not None or not track["terminal_evidence"]:
                raise AlphaContractError(
                    "HG006 D002 P1 conflict state evidence invalid"
                )

    return {
        "episode_id": episode["episode_id"],
        "symbol": episode["symbol"],
        "family": family,
        "chronology_id": episode["chronology_id"],
        "event_ids": list(episode["event_ids"]),
        "document_ids": list(episode["document_ids"]),
        "entry_date": entry_date,
        "observation_cutoff": OBSERVATION_CUTOFF.isoformat(),
        "first_observed_stage_dates": stage_dates,
        "excluded_cross_episode_document_ids": excluded_documents,
        "primary_outcome_track": (
            "issuance_completion"
            if family == "PREFERENTIAL_WARRANT"
            else "transaction_completion"
        ),
        "primary_terminal_state": primary["terminal_state"],
        "primary_terminal_date": primary["terminal_date"],
        "primary_terminal_evidence": primary["terminal_evidence"],
        "full_economic_exercise": (
            {
                "terminal_state": secondary["terminal_state"],
                "terminal_date": secondary["terminal_date"],
                "terminal_evidence": secondary["terminal_evidence"],
            }
            if secondary is not None
            else None
        ),
        "historical_terminal_labels_opened": True,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def build_terminal_label_panel(
    *,
    threading: dict[str, Any],
    ingestion: dict[str, Any],
    evidence_pack: dict[str, Any],
) -> dict[str, Any]:
    episodes, rows, chronologies = _validate_sources(
        threading,
        ingestion,
        evidence_pack,
    )
    extractions = _validated_extractions(rows)
    document_dates = _chronology_document_dates(chronologies)

    labeled = [
        label_episode(
            episode=episode,
            extractions=extractions,
            document_dates=document_dates,
        )
        for episode in episodes
    ]
    if len({str(row["episode_id"]) for row in labeled}) != EXPECTED_EPISODE_COUNT:
        raise AlphaContractError("HG006 D002 P1 episode labels must be unique")

    primary_counts: dict[str, Counter[str]] = defaultdict(Counter)
    exercise_counts: Counter[str] = Counter()
    for row in labeled:
        primary_counts[str(row["family"])][str(row["primary_terminal_state"])] += 1
        if row["family"] == "PREFERENTIAL_WARRANT":
            exercise = row["full_economic_exercise"]
            if not isinstance(exercise, dict):
                raise AlphaContractError("HG006 D002 P1 warrant exercise track missing")
            exercise_counts[str(exercise["terminal_state"])] += 1

    gates = {
        "complete_333_episode_accounting": len(labeled) == EXPECTED_EPISODE_COUNT,
        "unique_episode_identity": len(
            {str(row["episode_id"]) for row in labeled}
        ) == EXPECTED_EPISODE_COUNT,
        "all_terminal_dates_within_risk_interval": all(
            row["primary_terminal_date"] is None
            or (
                row["entry_date"]
                <= row["primary_terminal_date"]
                <= OBSERVATION_CUTOFF.isoformat()
            )
            for row in labeled
        ),
        "warrant_primary_secondary_tracks_distinct": all(
            row["family"] != "PREFERENTIAL_WARRANT"
            or row["full_economic_exercise"] is not None
            for row in labeled
        ),
        "return_outcomes_remain_closed": True,
    }

    output = {
        "schema_version": 1,
        "labeler_id": LABELER_ID,
        "classification": "HISTORICAL_DISCRETE_EVENT_TERMINAL_LABELS_NOT_PROBABILITIES",
        "source_threading_sha256": EXPECTED_THREADING_SHA,
        "source_ingestion_sha256": EXPECTED_INGESTION_SHA,
        "source_s002_pack_sha256": EXPECTED_S002_SHA,
        "observation_cutoff": OBSERVATION_CUTOFF.isoformat(),
        "episode_count": EXPECTED_EPISODE_COUNT,
        "primary_state_counts_by_family": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(primary_counts.items())
        },
        "warrant_full_exercise_state_counts": dict(sorted(exercise_counts.items())),
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_d004_base_rates": all(gates.values()),
        "episodes": sorted(labeled, key=lambda row: str(row["episode_id"])),
        "historical_terminal_labels_opened": True,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["label_panel_sha256"] = digest(output)
    return output
