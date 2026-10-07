from __future__ import annotations

from datetime import UTC, datetime, timedelta

from marketlab.hg006_d003_generator import (
    EXPECTED_EVENT_COUNT,
    build_deterministic_episode_threading,
)


def _inputs(*, conflict: bool = False) -> tuple[dict, dict]:
    chronologies = []
    for index in range(300):
        family = (
            "PREFERENTIAL_WARRANT"
            if index < 150
            else "SCHEME_REORGANISATION"
        )
        chronologies.append(
            {
                "chronology_id": f"C{index:03d}",
                "symbol": f"S{index:03d}",
                "family": family,
                "evidence_state": (
                    "TEXT_UNAVAILABLE" if index >= 298 else "EVIDENCE_READY"
                ),
                "retained_documents": [],
            }
        )

    rows = []
    event_index = 0
    base = datetime(2025, 1, 1, tzinfo=UTC)
    for row_index in range(1448):
        chronology_index = row_index % 298
        chronology = chronologies[chronology_index]
        event_count = 2 if row_index < 116 else 1
        event_ids = []
        for _ in range(event_count):
            event_ids.append(f"E{event_index:04d}")
            event_index += 1

        document_id = f"D{row_index:04d}"
        family = chronology["family"]
        if family == "PREFERENTIAL_WARRANT":
            anchors = [
                {
                    "anchor_type": "OTHER_EXPLICIT_TRANSACTION_REFERENCE",
                    "value": f"WREF-{row_index:04d}",
                    "evidence_segment_ids": [f"{document_id}:seg:1"],
                }
            ]
        else:
            anchors = [
                {
                    "anchor_type": "SCHEME_OR_TRANSACTION_NAME",
                    "value": f"SCHEME-{row_index:04d}",
                    "evidence_segment_ids": [f"{document_id}:seg:1"],
                }
            ]

        if conflict and row_index == 150:
            anchors = [
                {
                    "anchor_type": "EFFECTIVE_DATE",
                    "value": "2025-07-01",
                    "evidence_segment_ids": [f"{document_id}:seg:1"],
                },
                {
                    "anchor_type": "SCHEME_OR_TRANSACTION_NAME",
                    "value": "SCHEME-A",
                    "evidence_segment_ids": [f"{document_id}:seg:1"],
                },
                {
                    "anchor_type": "SCHEME_OR_TRANSACTION_NAME",
                    "value": "SCHEME-B",
                    "evidence_segment_ids": [f"{document_id}:seg:1"],
                },
            ]

        extraction = {
            "document_id": document_id,
            "event_ids": event_ids,
            "symbol": chronology["symbol"],
            "family": family,
            "transaction_anchors": anchors,
        }
        rows.append(
            {
                "status": "VALIDATED",
                "chronology_id": chronology["chronology_id"],
                "document_id": document_id,
                "symbol": chronology["symbol"],
                "family": family,
                "validated_response": {
                    "validated_extraction": extraction,
                },
            }
        )
        chronology["retained_documents"].append(
            {
                "document_id": document_id,
                "chronology_timestamp_utc": (
                    base + timedelta(days=row_index)
                ).isoformat().replace("+00:00", "Z"),
                "event_ids": event_ids,
            }
        )

    assert event_index == EXPECTED_EVENT_COUNT
    ingestion = {
        "execution_id": "HG006-L001-P2-v1",
        "ingestion_sha256": (
            "2188bf803f2088cd10f26892f92f1a82fc810543ad9679c4fc20534e2a3e59e6"
        ),
        "full_ingestion_pass": True,
        "historical_terminal_labels_opened": False,
        "return_outcomes_opened": False,
        "rows": rows,
    }
    evidence = {
        "pack_id": "HG006-S002-v1",
        "pack_sha256": (
            "e99f270bf48b76bb72f3e2734abddd34bcc580cb1583086cc73e50759e23766e"
        ),
        "historical_terminal_labels_opened": False,
        "return_outcomes_opened": False,
        "chronologies": chronologies,
    }
    return ingestion, evidence


def test_generator_accounts_for_all_events_and_groups_shared_document_events() -> None:
    ingestion, evidence = _inputs()
    result = build_deterministic_episode_threading(
        ingestion=ingestion,
        evidence_pack=evidence,
    )

    assert result["source_event_count"] == 1564
    assert (
        result["episode_assigned_event_count"]
        + result["thread_ambiguous_event_count"]
        == 1564
    )
    assert result["episode_count"] < 1564
    assert result["feasibility_pass"] is True
    assert result["promotion_allowed_to_d002_terminal_labeling"] is True
    assert result["historical_terminal_labels_opened"] is False
    assert result["return_outcomes_opened"] is False


def test_hard_identity_conflict_is_excluded_as_ambiguous() -> None:
    ingestion, evidence = _inputs(conflict=True)
    result = build_deterministic_episode_threading(
        ingestion=ingestion,
        evidence_pack=evidence,
    )

    conflicted = [
        row
        for row in result["ambiguous_events"]
        if row["reason"] == "HARD_IDENTITY_ANCHOR_CONFLICT"
    ]
    assert conflicted
    assert all(
        row["family"] == "SCHEME_REORGANISATION" for row in conflicted
    )
    assert result["feasibility_pass"] is True


def test_timestamps_are_retained_but_not_used_as_link_tokens() -> None:
    ingestion, evidence = _inputs()
    result = build_deterministic_episode_threading(
        ingestion=ingestion,
        evidence_pack=evidence,
    )
    episode = result["episodes"][0]
    assert episode["earliest_observed_at_utc"]
    assert episode["latest_observed_at_utc"]
    assert all(
        row["token_type"] not in {"TIMESTAMP", "TIME_GAP"}
        for row in episode["strong_anchor_support"]
    )



def test_ingestion_envelope_identity_mismatch_fails_closed() -> None:
    ingestion, evidence = _inputs()
    ingestion["rows"][0]["symbol"] = "WRONG"

    import pytest

    from marketlab.alpha import AlphaContractError

    with pytest.raises(AlphaContractError, match="symbol identity envelope mismatch"):
        build_deterministic_episode_threading(
            ingestion=ingestion,
            evidence_pack=evidence,
        )
