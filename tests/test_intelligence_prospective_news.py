from __future__ import annotations

from datetime import UTC, datetime

import pytest

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_prospective_news import (
    capture_from_store,
    captures_for_audit,
    empty_news_ledger,
    merge_news_ledger,
    observations_for_audit,
    validate_news_ledger,
)
from marketlab.intelligence_store import ResearchStore, digest


def news_item(item_id="item-1", first_seen="2026-09-18T02:30:00+00:00", symbols=None):
    return {
        "item_id": item_id, "resource_key": "resource-1", "source_id": "source-1",
        "source_class": "EDITORIAL_HEADLINES", "first_seen_at": first_seen,
        "processed_at": first_seen,
        "publication": {"value": "2026-09-18T01:30:00+00:00", "precision": "SECOND", "raw": ""},
        "title": "Synthetic company update",
        "mentions": {"panel_symbols": symbols or ["AAA"], "unverified_nse_symbols": [],
                     "bse_codes_for_review": []},
        "topics": [{"topic": "ORDER_CUSTOMER"}],
    }


def seed_run(
    store, *, item=None, critical=None, auxiliary=None, status="BOUNDED_CAPTURE_COMPLETE"
):
    item = item or news_item()
    store.append("news_item", item["item_id"], item)
    attempt = {"attempt_id": "attempt-1", "source_id": item["source_id"], "stage": "DISCOVERY",
               "status": "SNAPSHOT_CAPTURED", "started_at": "2026-09-18T02:29:00+00:00",
               "completed_at": "2026-09-18T02:31:00+00:00"}
    store.append("news_attempt", attempt["attempt_id"], attempt)
    core = {"started_at": "2026-09-18T02:29:00+00:00", "completed_at": "2026-09-18T02:32:00+00:00",
            "configuration_sha256": "a" * 64,
            "coverage_critical_source_ids": critical or [item["source_id"]],
            "auxiliary_source_ids": auxiliary or [],
            "attempt_ids": [attempt["attempt_id"]],
            "deferred": [], "selected_item_ids": [], "status": status,
            "full_market_coverage": False, "live_capital_allowed": False,
            "version": "NEWS-DISCOVERY-V1"}
    core["run_id"] = digest(core)
    store.append("news_run", core["run_id"], core)


def test_capture_seals_compact_metadata_without_headline_text(tmp_path):
    with ResearchStore(tmp_path) as store:
        seed_run(store)
        capture, observations = capture_from_store(
            store, identity_session="2026-09-17", identity_raw_sha256="b" * 64
        )
    assert capture["identity_session"] == "2026-09-17"
    assert capture["discovery_status"] == "DISCOVERY_CAPTURE_COMPLETE"
    assert observations[0]["mentions"]["panel_symbols"] == ["AAA"]
    assert "title" not in observations[0]
    assert len(observations[0]["title_sha256"]) == 64


def test_repeated_semantic_observation_does_not_reset_first_seen():
    ledger = empty_news_ledger()
    capture = {"capture_id": "c1", "started_at": "2026-09-18T02:29:00+00:00",
               "captured_at": "2026-09-18T02:32:00+00:00", "run_id": "r1",
               "run_status": "BOUNDED_CAPTURE_COMPLETE",
               "discovery_status": "DISCOVERY_CAPTURE_COMPLETE",
               "identity_session": "2026-09-17",
               "identity_raw_sha256": "b" * 64, "source_status_counts": {},
               "discovery_source_status_counts": {}, "document_status_counts": {},
               "source_states": {}, "discovery_source_states": {},
               "full_market_coverage": False, "live_capital_allowed": False}
    semantic = {"source_id": "s", "source_class": "X", "item_id": "i", "resource_key": "r",
                "publication": {"value": None, "precision": "UNKNOWN", "raw": ""},
                "title_sha256": "a" * 64, "mentions": {"panel_symbols": [],
                "official_nse_symbols": [], "unverified_nse_symbols": [], "bse_codes_for_review": []},
                "topics": []}
    observation = {**semantic, "capture_id": "c1", "first_seen_at": "2026-09-18T02:30:00+00:00",
                   "observation_id": digest(semantic)}
    merged = merge_news_ledger(ledger, capture, [observation])
    second_capture = {**capture, "capture_id": "c2", "started_at": "2026-09-18T05:59:00+00:00",
                      "captured_at": "2026-09-18T06:02:00+00:00", "run_id": "r2"}
    repeated = {**observation, "capture_id": "c2", "first_seen_at": "2026-09-18T06:00:00+00:00"}
    again = merge_news_ledger(merged, second_capture, [repeated])
    assert len(again["captures"]) == 2
    assert len(again["observations"]) == 1
    assert again["observations"][0]["first_seen_at"] == "2026-09-18T02:30:00+00:00"


def test_changed_resolution_is_new_observation_not_rewrite():
    ledger = empty_news_ledger()
    capture = {"capture_id": "c1", "started_at": "2026-09-18T02:29:00+00:00",
               "captured_at": "2026-09-18T02:32:00+00:00", "run_id": "r1",
               "run_status": "BOUNDED_CAPTURE_COMPLETE",
               "discovery_status": "DISCOVERY_CAPTURE_COMPLETE",
               "identity_session": "2026-09-17",
               "identity_raw_sha256": "b" * 64, "source_status_counts": {},
               "discovery_source_status_counts": {}, "document_status_counts": {},
               "source_states": {}, "discovery_source_states": {},
               "full_market_coverage": False, "live_capital_allowed": False}
    semantic = {"source_id": "s", "source_class": "X", "item_id": "i", "resource_key": "r",
                "publication": {"value": None, "precision": "UNKNOWN", "raw": ""},
                "title_sha256": "a" * 64, "mentions": {"panel_symbols": [],
                "official_nse_symbols": [], "unverified_nse_symbols": [], "bse_codes_for_review": []},
                "topics": []}
    first_row = {**semantic, "capture_id": "c1", "first_seen_at": "2026-09-18T02:30:00+00:00",
                 "observation_id": digest(semantic)}
    first = merge_news_ledger(ledger, capture, [first_row])
    changed_semantic = {**semantic, "mentions": {**semantic["mentions"], "panel_symbols": ["AAA"]}}
    changed = {**changed_semantic, "capture_id": "c2", "first_seen_at": "2026-09-18T06:00:00+00:00",
               "observation_id": digest(changed_semantic)}
    second_capture = {**capture, "capture_id": "c2", "started_at": "2026-09-18T05:59:00+00:00",
                      "captured_at": "2026-09-18T06:02:00+00:00", "run_id": "r2"}
    result = merge_news_ledger(first, second_capture, [changed])
    assert len(result["observations"]) == 2


def test_hash_tampering_and_cutoff_are_detected():
    ledger = empty_news_ledger()
    ledger["live_capital_allowed"] = True
    with pytest.raises(EvidenceError, match="hash"):
        validate_news_ledger(ledger)
    clean = empty_news_ledger()
    now = datetime.now(UTC).isoformat()
    assert observations_for_audit(clean, as_of=now) == []
    assert captures_for_audit(clean, as_of=now) == []


def test_discovery_failure_is_sealed_separately_from_document_health(tmp_path):
    with ResearchStore(tmp_path) as store:
        seed_run(store, critical=["source-1", "nse-announcements"])
        failure = {
            "attempt_id": "attempt-2", "source_id": "nse-announcements", "stage": "DISCOVERY",
            "status": "BLOCKED", "started_at": "2026-09-18T02:29:30+00:00",
            "completed_at": "2026-09-18T02:31:30+00:00",
        }
        store.append("news_attempt", failure["attempt_id"], failure)
        capture, _ = capture_from_store(
            store, identity_session="2026-09-17", identity_raw_sha256="b" * 64
        )
    assert capture["discovery_status"] == "DISCOVERY_DEGRADED"
    assert capture["discovery_source_status_counts"]["BLOCKED"] == 1


def test_auxiliary_source_failure_does_not_poison_core_capture_health(tmp_path):
    with ResearchStore(tmp_path) as store:
        seed_run(
            store,
            critical=["source-1"],
            auxiliary=["pib-rss"],
            status="PARTIAL_FAILURE",
        )
        failure = {
            "attempt_id": "attempt-pib",
            "source_id": "pib-rss",
            "stage": "DISCOVERY",
            "status": "BLOCKED",
            "started_at": "2026-09-18T02:29:30+00:00",
            "completed_at": "2026-09-18T02:31:30+00:00",
        }
        store.append("news_attempt", failure["attempt_id"], failure)
        capture, _ = capture_from_store(
            store, identity_session="2026-09-17", identity_raw_sha256="b" * 64
        )
    assert capture["run_status"] == "PARTIAL_FAILURE"
    assert capture["discovery_status"] == "DISCOVERY_CAPTURE_COMPLETE"
    assert capture["discovery_source_status_counts"]["BLOCKED"] == 1
    assert capture["critical_source_status_counts"] == {"SNAPSHOT_CAPTURED": 1}
