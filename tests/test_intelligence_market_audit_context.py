from __future__ import annotations

from marketlab.intelligence_market_audit_context import apply_prospective_capture_context
from marketlab.intelligence_prospective_news import empty_news_ledger, merge_news_ledger


def report():
    return {
        "session_date": "2026-09-18",
        "prior_session_date": "2026-09-17",
        "captured_at": "2026-09-18T13:30:00+00:00",
        "movers": [{"news_audit": {"coverage_class": "NOT_DISCOVERED", "matched_item_ids": []}}],
        "coverage_class_counts": {"NOT_DISCOVERED": 1},
        "interpretation_contract": {},
        "report_sha256": "old",
    }


def capture(capture_id, started, completed):
    return {
        "capture_id": capture_id,
        "started_at": started,
        "captured_at": completed,
        "run_id": capture_id,
        "run_status": "BOUNDED_CAPTURE_COMPLETE",
        "discovery_status": "DISCOVERY_CAPTURE_COMPLETE",
        "identity_session": "2026-09-17",
        "identity_raw_sha256": "a" * 64,
        "source_status_counts": {},
        "discovery_source_status_counts": {},
        "document_status_counts": {},
        "source_states": {},
        "discovery_source_states": {},
        "full_market_coverage": False,
        "live_capital_allowed": False,
    }


def test_no_capture_is_not_mislabelled_as_news_miss():
    result = apply_prospective_capture_context(report(), empty_news_ledger())
    assert result["coverage_class_counts"] == {"NO_SESSION_WINDOW_CAPTURE": 1}
    assert result["prospective_capture_context"]["preopen_capture_count"] == 0


def test_intraday_only_capture_discloses_preopen_gap():
    ledger = merge_news_ledger(
        empty_news_ledger(),
        capture("c1", "2026-09-18T05:00:00+00:00", "2026-09-18T05:05:00+00:00"),
        [],
    )
    result = apply_prospective_capture_context(report(), ledger)
    assert result["coverage_class_counts"] == {"NO_PREOPEN_CAPTURE_NOT_DISCOVERED": 1}
    assert result["prospective_capture_context"]["intraday_capture_count"] == 1


def test_preopen_capture_allows_true_not_discovered_classification():
    ledger = merge_news_ledger(
        empty_news_ledger(),
        capture("c1", "2026-09-18T02:30:00+00:00", "2026-09-18T02:35:00+00:00"),
        [],
    )
    result = apply_prospective_capture_context(report(), ledger)
    assert result["coverage_class_counts"] == {"NOT_DISCOVERED": 1}
    assert result["prospective_capture_context"]["preopen_capture_count"] == 1


def test_matched_item_class_is_not_overwritten_by_capture_context():
    value = report()
    value["movers"][0]["news_audit"] = {
        "coverage_class": "SYSTEM_PREOPEN_HIT",
        "matched_item_ids": ["item"],
    }
    ledger = merge_news_ledger(
        empty_news_ledger(),
        capture("c1", "2026-09-18T02:30:00+00:00", "2026-09-18T02:35:00+00:00"),
        [],
    )
    result = apply_prospective_capture_context(value, ledger)
    assert result["coverage_class_counts"] == {"SYSTEM_PREOPEN_HIT": 1}


def test_degraded_preopen_capture_is_not_scored_as_clean_miss():
    degraded = {
        **capture("c1", "2026-09-18T02:30:00+00:00", "2026-09-18T02:35:00+00:00"),
        "discovery_status": "DISCOVERY_DEGRADED",
        "discovery_source_status_counts": {"BLOCKED": 1, "SNAPSHOT_CAPTURED": 6},
        "discovery_source_states": {"nse-announcements": ["BLOCKED"]},
    }
    ledger = merge_news_ledger(empty_news_ledger(), degraded, [])
    result = apply_prospective_capture_context(report(), ledger)
    assert result["coverage_class_counts"] == {
        "PREOPEN_CAPTURE_DEGRADED_NOT_DISCOVERED": 1
    }
    assert result["prospective_capture_context"]["healthy_preopen_capture_count"] == 0
