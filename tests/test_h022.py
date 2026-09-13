from __future__ import annotations

from copy import deepcopy

import pytest

import marketlab.h022 as h022


def _candidate(source_id: str, symbol: str, published: str, *, deadline: bool = False, domain: str = "revenue") -> dict:
    return {
        "source_id": source_id,
        "symbol": symbol,
        "exchange_published_at_utc": published,
        "deadline_markers": ["next year"] if deadline else [],
        "domain_markers": [domain],
    }


def _record(
    source_id: str,
    symbol: str,
    published: str,
    candidate_count: int,
    *,
    text_chars: int = 10_000,
) -> dict:
    candidates = [
        _candidate(
            source_id,
            symbol,
            published,
            deadline=index % 2 == 0,
            domain=("revenue" if index % 2 == 0 else "margin"),
        )
        for index in range(candidate_count)
    ]
    return {
        "source_id": source_id,
        "symbol": symbol,
        "exchange_published_at_utc": published,
        "status": "TEXT_READY",
        "text_char_count": text_chars,
        "candidate_count": candidate_count,
        "candidates": candidates,
    }


def _report(records: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "rule_id": h022.SOURCE_RULE_ID,
        "rule_sha256": h022.SOURCE_RULE_SHA256,
        "source_bundle_sha256": h022.SOURCE_BUNDLE_SHA256,
        "report_sha256": h022.SOURCE_REPORT_SHA256,
        "processed_source_count": len(records),
        "candidate_count": sum(row["candidate_count"] for row in records),
        "complete": True,
        "freeze_blockers": [],
        "source_status_counts": {"TEXT_READY": len(records)},
        "records": records,
    }


def _patch_counts(monkeypatch: pytest.MonkeyPatch, report: dict) -> None:
    monkeypatch.setattr(h022, "EXPECTED_SOURCE_COUNT", report["processed_source_count"])
    monkeypatch.setattr(h022, "EXPECTED_CANDIDATE_COUNT", report["candidate_count"])


def test_primary_delta_uses_only_strictly_prior_call(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report(
        [
            _record("s1", "AAA", "2025-01-10T12:00:00+00:00", 1),
            _record("s2", "AAA", "2025-04-10T12:00:00+00:00", 3),
            _record("s3", "AAA", "2025-07-10T12:00:00+00:00", 20),
        ]
    )
    _patch_counts(monkeypatch, report)
    panel = h022.build_feature_panel(report)
    by_source = {row["source_id"]: row for row in panel["records"]}

    assert by_source["s1"]["feature_status"] == "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
    assert by_source["s2"]["prior_source_id"] == "s1"
    assert by_source["s2"]["primary_signal"] == pytest.approx(2.0)
    assert by_source["s3"]["prior_source_id"] == "s2"
    assert panel["outcome_data_attached"] is False


def test_equal_timestamp_calls_cannot_become_prior_to_each_other(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report(
        [
            _record("s1", "AAA", "2025-01-10T12:00:00+00:00", 1),
            _record("s2", "AAA", "2025-01-10T12:00:00+00:00", 2),
            _record("s3", "AAA", "2025-04-10T12:00:00+00:00", 3),
        ]
    )
    _patch_counts(monkeypatch, report)
    panel = h022.build_feature_panel(report)
    by_source = {row["source_id"]: row for row in panel["records"]}

    assert by_source["s1"]["feature_status"] == "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
    assert by_source["s2"]["feature_status"] == "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
    assert by_source["s3"]["feature_status"] == "NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP"


def test_zero_candidate_transcript_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report(
        [
            _record("s1", "AAA", "2025-01-10T12:00:00+00:00", 2),
            _record("s2", "AAA", "2025-04-10T12:00:00+00:00", 0),
        ]
    )
    _patch_counts(monkeypatch, report)
    panel = h022.build_feature_panel(report)
    row = next(item for item in panel["records"] if item["source_id"] == "s2")

    assert row["feature_status"] == "SIGNAL"
    assert row["current"]["forward_commitment_density_per_10k_chars"] == 0.0
    assert row["current"]["deadline_share"] == 0.0
    assert row["primary_signal"] == pytest.approx(-2.0)


def test_feature_panel_hash_detects_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report(
        [
            _record("s1", "AAA", "2025-01-10T12:00:00+00:00", 1),
            _record("s2", "AAA", "2025-04-10T12:00:00+00:00", 2),
        ]
    )
    _patch_counts(monkeypatch, report)
    panel = h022.build_feature_panel(report)
    h022.validate_feature_panel(panel)

    tampered = deepcopy(panel)
    tampered["records"][1]["primary_signal"] = 999.0
    with pytest.raises(h022.H022Error, match="hash mismatch"):
        h022.validate_feature_panel(tampered)


def test_source_report_rejects_future_candidate_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _record("s1", "AAA", "2025-01-10T12:00:00+00:00", 1)
    record["candidates"][0]["exchange_published_at_utc"] = "2025-01-11T12:00:00+00:00"
    report = _report([record])
    _patch_counts(monkeypatch, report)

    with pytest.raises(h022.H022Error, match="timestamp mismatch"):
        h022.build_feature_panel(report)


def test_challenge_split_is_fixed_by_publication_date(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report(
        [
            _record("s1", "AAA", "2025-09-30T23:59:59+00:00", 1),
            _record("s2", "AAA", "2025-10-01T00:00:00+00:00", 2),
        ]
    )
    _patch_counts(monkeypatch, report)
    panel = h022.build_feature_panel(report)
    by_source = {row["source_id"]: row for row in panel["records"]}

    assert by_source["s1"]["historical_split"] == "DESIGN"
    assert by_source["s2"]["historical_split"] == "CHALLENGE"
