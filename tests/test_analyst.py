from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab.analyst import seal_decision, validate_decision


def decision_payload(**overrides: object) -> dict:
    payload = {
        "schema_version": 1,
        "object_type": "ANALYST_DECISION",
        "live_capital_allowed": False,
        "decision_timestamp": "2026-09-12T16:00:00+05:30",
        "symbol": "EXAMPLE",
        "isin": "INE000A01001",
        "company_name": "Example Ltd",
        "sector": "Industrials",
        "benchmark": "NIFTY 500",
        "horizon_sessions": 60,
        "validation_role": "PROSPECTIVE_VALIDATION",
        "business_thesis": "A timestamped thesis with an observable catalyst.",
        "thesis_evidence": [
            {
                "source_ref": "repo://research/example/source.json",
                "available_at": "2026-09-12T15:00:00+05:30",
            }
        ],
        "valuation_assumptions": {
            "forward_pe": None,
            "note": "No point-in-time forward multiple available.",
        },
        "signal_states": {
            "h019": {"state": "MISSING", "evidence_ref": None},
            "h021": {"state": "MISSING_EXPECTATION_SIGNAL", "evidence_ref": None},
            "h013": {"state": "NOT_DUE", "evidence_ref": None},
            "h020": {
                "state": "PAPER_ENTRY_ELIGIBLE_TREND",
                "evidence_ref": "repo://reports/h020/example.json",
            },
        },
        "market_regime": "BEARISH",
        "sector_regime": "NEUTRAL",
        "catalysts": [
            {"description": "Order conversion", "expected_window": "next 60 sessions"}
        ],
        "invalidations": [
            {
                "condition": "management withdraws FY27 growth guidance",
                "severity": "HARD",
            }
        ],
        "scenarios": {
            "bear": {"narrative": "Execution weakens.", "benchmark_relative_return_pct": None},
            "base": {"narrative": "Execution tracks plan.", "benchmark_relative_return_pct": None},
            "bull": {"narrative": "Execution accelerates.", "benchmark_relative_return_pct": None},
        },
        "forecast": {
            "expected_benchmark_relative_return_pct": None,
            "p10_benchmark_relative_return_pct": None,
            "p50_benchmark_relative_return_pct": None,
            "p90_benchmark_relative_return_pct": None,
            "probability_beat_benchmark": None,
            "expected_mae_pct": None,
            "calibration_status": "UNAVAILABLE",
        },
        "missing_information": ["First valid H021 30-day revision is not available yet."],
        "analyst_action": "PORTFOLIO_ELIGIBLE",
    }
    payload.update(overrides)
    return payload


def test_seal_decision_is_deterministic_and_valid() -> None:
    first = seal_decision(decision_payload())
    second = seal_decision(decision_payload())
    assert first == second
    assert first["decision_id"].startswith("ADO1-EXAMPLE-20260912T103000Z-")
    assert validate_decision(first) == []


def test_future_dated_evidence_is_rejected() -> None:
    payload = decision_payload()
    payload["thesis_evidence"] = [
        {
            "source_ref": "repo://future.json",
            "available_at": "2026-09-12T17:00:00+05:30",
        }
    ]
    with pytest.raises(ValueError, match="future-dated"):
        seal_decision(payload)


def test_probability_requires_experimental_or_calibrated_status() -> None:
    payload = decision_payload()
    payload["forecast"] = {
        **payload["forecast"],
        "probability_beat_benchmark": 0.7,
        "calibration_status": "UNCALIBRATED",
    }
    with pytest.raises(ValueError, match="numeric probability"):
        seal_decision(payload)


def test_quantiles_must_be_ordered() -> None:
    payload = decision_payload()
    payload["forecast"] = {
        **payload["forecast"],
        "p10_benchmark_relative_return_pct": 5.0,
        "p50_benchmark_relative_return_pct": 1.0,
        "p90_benchmark_relative_return_pct": 10.0,
        "calibration_status": "EXPERIMENTAL",
    }
    with pytest.raises(ValueError, match="quantiles"):
        seal_decision(payload)


def test_sealed_payload_detects_mutation() -> None:
    decision = seal_decision(decision_payload())
    mutated = deepcopy(decision)
    mutated["business_thesis"] = "Rewritten after the fact."
    assert "record_sha256 does not match canonical decision payload" in validate_decision(mutated)
