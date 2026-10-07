from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg006_episode_threading import (
    THREADING_ID,
    deterministic_episode_id,
    validate_episode_manifest,
)

GENERATOR_ID = "HG006-D003-P1-v1"
EXPECTED_INGESTION_SHA = (
    "2188bf803f2088cd10f26892f92f1a82fc810543ad9679c4fc20534e2a3e59e6"
)
EXPECTED_S002_SHA = (
    "e99f270bf48b76bb72f3e2734abddd34bcc580cb1583086cc73e50759e23766e"
)
EXPECTED_EVENT_COUNT = 1564

SCHEME_DIRECT = frozenset(
    {
        "SCHEME_OR_TRANSACTION_NAME",
        "CASE_ORDER_REFERENCE",
        "BOARD_APPROVAL_DATE",
        "OTHER_EXPLICIT_TRANSACTION_REFERENCE",
        "EFFECTIVE_DATE",
        "REGULATORY_OR_COURT_ORDER_DATE",
    }
)
WARRANT_DIRECT = frozenset(
    {
        "BOARD_APPROVAL_DATE",
        "SHAREHOLDER_APPROVAL_DATE",
        "OTHER_EXPLICIT_TRANSACTION_REFERENCE",
        "ALLOTTEE_OR_ALLOTTEE_GROUP",
    }
)
HARD_CONFLICT = {
    "SCHEME_REORGANISATION": frozenset(
        {
            "SCHEME_OR_TRANSACTION_NAME",
            "CASE_ORDER_REFERENCE",
            "BOARD_APPROVAL_DATE",
        }
    ),
    "PREFERENTIAL_WARRANT": frozenset(
        {
            "BOARD_APPROVAL_DATE",
            "SHAREHOLDER_APPROVAL_DATE",
            "OTHER_EXPLICIT_TRANSACTION_REFERENCE",
        }
    ),
}


def _canonical_value(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("HG006 D003 anchor value must be finite JSON") from exc


def _validate_inputs(
    ingestion: dict[str, Any],
    evidence_pack: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if ingestion.get("execution_id") != "HG006-L001-P2-v1":
        raise AlphaContractError("HG006 D003 requires full P2 ingestion")
    if ingestion.get("ingestion_sha256") != EXPECTED_INGESTION_SHA:
        raise AlphaContractError("HG006 D003 P2 ingestion SHA mismatch")
    if ingestion.get("full_ingestion_pass") is not True:
        raise AlphaContractError("HG006 D003 requires passed P2 ingestion")
    if ingestion.get("historical_terminal_labels_opened") is not False:
        raise AlphaContractError("HG006 D003 refuses opened terminal labels")
    if ingestion.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 D003 refuses opened return outcomes")

    if evidence_pack.get("pack_id") != "HG006-S002-v1":
        raise AlphaContractError("HG006 D003 requires frozen S002 evidence pack")
    if evidence_pack.get("pack_sha256") != EXPECTED_S002_SHA:
        raise AlphaContractError("HG006 D003 S002 pack SHA mismatch")
    if evidence_pack.get("historical_terminal_labels_opened") is not False:
        raise AlphaContractError("HG006 D003 S002 terminal labels must remain closed")
    if evidence_pack.get("return_outcomes_opened") is not False:
        raise AlphaContractError("HG006 D003 S002 returns must remain closed")

    rows = ingestion.get("rows")
    chronologies = evidence_pack.get("chronologies")
    if not isinstance(rows, list) or len(rows) != 1448:
        raise AlphaContractError("HG006 D003 ingestion rows unavailable")
    if not isinstance(chronologies, list) or len(chronologies) != 300:
        raise AlphaContractError("HG006 D003 S002 chronologies unavailable")
    return rows, chronologies


def _extractions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "VALIDATED":
            raise AlphaContractError("HG006 D003 requires VALIDATED P2 rows")
        response = row.get("validated_response")
        if not isinstance(response, dict):
            raise AlphaContractError("HG006 D003 validated response unavailable")
        extraction = response.get("validated_extraction")
        if not isinstance(extraction, dict):
            raise AlphaContractError("HG006 D003 validated extraction unavailable")
        result.append(extraction)
    return result


def _event_anchor_values(
    extractions: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, str],
]:
    events: dict[str, dict[str, Any]] = {}
    event_chronology: dict[str, str] = {}
    for extraction in extractions:
        symbol = str(extraction.get("symbol") or "")
        family = str(extraction.get("family") or "")
        chronology_id = str(extraction.get("chronology_id") or "")
        document_id = str(extraction.get("document_id") or "")
        event_ids = extraction.get("event_ids")
        anchors = extraction.get("transaction_anchors")
        if (
            not symbol
            or not family
            or not chronology_id
            or not document_id
            or not isinstance(event_ids, list)
            or not isinstance(anchors, list)
        ):
            raise AlphaContractError("HG006 D003 extraction identity incomplete")

        for event_id_raw in event_ids:
            event_id = str(event_id_raw)
            if not event_id:
                raise AlphaContractError("HG006 D003 empty event ID")
            previous = event_chronology.get(event_id)
            if previous is not None and previous != chronology_id:
                raise AlphaContractError("HG006 D003 event crosses source chronologies")
            event_chronology[event_id] = chronology_id
            event = events.setdefault(
                event_id,
                {
                    "symbol": symbol,
                    "family": family,
                    "documents": set(),
                    "anchors": defaultdict(set),
                },
            )
            if event["symbol"] != symbol or event["family"] != family:
                raise AlphaContractError("HG006 D003 event symbol/family conflict")
            event["documents"].add(document_id)
            for anchor in anchors:
                if not isinstance(anchor, dict):
                    raise TypeError("HG006 D003 transaction anchor must be object")
                anchor_type = str(anchor.get("anchor_type") or "")
                if not anchor_type or anchor.get("value") in (None, ""):
                    raise AlphaContractError("HG006 D003 transaction anchor incomplete")
                event["anchors"][anchor_type].add(
                    _canonical_value(anchor["value"])
                )

    if len(events) != EXPECTED_EVENT_COUNT:
        raise AlphaContractError(
            f"HG006 D003 expected {EXPECTED_EVENT_COUNT} events, observed {len(events)}"
        )
    return events, event_chronology


def _source_metadata(
    chronologies: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    list[str],
]:
    chronology_by_id: dict[str, dict[str, Any]] = {}
    event_meta: dict[str, dict[str, Any]] = {}
    unavailable = []

    for chronology in chronologies:
        if not isinstance(chronology, dict):
            raise TypeError("HG006 D003 chronology must be object")
        chronology_id = str(chronology.get("chronology_id") or "")
        if not chronology_id or chronology_id in chronology_by_id:
            raise AlphaContractError("HG006 D003 chronology IDs must be unique")
        chronology_by_id[chronology_id] = chronology

        if chronology.get("evidence_state") == "TEXT_UNAVAILABLE":
            unavailable.append(chronology_id)

        documents = chronology.get("retained_documents")
        if not isinstance(documents, list):
            raise AlphaContractError("HG006 D003 retained documents unavailable")
        for document in documents:
            if not isinstance(document, dict):
                raise TypeError("HG006 D003 retained document must be object")
            document_id = str(document.get("document_id") or "")
            timestamp = str(document.get("chronology_timestamp_utc") or "")
            event_ids = document.get("event_ids")
            if not document_id or not timestamp or not isinstance(event_ids, list):
                raise AlphaContractError("HG006 D003 retained document identity incomplete")
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise AlphaContractError(
                    "HG006 D003 chronology timestamp must be ISO datetime"
                ) from exc
            for event_id_raw in event_ids:
                event_id = str(event_id_raw)
                meta = event_meta.setdefault(
                    event_id,
                    {
                        "chronology_id": chronology_id,
                        "document_ids": set(),
                        "timestamps": set(),
                    },
                )
                if meta["chronology_id"] != chronology_id:
                    raise AlphaContractError(
                        "HG006 D003 source event crosses chronologies"
                    )
                meta["document_ids"].add(document_id)
                meta["timestamps"].add(timestamp)

    return chronology_by_id, event_meta, sorted(unavailable)


def _direct_tokens(
    family: str,
    anchors: dict[str, set[str]],
) -> set[tuple[str, str]]:
    allowed = (
        SCHEME_DIRECT
        if family == "SCHEME_REORGANISATION"
        else WARRANT_DIRECT
    )
    result = {
        (anchor_type, value)
        for anchor_type in allowed
        for value in anchors.get(anchor_type, set())
    }

    if family == "SCHEME_REORGANISATION":
        for target in anchors.get("TARGET_OR_TRANSFEROR", set()):
            for transferee in anchors.get(
                "TRANSFEREE_OR_RESULTING_ENTITY", set()
            ):
                result.add(("TARGET_TRANSFEREE_PAIR", f"{target}|{transferee}"))
        for record_date in anchors.get("RECORD_DATE", set()):
            for ratio in anchors.get(
                "ENTITLEMENT_OR_EXCHANGE_RATIO", set()
            ):
                result.add(("RECORD_RATIO", f"{record_date}|{ratio}"))
    elif family == "PREFERENTIAL_WARRANT":
        for price in anchors.get("OFFER_OR_ISSUE_PRICE", set()):
            for count in anchors.get("SECURITY_COUNT", set()):
                result.add(("PRICE_SECURITY_COUNT", f"{price}|{count}"))
            for size in anchors.get("OFFER_OR_ISSUE_SIZE", set()):
                result.add(("PRICE_ISSUE_SIZE", f"{price}|{size}"))
    else:
        raise AlphaContractError(f"HG006 D003 unsupported family: {family}")
    return result


def _hard_conflicts(
    family: str,
    event_ids: list[str],
    events: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for anchor_type in sorted(HARD_CONFLICT[family]):
        values = set()
        for event_id in event_ids:
            values.update(events[event_id]["anchors"].get(anchor_type, set()))
        if len(values) > 1:
            result.append(
                {
                    "anchor_type": anchor_type,
                    "canonical_values": sorted(values),
                }
            )
    return result


def _components(
    event_ids: list[str],
    events: dict[str, dict[str, Any]],
) -> list[list[str]]:
    token_to_events: dict[tuple[str, str], list[str]] = defaultdict(list)
    adjacency = {event_id: set() for event_id in event_ids}

    for event_id in event_ids:
        event = events[event_id]
        for token in _direct_tokens(event["family"], event["anchors"]):
            token_to_events[token].append(event_id)

    for linked in token_to_events.values():
        if len(linked) < 2:
            continue
        first = linked[0]
        for event_id in linked[1:]:
            adjacency[first].add(event_id)
            adjacency[event_id].add(first)

    seen: set[str] = set()
    result = []
    for event_id in sorted(event_ids):
        if event_id in seen:
            continue
        stack = [event_id]
        component = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - seen, reverse=True))
        result.append(sorted(component))
    return result


def build_deterministic_episode_threading(
    *,
    ingestion: dict[str, Any],
    evidence_pack: dict[str, Any],
) -> dict[str, Any]:
    rows, chronologies = _validate_inputs(ingestion, evidence_pack)
    extractions = _extractions(rows)
    events, event_chronology = _event_anchor_values(extractions)
    chronology_by_id, event_meta, unavailable_chronologies = _source_metadata(
        chronologies
    )
    if set(events) != set(event_meta):
        raise AlphaContractError("HG006 D003 S002/P2 event identity mismatch")

    chronology_events: dict[str, list[str]] = defaultdict(list)
    for event_id, chronology_id in event_chronology.items():
        chronology_events[chronology_id].append(event_id)

    raw_episodes = []
    ambiguous_ids: list[str] = []
    ambiguity_rows = []
    strong_tokens_by_episode: dict[str, list[dict[str, str]]] = {}

    for chronology_id, ids in sorted(chronology_events.items()):
        chronology = chronology_by_id.get(chronology_id)
        if chronology is None:
            raise AlphaContractError("HG006 D003 chronology metadata missing")
        expected_symbol = str(chronology.get("symbol") or "")
        expected_family = str(chronology.get("family") or "")

        for component in _components(sorted(ids), events):
            symbol = events[component[0]]["symbol"]
            family = events[component[0]]["family"]
            if symbol != expected_symbol or family != expected_family:
                raise AlphaContractError(
                    "HG006 D003 event identity differs from source chronology"
                )

            all_tokens = set()
            token_support: dict[tuple[str, str], set[str]] = defaultdict(set)
            for event_id in component:
                for token in _direct_tokens(
                    family, events[event_id]["anchors"]
                ):
                    all_tokens.add(token)
                    token_support[token].add(event_id)

            supported_tokens = [
                {
                    "token_type": token_type,
                    "canonical_value": value,
                    "supporting_event_ids": sorted(support),
                }
                for (token_type, value), support in sorted(token_support.items())
                if len(component) == 1 or len(support) >= 2
            ]
            conflicts = _hard_conflicts(family, component, events)

            if not all_tokens:
                ambiguous_ids.extend(component)
                for event_id in component:
                    ambiguity_rows.append(
                        {
                            "event_id": event_id,
                            "chronology_id": chronology_id,
                            "symbol": symbol,
                            "family": family,
                            "reason": "NO_FROZEN_STRONG_ANCHOR",
                        }
                    )
                continue

            if conflicts:
                ambiguous_ids.extend(component)
                for event_id in component:
                    ambiguity_rows.append(
                        {
                            "event_id": event_id,
                            "chronology_id": chronology_id,
                            "symbol": symbol,
                            "family": family,
                            "reason": "HARD_IDENTITY_ANCHOR_CONFLICT",
                            "conflicts": conflicts,
                        }
                    )
                continue

            episode_id = deterministic_episode_id(symbol, family, component)
            raw_episodes.append(
                {
                    "episode_id": episode_id,
                    "symbol": symbol,
                    "family": family,
                    "event_ids": component,
                }
            )
            strong_tokens_by_episode[episode_id] = supported_tokens

    raw_manifest = {
        "threading_id": THREADING_ID,
        "episodes": raw_episodes,
        "ambiguous_event_ids": sorted(ambiguous_ids),
        "document_unavailable_event_ids": [],
    }
    sealed = validate_episode_manifest(
        extractions=extractions,
        manifest=raw_manifest,
    )

    enriched = []
    for episode in sealed["episodes"]:
        event_ids = episode["event_ids"]
        chronology_ids = {
            event_meta[event_id]["chronology_id"] for event_id in event_ids
        }
        if len(chronology_ids) != 1:
            raise AlphaContractError("HG006 D003 episode crosses chronologies")
        chronology_id = next(iter(chronology_ids))
        timestamps = sorted(
            {
                timestamp
                for event_id in event_ids
                for timestamp in event_meta[event_id]["timestamps"]
            }
        )
        document_ids = sorted(
            {
                document_id
                for event_id in event_ids
                for document_id in event_meta[event_id]["document_ids"]
            }
        )
        enriched.append(
            {
                **episode,
                "chronology_id": chronology_id,
                "document_ids": document_ids,
                "earliest_observed_at_utc": timestamps[0],
                "latest_observed_at_utc": timestamps[-1],
                "strong_anchor_support": strong_tokens_by_episode[
                    episode["episode_id"]
                ],
                "threading_state": "EPISODE_ASSIGNED",
            }
        )

    assigned_event_count = sum(len(row["event_ids"]) for row in enriched)
    ambiguous_event_count = len(set(ambiguous_ids))
    family_counts = Counter(row["family"] for row in enriched)
    threshold_passes = {
        "complete_1564_event_accounting": (
            assigned_event_count + ambiguous_event_count == EXPECTED_EVENT_COUNT
        ),
        "no_cross_symbol_family_chronology": True,
        "assigned_episodes_have_strong_anchor": all(
            row["strong_anchor_support"] for row in enriched
        ),
        "assigned_episodes_have_no_hard_identity_conflict": True,
        "frozen_d003_validator_accepts_manifest": True,
        "minimum_30_episodes_each_priority_family": all(
            family_counts.get(family, 0) >= 30
            for family in (
                "PREFERENTIAL_WARRANT",
                "SCHEME_REORGANISATION",
            )
        ),
        "grouping_ignores_stage_terminal_and_market_outcomes": True,
    }

    output = {
        "schema_version": 1,
        "generator_id": GENERATOR_ID,
        "threading_id": THREADING_ID,
        "classification": "DETERMINISTIC_HISTORICAL_TRANSACTION_THREADING_NOT_OUTCOMES",
        "source_ingestion_sha256": EXPECTED_INGESTION_SHA,
        "source_s002_pack_sha256": EXPECTED_S002_SHA,
        "source_event_count": EXPECTED_EVENT_COUNT,
        "episode_count": len(enriched),
        "episode_assigned_event_count": assigned_event_count,
        "thread_ambiguous_event_count": ambiguous_event_count,
        "episode_counts_by_family": dict(sorted(family_counts.items())),
        "text_unavailable_chronology_ids": unavailable_chronologies,
        "episodes": sorted(enriched, key=lambda row: row["episode_id"]),
        "ambiguous_events": sorted(
            ambiguity_rows, key=lambda row: row["event_id"]
        ),
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_d002_terminal_labeling": all(
            threshold_passes.values()
        ),
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["threading_sha256"] = digest(output)
    return output
