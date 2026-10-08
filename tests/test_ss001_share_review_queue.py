from __future__ import annotations

import copy

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_share_review_queue import build_share_change_packets


def _payloads() -> tuple[dict, dict]:
    states = (
        ["BOTH_SOURCES_REVIEW_REQUIRED"] * 24
        + ["CORPORATE_ACTION_REVIEW_REQUIRED"] * 11
        + ["ANNOUNCEMENT_REVIEW_REQUIRED"] * 296
        + ["D005_SOURCE_NOT_READY"] * 359
        + ["NO_OBSERVED_TRIGGER_STILL_UNVERIFIED"] * 1629
    )
    rows = []
    events = []
    seq = 0
    for index, state in enumerate(states):
        symbol = f"S{index:04d}"
        actions = []
        announcements = []
        if state in {"BOTH_SOURCES_REVIEW_REQUIRED", "CORPORATE_ACTION_REVIEW_REQUIRED"}:
            actions = [
                {
                    "symbol": symbol,
                    "ex_date": "2026-09-15",
                    "subject": "Bonus",
                    "isin": "INE000000001",
                    "source_raw_sha256": "a" * 64,
                }
            ]
        if state in {"BOTH_SOURCES_REVIEW_REQUIRED", "ANNOUNCEMENT_REVIEW_REQUIRED"}:
            event_id = f"E{seq:04d}"
            seq += 1
            announcements = [
                {
                    "event_id": event_id,
                    "published_at_utc": "2026-09-20T10:00:00Z",
                    "categories": ["RIGHTS_ISSUE"],
                }
            ]
            events.append(
                {
                    "announcement_id": event_id,
                    "symbol": symbol,
                    "mapping_state": "CURRENT_INVESTABLE_IDENTITY",
                    "attachment_state": "READY",
                    "approved_attachment_url": (
                        f"https://nsearchives.nseindia.com/corporate/{event_id}.pdf"
                    ),
                }
            )
        rows.append(
            {
                "symbol": symbol,
                "review_state": state,
                "intervening_corporate_actions": actions,
                "intervening_announcement_candidates": announcements,
            }
        )

    for i in range(len(events), 2272):
        events.append(
            {
                "announcement_id": f"E{i:04d}",
                "symbol": f"OLD{i:04d}",
                "mapping_state": "ARCHIVAL_NONCURRENT_IDENTITY",
                "attachment_state": "ARCHIVAL_NOT_GATED",
                "approved_attachment_url": None,
            }
        )

    d006 = {
        "audit_id": "SS001-D006-v1",
        "audit_sha256": "b2aef97d107a1494adafa70d18321ee2e484d7b4796fe6ed7a7b0f5336f2f479",
        "identity_count": 2319,
        "d005_time_and_price_ready_count": 1960,
        "review_state_counts": {
            "ANNOUNCEMENT_REVIEW_REQUIRED": 296,
            "BOTH_SOURCES_REVIEW_REQUIRED": 24,
            "CORPORATE_ACTION_REVIEW_REQUIRED": 11,
            "D005_SOURCE_NOT_READY": 359,
            "NO_OBSERVED_TRIGGER_STILL_UNVERIFIED": 1629,
        },
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "rows": rows,
    }
    p2 = {
        "census_id": "SS002-D001-P2-v1",
        "census_sha256": "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071",
        "events": events,
    }
    for payload in (d006, p2):
        payload.update(
            {
                "return_outcomes_opened": False,
                "model_fitted": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )
    return d006, p2


def test_full_evidence_packets_preserve_all_source_states() -> None:
    d006, p2 = _payloads()
    queue = build_share_change_packets(d006_review=d006, p2_census=p2)
    assert queue["review_packet_count"] == 331
    assert queue["pilot_packet_count"] == 50
    assert queue["remaining_review_packet_count"] == 281
    assert queue["packets"][0]["review_state"] == "BOTH_SOURCES_REVIEW_REQUIRED"
    assert queue["packets"][23]["review_state"] == "BOTH_SOURCES_REVIEW_REQUIRED"
    assert queue["packets"][24]["review_state"] == "CORPORATE_ACTION_REVIEW_REQUIRED"
    assert queue["packets"][35]["review_state"] == "ANNOUNCEMENT_REVIEW_REQUIRED"
    assert sum(row["in_first_50_pilot"] for row in queue["packets"]) == 50
    assert all(not row["share_action_clearance_proven"] for row in queue["packets"])
    assert queue["market_capitalization_calculated"] is False


def test_exact_p2_identity_mismatch_fails_closed() -> None:
    d006, p2 = _payloads()
    p2["events"][0]["symbol"] = "WRONG"
    with pytest.raises(AlphaContractError, match="canonical event identity mismatch"):
        build_share_change_packets(d006_review=d006, p2_census=p2)


def test_unapproved_host_fails_closed() -> None:
    d006, p2 = _payloads()
    p2["events"][0]["approved_attachment_url"] = "https://invalid.example/document.pdf"
    with pytest.raises(AlphaContractError, match="READY NSE attachment URL invalid"):
        build_share_change_packets(d006_review=d006, p2_census=p2)


def test_source_hash_mismatch_fails_closed() -> None:
    d006, p2 = _payloads()
    broken = copy.deepcopy(d006)
    broken["audit_sha256"] = "0" * 64
    with pytest.raises(AlphaContractError, match="frozen D006 source"):
        build_share_change_packets(d006_review=broken, p2_census=p2)


def test_no_automatic_clearance_if_document_link_is_available() -> None:
    d006, p2 = _payloads()
    queue = build_share_change_packets(d006_review=d006, p2_census=p2)
    first = queue["packets"][0]
    assert first["source_packet_status"] == "NSE_LINKS_PRESENT"
    assert first["announcement_evidence"][0]["document_sha256_bound"] is False
    assert first["capitalization_calculation_allowed"] is False
