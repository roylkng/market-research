from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketlab.h002_historical_outcomes import (
    HistoricalOutcomeError,
    adapt_signal_for_execution,
    canonical_hash,
    load_phase_a_manifest,
    summarize_phase_b,
)


def _phase_a() -> dict:
    document = {
        "schema_version": 1,
        "phase": "A_SIGNAL_CAPTURE_ONLY",
        "replay_rule_id": "H002-HR001",
        "source_signal_rule_id": "H002-R001",
        "outcome_data_included": False,
        "status_counts": {"SIGNAL": 1},
        "records": [],
    }
    document["manifest_sha256"] = canonical_hash(document)
    return document


def _signal_record() -> dict:
    return {
        "status": "SIGNAL",
        "signal": {
            "replay_rule_id": "H002-HR001",
            "source_signal_rule_id": "H002-R001",
            "signal_version": "ue_price_normalized_v1",
            "event_id": "event",
            "event_version_id": "event-v1",
            "expectation_id": "expectation",
            "symbol": "ABC",
            "actual_basic_eps": 12.0,
            "expected_eps": 10.0,
            "surprise_eps": 2.0,
            "price_day_minus_2": 100.0,
            "ue": 0.02,
            "bucket": "POSITIVE",
        },
        "target_event": {
            "provenance": {"exchange_published_at_utc": "2026-04-20T10:00:00Z"}
        },
    }


def _completed(symbol: str, quarter: str, bucket: str, ue: float, excess: float) -> dict:
    return {
        "status": "COMPLETED",
        "symbol": symbol,
        "quarter_id": quarter,
        "signal_bucket": bucket,
        "signal_ue": ue,
        "gross_return_pct": excess + 1.0,
        "benchmarks": [
            {
                "benchmark_id": "nifty_50",
                "status": "COMPLETE",
                "return_pct": 1.0,
                "excess_return_pct": excess,
            },
            {
                "benchmark_id": "nifty_200_momentum_30",
                "status": "COMPLETE",
                "return_pct": 0.5,
                "excess_return_pct": excess + 0.5,
            },
        ],
    }


def test_phase_a_manifest_hash_and_identity_are_required(tmp_path: Path):
    document = _phase_a()
    path = tmp_path / "phase-a.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    loaded = load_phase_a_manifest(path, expected_sha256=document["manifest_sha256"])
    assert loaded["phase"] == "A_SIGNAL_CAPTURE_ONLY"

    tampered = dict(document)
    tampered["outcome_data_included"] = True
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(HistoricalOutcomeError, match="hash mismatch"):
        load_phase_a_manifest(path, expected_sha256=document["manifest_sha256"])


def test_phase_a_manifest_cannot_be_substituted_with_another_valid_hash(tmp_path: Path):
    document = _phase_a()
    path = tmp_path / "phase-a.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(HistoricalOutcomeError, match="identity changed"):
        load_phase_a_manifest(path, expected_sha256="0" * 64)


def test_historical_signal_adapter_uses_publication_as_simulated_decision_timestamp():
    result = adapt_signal_for_execution(_signal_record())
    assert result.rule_id == "H002-R001"
    assert result.scored_at_utc == "2026-04-20T10:00:00Z"
    assert result.bucket == "POSITIVE"
    assert result.ue == pytest.approx(0.02)


def test_historical_signal_adapter_refuses_non_signal_records():
    record = _signal_record()
    record["status"] = "SKIPPED"
    with pytest.raises(HistoricalOutcomeError, match="only phase-A SIGNAL"):
        adapt_signal_for_execution(record)


def test_phase_b_summary_uses_company_clustered_uncertainty():
    records = [
        _completed("A", "Q1", "POSITIVE", 0.03, 4.0),
        _completed("A", "Q2", "POSITIVE", 0.02, 3.0),
        _completed("B", "Q1", "NEGATIVE", -0.02, -2.0),
        _completed("B", "Q2", "NEGATIVE", -0.01, -1.0),
        _completed("C", "Q1", "POSITIVE", 0.01, 1.0),
        _completed("C", "Q2", "NEGATIVE", -0.03, -3.0),
        _completed("D", "Q1", "POSITIVE", 0.04, 2.0),
        _completed("D", "Q2", "NEGATIVE", -0.04, -4.0),
    ]
    summary = summarize_phase_b(records)
    evaluation = summary["by_benchmark"]["nifty_50"]["evaluation"]
    assert summary["completed_count"] == 8
    assert evaluation["observation_level_binary"]["spread"] > 0
    cluster = evaluation["company_cluster_bootstrap"]
    assert cluster["cluster_unit"] == "symbol"
    assert cluster["unique_companies"] == 4
    leave_one_out = evaluation["leave_one_company_out"]
    assert leave_one_out["company_count"] == 4
