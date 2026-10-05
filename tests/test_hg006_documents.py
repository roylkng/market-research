from __future__ import annotations

import marketlab.hg006_documents as h


def _census() -> dict:
    events = [
        {
            "announcement_id": "E1",
            "symbol": "AAA",
            "historical_discrete_families": ["SCHEME_REORGANISATION"],
            "approved_attachment_url": "https://nsearchives.nseindia.com/a.pdf",
            "exchange_published_at_utc": "2024-01-01T10:00:00+00:00",
        },
        {
            "announcement_id": "E2",
            "symbol": "AAA",
            "historical_discrete_families": ["SCHEME_REORGANISATION"],
            "approved_attachment_url": "https://nsearchives.nseindia.com/a.pdf",
            "exchange_published_at_utc": "2024-02-01T10:00:00+00:00",
        },
        {
            "announcement_id": "E3",
            "symbol": "BBB",
            "historical_discrete_families": ["PREFERENTIAL_WARRANT"],
            "approved_attachment_url": None,
            "exchange_published_at_utc": "2024-03-01T10:00:00+00:00",
        },
        {
            "announcement_id": "E4",
            "symbol": "CCC",
            "historical_discrete_families": ["BUYBACK"],
            "approved_attachment_url": "https://nsearchives.nseindia.com/b.pdf",
            "exchange_published_at_utc": "2024-04-01T10:00:00+00:00",
        },
    ]
    chronologies = [
        {
            "chronology_id": "C1",
            "symbol": "AAA",
            "family": "SCHEME_REORGANISATION",
            "announcement_ids": ["E1", "E2"],
        },
        {
            "chronology_id": "C2",
            "symbol": "BBB",
            "family": "PREFERENTIAL_WARRANT",
            "announcement_ids": ["E3"],
        },
        {
            "chronology_id": "C3",
            "symbol": "CCC",
            "family": "BUYBACK",
            "announcement_ids": ["E4"],
        },
    ]
    return {
        "census_id": "HG006-D001-v1",
        "census_sha256": "test-sha",
        "retained_event_count": 4,
        "historical_chronology_count": 3,
        "events": events,
        "chronologies": chronologies,
        "completion_probabilities_assigned": False,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _patch_small(monkeypatch) -> None:
    monkeypatch.setattr(h, "EXPECTED_D001_SHA", "test-sha")
    monkeypatch.setattr(h, "EXPECTED_EVENT_COUNT", 4)
    monkeypatch.setattr(h, "EXPECTED_CHRONOLOGY_COUNT", 3)
    monkeypatch.setattr(h, "EXPECTED_SELECTED_CHRONOLOGY_COUNT", 2)


def test_selected_population_keeps_only_priority_families(monkeypatch) -> None:
    _patch_small(monkeypatch)
    selected = h.selected_source_population(_census())
    assert len(selected["chronologies"]) == 2
    assert [row["announcement_id"] for row in selected["events"]] == ["E1", "E2", "E3"]


def test_attachment_requests_deduplicate_same_url(monkeypatch) -> None:
    _patch_small(monkeypatch)
    requests, states = h.build_attachment_requests(_census())
    assert len(requests) == 1
    assert requests[0].event_ids == ("E1", "E2")
    assert requests[0].chronology_ids == ("C1",)
    assert len(states) == 3
    assert sum(row["attachment_state"] == "NO_APPROVED_ATTACHMENT" for row in states) == 1


def test_shard_is_deterministic() -> None:
    url = "https://nsearchives.nseindia.com/a.pdf"
    assert h.shard_for_url(url) == h.shard_for_url(url)
    assert 0 <= h.shard_for_url(url) < 8


def test_historical_corpus_passes_with_ready_document(monkeypatch) -> None:
    _patch_small(monkeypatch)
    census = _census()
    requests, _ = h.build_attachment_requests(census)
    evidence = [
        h.attachment_evidence(
            requests[0],
            raw=b"%PDF-1.7\nexample",
            error=None,
        )
    ]
    corpus = h.build_historical_document_corpus(
        census,
        evidence,
        captured_at_utc="2026-10-05T12:00:00Z",
    )
    assert corpus["selected_chronology_count"] == 2
    assert corpus["selected_event_count"] == 3
    assert corpus["attachment_ready_chronology_count"] == 1
    assert corpus["chronology_with_successful_document_count"] == 1
    assert corpus["feasibility_pass"] is True
    assert corpus["historical_terminal_labels_opened"] is False
    assert corpus["completion_probabilities_assigned"] is False


def test_failed_fetch_is_not_replaced(monkeypatch) -> None:
    _patch_small(monkeypatch)
    census = _census()
    requests, _ = h.build_attachment_requests(census)
    evidence = [
        h.attachment_evidence(
            requests[0],
            raw=None,
            error="HTTP 404",
        )
    ]
    corpus = h.build_historical_document_corpus(
        census,
        evidence,
        captured_at_utc="2026-10-05T12:00:00Z",
    )
    assert corpus["fetch_failure_count"] == 1
    assert corpus["feasibility_pass"] is False
    assert corpus["chronology_state_counts"]["DOCUMENT_FETCH_FAILED"] == 1
