from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest

PACK_ID = "HG006-S002-v1"
EXPECTED_SELECTION_ID = "HG006-S001-v1"
EXPECTED_SELECTION_SHA = "4bc9659c1111f0694bbbec8754b6193116871367b78f126c39e09bc329c961f5"
EXPECTED_D001_ID = "HG006-D001-v1"
EXPECTED_D001_SHA = "a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5"
EXPECTED_D001B_ID = "HG006-D001B-v1"
EXPECTED_D001B_SHA = "4f841df6599d4836b1a7798439f69eb889690da19942cf48f41d4752b57d4ce9"
EXPECTED_CHRONOLOGY_COUNT = 300
MAX_ADDITIONAL_DOCUMENTS = 4
MAX_ADDITIONAL_SEGMENTS = 4

PHRASE_GROUPS: dict[str, tuple[str, ...]] = {
    "TERMINAL": (
        "completed",
        "completion",
        "consummated",
        "implemented",
        "became effective",
        "effective from",
        "effective date",
        "has become effective",
        "made effective",
        "withdrawn",
        "withdrawal",
        "cancelled",
        "canceled",
        "cancellation",
        "terminated",
        "termination",
        "abandoned",
        "not proceeded",
        "not proceed",
        "rejected",
        "rejection",
        "forfeited",
        "forfeiture",
        "extinguishment",
        "extinguished",
    ),
    "APPROVAL_STAGE": (
        "board of directors",
        "board meeting",
        "board approved",
        "shareholders approved",
        "shareholder approval",
        "special resolution",
        "voting results",
        "scrutinizer",
        "in-principle approval",
        "in principle approval",
        "stock exchange approval",
        "no objection",
        "no-objection",
        "nclt",
        "national company law tribunal",
        "tribunal",
        "sanctioned",
        "sanction",
        "regulatory approval",
        "record date",
        "offer opens",
        "offer opening",
        "offer closes",
        "offer closing",
        "allotment",
        "allotted",
        "issue and allot",
        "conversion",
        "converted",
        "exercise of warrants",
        "exercise warrant",
        "registrar of companies",
        "roc filing",
        "filed with roc",
    ),
    "SCHEME_ANCHOR": (
        "scheme of arrangement",
        "composite scheme",
        "demerger",
        "de-merger",
        "amalgamation",
        "merger",
        "transferor company",
        "transferee company",
        "resulting company",
        "appointed date",
        "exchange ratio",
        "share entitlement ratio",
        "case number",
        "company petition",
    ),
    "WARRANT_ANCHOR": (
        "preferential issue",
        "preferential allotment",
        "preferential basis",
        "convertible warrant",
        "warrants",
        "warrant",
        "issue price",
        "exercise price",
        "allottee",
        "allottees",
        "promoter group",
        "consideration",
        "number of warrants",
        "number of securities",
        "conversion price",
        "balance consideration",
    ),
}


def _normalise(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", text).strip()


def phrase_hits(text: str) -> dict[str, Any]:
    normalised = _normalise(text)
    groups: dict[str, dict[str, int]] = {}
    total = 0
    for group, phrases in PHRASE_GROUPS.items():
        counts = {
            phrase: normalised.count(phrase)
            for phrase in phrases
            if normalised.count(phrase) > 0
        }
        if counts:
            groups[group] = counts
            total += sum(counts.values())
    return {
        "groups": groups,
        "distinct_group_count": len(groups),
        "total_phrase_occurrences": total,
        "terminal_match": "TERMINAL" in groups,
    }


def _iso_timestamp(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise AlphaContractError("HG006 S002 event timestamp unavailable")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError(
            f"HG006 S002 invalid event timestamp: {value}"
        ) from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("HG006 S002 event timestamp lacks timezone")
    return parsed.isoformat().replace("+00:00", "Z")


def _validate_inputs(
    selection: dict[str, Any],
    d001: dict[str, Any],
    d001b_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if selection.get("selection_id") != EXPECTED_SELECTION_ID:
        raise AlphaContractError("HG006 S002 requires frozen S001 selection")
    if selection.get("selection_sha256") != EXPECTED_SELECTION_SHA:
        raise AlphaContractError("HG006 S002 S001 selection SHA mismatch")
    if selection.get("selected_chronology_count") != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 S002 selected chronology count mismatch")
    if d001.get("census_id") != EXPECTED_D001_ID:
        raise AlphaContractError("HG006 S002 requires frozen D001 census")
    if d001.get("census_sha256") != EXPECTED_D001_SHA:
        raise AlphaContractError("HG006 S002 D001 census SHA mismatch")
    if d001b_summary.get("corpus_id") != EXPECTED_D001B_ID:
        raise AlphaContractError("HG006 S002 requires frozen D001B corpus")
    if d001b_summary.get("corpus_sha256") != EXPECTED_D001B_SHA:
        raise AlphaContractError("HG006 S002 D001B corpus SHA mismatch")

    for payload, label in (
        (selection, "S001"),
        (d001, "D001"),
        (d001b_summary, "D001B"),
    ):
        for field in (
            "completion_probabilities_assigned",
            "return_outcomes_opened",
            "portfolio_eligibility_allowed",
            "live_capital_allowed",
        ):
            if payload.get(field) is not False:
                raise AlphaContractError(
                    f"HG006 S002 requires {label} {field}=false"
                )
    if selection.get("historical_terminal_labels_opened") is not False:
        raise AlphaContractError(
            "HG006 S002 requires S001 historical_terminal_labels_opened=false"
        )
    if d001b_summary.get("historical_terminal_labels_opened") is not False:
        raise AlphaContractError(
            "HG006 S002 requires D001B historical_terminal_labels_opened=false"
        )

    rows = selection.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 S002 S001 rows unavailable")

    events = d001.get("events")
    if not isinstance(events, list):
        raise AlphaContractError("HG006 S002 D001 events unavailable")
    event_index: dict[str, dict[str, Any]] = {}
    for row in events:
        if not isinstance(row, dict):
            raise TypeError("HG006 S002 D001 event must be object")
        event_id = str(row.get("announcement_id") or "")
        if not event_id or event_id in event_index:
            raise AlphaContractError("HG006 S002 D001 event IDs must be unique")
        event_index[event_id] = row
    return rows, event_index


def _segment_score(segment: dict[str, Any]) -> tuple[int, int, str]:
    hits = phrase_hits(str(segment.get("text") or ""))
    return (
        int(hits["distinct_group_count"]),
        int(hits["total_phrase_occurrences"]),
        str(segment.get("segment_id") or ""),
    )


def _select_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not segments:
        return []
    enriched = []
    for order, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise TypeError("HG006 S002 text segment must be object")
        segment_id = str(segment.get("segment_id") or "")
        text = segment.get("text")
        text_sha = str(segment.get("text_sha256") or "")
        if not segment_id or not isinstance(text, str) or len(text_sha) != 64:
            raise AlphaContractError("HG006 S002 text segment is incomplete")
        hits = phrase_hits(text)
        enriched.append(
            {
                "order": order,
                "segment": segment,
                "hits": hits,
            }
        )

    keep_ids = {
        enriched[0]["segment"]["segment_id"],
        enriched[-1]["segment"]["segment_id"],
    }
    keep_ids.update(
        row["segment"]["segment_id"]
        for row in enriched
        if row["hits"]["terminal_match"]
    )

    candidates = [
        row
        for row in enriched
        if row["segment"]["segment_id"] not in keep_ids
        and row["hits"]["total_phrase_occurrences"] > 0
    ]
    candidates.sort(
        key=lambda row: (
            -int(row["hits"]["distinct_group_count"]),
            -int(row["hits"]["total_phrase_occurrences"]),
            int(row["order"]),
            str(row["segment"]["segment_id"]),
        )
    )
    keep_ids.update(
        row["segment"]["segment_id"]
        for row in candidates[:MAX_ADDITIONAL_SEGMENTS]
    )

    selected = []
    for row in enriched:
        if row["segment"]["segment_id"] not in keep_ids:
            continue
        segment = row["segment"]
        selected.append(
            {
                "segment_id": segment["segment_id"],
                "kind": segment.get("kind"),
                "locator": segment.get("locator"),
                "text": segment["text"],
                "text_sha256": segment["text_sha256"],
                "phrase_hits": row["hits"],
                "source_order": row["order"],
            }
        )
    return selected


def _document_hit_summary(segments: list[dict[str, Any]]) -> dict[str, Any]:
    group_counts: Counter[str] = Counter()
    phrase_count = 0
    terminal = False
    for segment in segments:
        hits = phrase_hits(str(segment.get("text") or ""))
        group_counts.update(hits["groups"].keys())
        phrase_count += int(hits["total_phrase_occurrences"])
        terminal = terminal or bool(hits["terminal_match"])
    return {
        "distinct_group_count": len(group_counts),
        "total_phrase_occurrences": phrase_count,
        "terminal_match": terminal,
        "group_segment_counts": dict(sorted(group_counts.items())),
    }


def build_stage_evidence_pack(
    *,
    selection: dict[str, Any],
    d001: dict[str, Any],
    d001b_summary: dict[str, Any],
    text_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    selection_rows, event_index = _validate_inputs(
        selection, d001, d001b_summary
    )
    selected_by_id = {
        str(row["chronology_id"]): row
        for row in selection_rows
    }
    if len(selected_by_id) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 S002 chronology IDs must be unique")

    docs_by_chronology: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_doc_ids: set[str] = set()
    for row in text_rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 S002 D001B row must be object")
        doc_id = str(row.get("document_id") or "")
        if not doc_id or doc_id in seen_doc_ids:
            raise AlphaContractError("HG006 S002 D001B document IDs must be unique")
        seen_doc_ids.add(doc_id)
        chronology_ids = row.get("chronology_ids")
        if not isinstance(chronology_ids, list):
            raise AlphaContractError("HG006 S002 chronology_ids unavailable")
        for chronology_id_raw in chronology_ids:
            chronology_id = str(chronology_id_raw)
            if chronology_id in selected_by_id:
                docs_by_chronology[chronology_id].append(row)

    evidence_rows = []
    state_counts: Counter[str] = Counter()
    total_retained_docs = 0
    total_retained_segments = 0

    for chronology_id, chronology in sorted(selected_by_id.items()):
        symbol = str(chronology["symbol"])
        family = str(chronology["family"])
        chronology_event_ids = {str(v) for v in chronology["announcement_ids"]}
        source_docs = docs_by_chronology.get(chronology_id, [])

        doc_rows = []
        for doc in source_docs:
            if doc.get("extraction_state") != "READY":
                continue
            if symbol not in {str(v) for v in doc.get("symbols", [])}:
                raise AlphaContractError(
                    f"HG006 S002 document crosses symbol: {chronology_id}"
                )
            if family not in {str(v) for v in doc.get("families", [])}:
                raise AlphaContractError(
                    f"HG006 S002 document crosses family: {chronology_id}"
                )
            linked_event_ids = sorted(
                chronology_event_ids.intersection(
                    str(v) for v in doc.get("event_ids", [])
                )
            )
            if not linked_event_ids:
                raise AlphaContractError(
                    f"HG006 S002 document has no chronology event link: {chronology_id}"
                )
            event_timestamps = [
                _iso_timestamp(event_index[event_id]["exchange_published_at_utc"])
                for event_id in linked_event_ids
            ]
            timestamp = min(event_timestamps)
            segments = doc.get("segments")
            if not isinstance(segments, list):
                raise AlphaContractError("HG006 S002 READY doc segments unavailable")
            hits = _document_hit_summary(segments)
            doc_rows.append(
                {
                    "document_id": str(doc["document_id"]),
                    "chronology_timestamp_utc": timestamp,
                    "event_ids": linked_event_ids,
                    "segment_source_count": len(segments),
                    "hit_summary": hits,
                    "segments": segments,
                    "segment_manifest_sha256": str(
                        doc.get("segment_manifest_sha256") or ""
                    ),
                }
            )

        if not doc_rows:
            state = "TEXT_UNAVAILABLE"
            retained_docs: list[dict[str, Any]] = []
        else:
            state = "EVIDENCE_READY"
            doc_rows.sort(
                key=lambda row: (
                    row["chronology_timestamp_utc"],
                    row["document_id"],
                )
            )
            keep_ids = {
                doc_rows[0]["document_id"],
                doc_rows[-1]["document_id"],
            }
            keep_ids.update(
                row["document_id"]
                for row in doc_rows
                if row["hit_summary"]["terminal_match"]
            )
            candidates = [
                row
                for row in doc_rows
                if row["document_id"] not in keep_ids
                and row["hit_summary"]["total_phrase_occurrences"] > 0
            ]
            candidates.sort(
                key=lambda row: (
                    -int(row["hit_summary"]["distinct_group_count"]),
                    -int(row["hit_summary"]["total_phrase_occurrences"]),
                    row["chronology_timestamp_utc"],
                    row["document_id"],
                )
            )
            keep_ids.update(
                row["document_id"]
                for row in candidates[:MAX_ADDITIONAL_DOCUMENTS]
            )
            retained_docs = []
            for row in doc_rows:
                if row["document_id"] not in keep_ids:
                    continue
                selected_segments = _select_segments(row["segments"])
                if not selected_segments:
                    raise AlphaContractError(
                        "HG006 S002 retained document has no selected segment"
                    )
                retained_docs.append(
                    {
                        "document_id": row["document_id"],
                        "chronology_timestamp_utc": row[
                            "chronology_timestamp_utc"
                        ],
                        "event_ids": row["event_ids"],
                        "segment_manifest_sha256": row[
                            "segment_manifest_sha256"
                        ],
                        "source_segment_count": row["segment_source_count"],
                        "hit_summary": row["hit_summary"],
                        "selected_segments": selected_segments,
                    }
                )

        total_retained_docs += len(retained_docs)
        total_retained_segments += sum(
            len(row["selected_segments"]) for row in retained_docs
        )
        state_counts[state] += 1
        evidence = {
            "chronology_id": chronology_id,
            "symbol": symbol,
            "family": family,
            "source_event_count": int(chronology["event_count"]),
            "source_document_count": len(source_docs),
            "text_ready_source_document_count": len(doc_rows),
            "evidence_state": state,
            "retained_document_count": len(retained_docs),
            "retained_documents": retained_docs,
        }
        evidence["chronology_evidence_sha256"] = digest(evidence)
        evidence_rows.append(evidence)

    unavailable = [
        row["chronology_id"]
        for row in evidence_rows
        if row["evidence_state"] == "TEXT_UNAVAILABLE"
    ]
    gates = {
        "complete_300_chronology_accounting": len(evidence_rows)
        == EXPECTED_CHRONOLOGY_COUNT,
        "minimum_298_evidence_ready": state_counts["EVIDENCE_READY"] >= 298,
        "maximum_2_text_unavailable": len(unavailable) <= 2,
        "retained_documents_have_segments": all(
            all(doc["selected_segments"] for doc in row["retained_documents"])
            for row in evidence_rows
            if row["evidence_state"] == "EVIDENCE_READY"
        ),
    }

    output = {
        "schema_version": 1,
        "pack_id": PACK_ID,
        "classification": "DETERMINISTIC_HISTORICAL_STAGE_EVIDENCE_PACK_NOT_LABELS",
        "source_selection_sha256": EXPECTED_SELECTION_SHA,
        "source_d001_census_sha256": EXPECTED_D001_SHA,
        "source_d001b_corpus_sha256": EXPECTED_D001B_SHA,
        "chronology_count": len(evidence_rows),
        "state_counts": dict(sorted(state_counts.items())),
        "text_unavailable_chronology_ids": sorted(unavailable),
        "retained_document_count": total_retained_docs,
        "retained_segment_count": total_retained_segments,
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_hg006_l001": all(gates.values()),
        "chronologies": evidence_rows,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["pack_sha256"] = digest(output)
    return output
