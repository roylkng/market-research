from __future__ import annotations

import copy
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab import ss002_daily_research_inbox as inbox

IST = ZoneInfo("Asia/Kolkata")
DAYS = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]


def _event(day: str, index: int) -> dict:
    # Use an IST-local noon publication with an explicit UTC offset.
    stamp = datetime.fromisoformat(day + "T12:00:00+05:30")
    entries = [
        ("AAA", "INE000A01001", "SYMBOL_IN_EQ_MASTER_AT_CAPTURE", "BUYBACK"),
        ("AAA", "INE000A01001", "SYMBOL_IN_EQ_MASTER_AT_CAPTURE", "BUYBACK"),
        ("CCC", None, "ARCHIVAL_OR_UNMATCHED_AT_CAPTURE", "DELISTING"),
        ("DDD", "INE000D01001", "SYMBOL_IN_EQ_MASTER_AT_CAPTURE", "RIGHTS_ISSUE"),
    ]
    symbol, isin, mapping, category = entries[index]
    url = "https://nsearchives.nseindia.com/corporate/offer.pdf" if index == 0 else None
    return {
        "announcement_id": f"ANN{index}",
        "exchange_published_at_utc": stamp.astimezone(
            ZoneInfo("UTC")
        ).isoformat().replace("+00:00", "Z"),
        "symbol": symbol,
        "current_eq_isin_at_capture": isin,
        "current_eq_name_at_capture": symbol,
        "mapping_state": mapping,
        "category_hints_only": [category],
        "approved_attachment_url": url,
        "attachment_state": "OFFICIAL_URL" if url else "ABSENT",
        "source_raw_sha256": "a" * 64,
        "economic_relevance_verified": False,
    }


def _sources(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict]:
    captures = {}
    expected = {}
    for index, day in enumerate(DAYS):
        event = _event(day, index)
        capture = {
            "schema_version": 1,
            "capture_id": f"SS002-P001-{day}-v1",
            "contract_id": "SS002-P001-v1",
            "source_day_ist": day,
            "source_lag_state": "NEXT_DAY_SOURCE_CAPTURE",
            "candidate_event_count": 1,
            "candidate_current_eq_event_count": int(
                event["mapping_state"] == "SYMBOL_IN_EQ_MASTER_AT_CAPTURE"
            ),
            "announcement_count": 1,
            "candidate_events": [event],
            "announcements": [{"announcement_id": event["announcement_id"]}],
            "model_inference_executed": False,
            "return_outcomes_opened": False,
            "model_fitted": False,
            "share_action_clearance_proven": False,
            "market_capitalization_calculated": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        }
        capture["capture_sha256"] = digest(capture)
        captures[day] = capture
        expected[day] = capture["capture_sha256"]

    router = {
        "router_id": "HG001-D001-v1",
        "identity_count": 2,
        "rows": [
            {
                "symbol": "AAA",
                "isin": "INE000A01001",
                "active_opportunity_lane_count": 2,
                "active_opportunity_lanes": [
                    "ASSET_OR_CAPACITY_ANOMALY", "EARNINGS_INFLECTION"
                ],
                "research_route": "CONVERGENT_DEEP_DIVE",
                "governance_caution_flags": ["PROMOTER_PLEDGE_PRESENT"],
                "asset_caution_flags": [],
                "liquidity_band": "L3_2_TO_5CR",
                "in_existing_u001": False,
            },
            {
                "symbol": "BBB",
                "isin": "INE000B01001",
                "active_opportunity_lane_count": 0,
                "active_opportunity_lanes": [],
                "research_route": "BACKLOG_NO_ACTIVE_LANE",
                "governance_caution_flags": [],
                "asset_caution_flags": [],
                "liquidity_band": "L4_1_TO_2CR",
                "in_existing_u001": False,
            },
        ],
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    router["router_sha256"] = digest(router)

    monkeypatch.setattr(inbox, "SOURCE_CAPTURE_SHAS", expected)
    monkeypatch.setattr(inbox, "EXPECTED_EVENT_COUNT", 4)
    monkeypatch.setattr(inbox, "EXPECTED_CURRENT_EQ_COUNT", 3)
    monkeypatch.setattr(inbox, "EXPECTED_HG001_COUNT", 2)
    monkeypatch.setattr(inbox, "EXPECTED_HG001_SHA", router["router_sha256"])
    return captures, router


def test_daily_inbox_preserves_all_events_and_source_only_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captures, router = _sources(monkeypatch)
    result = inbox.build_daily_research_inbox(captures, router)
    assert result["source_event_count"] == 4
    assert result["current_eq_at_capture_event_count"] == 3
    assert result["archival_or_unmatched_count"] == 1
    assert result["exact_hg001_identity_match_count"] == 2
    assert result["document_intake_ready_count"] == 1
    assert result["prior_governance_caution_event_count"] == 2
    assert result["thread_count"] == 3
    assert result["source_only_gate_pass"] is True
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False

    states = [row["research_attention_state"] for row in result["events"]]
    assert states == [
        "CONVERGENT_PRIOR_RESEARCH",
        "CONVERGENT_PRIOR_RESEARCH",
        "ARCHIVAL_OR_UNMATCHED",
        "IDENTITY_REVIEW_REQUIRED",
    ]
    assert result["events"][0]["historical_research_context"][
        "governance_caution_flags"
    ] == ["PROMOTER_PLEDGE_PRESENT"]
    assert result["events"][2]["historical_research_context"] is None


def test_tampered_capture_fails_sha_check(monkeypatch: pytest.MonkeyPatch) -> None:
    captures, router = _sources(monkeypatch)
    altered = copy.deepcopy(captures)
    altered[DAYS[0]]["candidate_events"][0]["symbol"] = "FAKE"
    with pytest.raises(AlphaContractError, match="tampered source"):
        inbox.build_daily_research_inbox(altered, router)


def test_identity_drift_never_inherits_old_governance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captures, router = _sources(monkeypatch)
    altered = copy.deepcopy(captures)
    altered[DAYS[0]]["candidate_events"][0]["current_eq_isin_at_capture"] = (
        "INE000A01099"
    )
    altered[DAYS[0]]["capture_sha256"] = digest({
        k: v for k, v in altered[DAYS[0]].items() if k != "capture_sha256"
    })
    monkeypatch.setitem(inbox.SOURCE_CAPTURE_SHAS, DAYS[0], altered[DAYS[0]]["capture_sha256"])

    result = inbox.build_daily_research_inbox(altered, router)
    first = result["events"][0]
    assert first["research_attention_state"] == "IDENTITY_REVIEW_REQUIRED"
    assert first["historical_research_context"] is None
    assert first["document_intake_state"] == "DOCUMENT_INTAKE_READY"


def test_invalid_official_url_never_becomes_document_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captures, router = _sources(monkeypatch)
    altered = copy.deepcopy(captures)
    altered[DAYS[0]]["candidate_events"][0]["approved_attachment_url"] = (
        "https://attacker.example/offer.pdf"
    )
    altered[DAYS[0]]["capture_sha256"] = digest({
        k: v for k, v in altered[DAYS[0]].items() if k != "capture_sha256"
    })
    monkeypatch.setitem(inbox.SOURCE_CAPTURE_SHAS, DAYS[0], altered[DAYS[0]]["capture_sha256"])
    with pytest.raises(AlphaContractError, match="official URL classification is invalid"):
        inbox.build_daily_research_inbox(altered, router)
