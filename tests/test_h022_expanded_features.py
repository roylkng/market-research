from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab import h022_expanded_features as expanded


def _candidate(deadline: bool = False, domain: str = "revenue") -> dict:
    return {
        "deadline_markers": ["next year"] if deadline else [],
        "domain_markers": [domain],
    }


def _record(
    source_id: str,
    symbol: str,
    published: str,
    count: int,
    *,
    membership: str,
    text_chars: int = 10_000,
) -> dict:
    candidates = [
        _candidate(deadline=index % 2 == 0, domain="revenue" if index % 2 == 0 else "margin")
        for index in range(count)
    ]
    return {
        "source_id": source_id,
        "symbol": symbol,
        "exchange_published_at_utc": published,
        "membership_status": membership,
        "signal_eligible": membership == "SIGNAL_ELIGIBLE",
        "candidate_count": count,
        "text_char_count": text_chars,
        "candidates": candidates,
    }


def _report(records: list[dict]) -> dict:
    return {"records": records}


def _patch_validation(monkeypatch: pytest.MonkeyPatch, count: int) -> None:
    monkeypatch.setattr(expanded, "validate_source_report", lambda _doc: None)
    monkeypatch.setattr(expanded, "EXPECTED_SOURCE_COUNT", count)


def test_context_call_can_be_prior_but_not_evaluation_event(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [
        _record(
            "s1",
            "AAA",
            "2025-09-10T03:00:00+00:00",
            1,
            membership="PRE_CHALLENGE_CONTEXT",
        ),
        _record(
            "s2",
            "AAA",
            "2025-11-10T03:00:00+00:00",
            3,
            membership="SIGNAL_ELIGIBLE",
        ),
    ]
    _patch_validation(monkeypatch, 2)
    panel = expanded.build_expanded_feature_panel(_report(records))
    by_id = {row["source_id"]: row for row in panel["records"]}
    assert by_id["s1"]["feature_status"] == "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
    assert by_id["s2"]["prior_source_id"] == "s1"
    assert by_id["s2"]["primary_signal"] == pytest.approx(2.0)
    assert by_id["s2"]["evaluation_eligible"] is True
    assert panel["challenge_evaluation_signal_count"] == 1


def test_nonmember_challenge_call_can_update_context_but_not_evaluate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [
        _record(
            "s1",
            "AAA",
            "2025-09-10T03:00:00+00:00",
            1,
            membership="PRE_CHALLENGE_CONTEXT",
        ),
        _record(
            "s2",
            "AAA",
            "2025-11-10T03:00:00+00:00",
            2,
            membership="CONTEXT_ONLY_NONMEMBER",
        ),
        _record(
            "s3",
            "AAA",
            "2026-04-10T03:00:00+00:00",
            5,
            membership="SIGNAL_ELIGIBLE",
        ),
    ]
    _patch_validation(monkeypatch, 3)
    panel = expanded.build_expanded_feature_panel(_report(records))
    by_id = {row["source_id"]: row for row in panel["records"]}
    assert by_id["s2"]["feature_status"] == "SIGNAL"
    assert by_id["s2"]["evaluation_eligible"] is False
    assert by_id["s3"]["prior_source_id"] == "s2"
    assert by_id["s3"]["primary_signal"] == pytest.approx(3.0)
    assert by_id["s3"]["evaluation_eligible"] is True


def test_equal_timestamp_calls_are_not_prior_to_each_other(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [
        _record("s1", "AAA", "2025-11-10T03:00:00+00:00", 1, membership="SIGNAL_ELIGIBLE"),
        _record("s2", "AAA", "2025-11-10T03:00:00+00:00", 2, membership="SIGNAL_ELIGIBLE"),
        _record("s3", "AAA", "2026-02-10T03:00:00+00:00", 3, membership="SIGNAL_ELIGIBLE"),
    ]
    _patch_validation(monkeypatch, 3)
    panel = expanded.build_expanded_feature_panel(_report(records))
    by_id = {row["source_id"]: row for row in panel["records"]}
    assert by_id["s1"]["feature_status"] == "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
    assert by_id["s2"]["feature_status"] == "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
    assert by_id["s3"]["feature_status"] == "NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP"


def test_zero_candidate_transcript_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [
        _record("s1", "AAA", "2025-09-10T03:00:00+00:00", 2, membership="PRE_CHALLENGE_CONTEXT"),
        _record("s2", "AAA", "2025-11-10T03:00:00+00:00", 0, membership="SIGNAL_ELIGIBLE"),
    ]
    _patch_validation(monkeypatch, 2)
    panel = expanded.build_expanded_feature_panel(_report(records))
    row = next(item for item in panel["records"] if item["source_id"] == "s2")
    assert row["primary_signal"] == pytest.approx(-2.0)
    assert row["current"]["deadline_share"] == 0.0
    assert row["evaluation_eligible"] is True


def test_panel_hash_detects_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [
        _record("s1", "AAA", "2025-09-10T03:00:00+00:00", 1, membership="PRE_CHALLENGE_CONTEXT"),
        _record("s2", "AAA", "2025-11-10T03:00:00+00:00", 2, membership="SIGNAL_ELIGIBLE"),
    ]
    _patch_validation(monkeypatch, 2)
    panel = expanded.build_expanded_feature_panel(_report(records))
    expanded.validate_expanded_feature_panel(panel)
    tampered = deepcopy(panel)
    tampered["records"][1]["primary_signal"] = 999.0
    with pytest.raises(expanded.ExpandedFeatureError, match="hash mismatch"):
        expanded.validate_expanded_feature_panel(tampered)
