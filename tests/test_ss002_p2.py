from __future__ import annotations

from marketlab.ss002_p2 import build_p2_census


def _base_event(index: int, *, desc: str, attachment: str, state: str) -> dict:
    return {
        "announcement_id": f"id-{index}",
        "symbol": "AAA",
        "seq_id": str(index),
        "exchange_published_at_utc": "2026-06-01T00:00:00Z",
        "desc": desc,
        "attchmntText": "text",
        "attchmntFile": attachment,
        "mapping_state": "CURRENT_IDENTITY_MAPPED",
        "current_context": {"isin": "INE000000001"},
        "p1_actionability_state": state,
        "p1_special_situation_categories": ["SCHEME_REORGANISATION"],
    }


def _p1() -> dict:
    events = [
        _base_event(
            i,
            desc="Announcement",
            attachment="https://nsearchives.nseindia.com/corporate/a.pdf",
            state="CURRENT_ACTIONABLE_PRIMARY",
        )
        for i in range(6435)
    ]
    return {
        "census_id": "SS002-D001-P1-v1",
        "census_sha256": (
            "2d0f39e218cdb1784d390a45685f0e787cff9edb4443a2c395d8806219213e2c"
        ),
        "events": events,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_no_attachment_news_query_is_demoted() -> None:
    p1 = _p1()
    p1["events"][0] = _base_event(
        0,
        desc="News Verification",
        attachment="-",
        state="CURRENT_ACTIONABLE_PRIMARY",
    )
    result = build_p2_census(p1)
    row = next(row for row in result["events"] if row["announcement_id"] == "id-0")
    assert row["p2_actionability_state"] == "CURRENT_UNCONFIRMED_NEWS_QUERY"
    assert result["demoted_unconfirmed_news_query_count"] == 1
    assert result["current_actionable_primary_event_count"] == 6434


def test_attached_issuer_news_verification_response_remains_primary() -> None:
    p1 = _p1()
    p1["events"][0] = _base_event(
        0,
        desc="News Verification",
        attachment="https://nsearchives.nseindia.com/corporate/clarification.pdf",
        state="CURRENT_ACTIONABLE_PRIMARY",
    )
    result = build_p2_census(p1)
    row = next(row for row in result["events"] if row["announcement_id"] == "id-0")
    assert row["p2_actionability_state"] == "CURRENT_ACTIONABLE_PRIMARY"
    assert result["feasibility_pass"] is True


def test_non_primary_state_is_preserved() -> None:
    p1 = _p1()
    p1["events"][0]["p1_actionability_state"] = "CURRENT_CONTEXT_ONLY"
    result = build_p2_census(p1)
    row = next(row for row in result["events"] if row["announcement_id"] == "id-0")
    assert row["p2_actionability_state"] == "CURRENT_CONTEXT_ONLY"
