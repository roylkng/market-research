from __future__ import annotations

from pathlib import Path

import yaml

from marketlab.h002_historical_v2 import (
    candidate_rows_for_period,
    historical_freeze_v2,
    select_mixed_historical_pair,
    validate_historical_replay_v2_rule,
)


def _integrated_row(
    *,
    period: str,
    broadcast: str,
    url: str,
    basis: str = "Consolidated",
) -> dict:
    return {
        "type": "Integrated Filing- Financials",
        "symbol": "ABC",
        "consolidated": basis,
        "qe_Date": period,
        "broadcast_Date": broadcast,
        "xbrl": url,
    }


def _legacy_row(
    *,
    period: str,
    broadcast: str,
    url: str,
    basis: str = "Consolidated",
) -> dict:
    return {
        "symbol": "ABC",
        "period": "Quarterly",
        "consolidated": basis,
        "toDate": period,
        "broadCastDate": broadcast,
        "relatingTo": "Third Quarter",
        "xbrl": url,
    }


def test_six_quarter_rule_hash_is_frozen_and_valid():
    document = yaml.safe_load(Path("registry/h002_historical_replay_v2_rule.yaml").read_text())
    assert validate_historical_replay_v2_rule(document) == document["sha256"]
    assert len(document["target_quarters"]) == 6
    assert document["cohort"]["planned_observations"] == 600


def test_v2_freeze_uses_exact_live_anchor_clock():
    rule = yaml.safe_load(Path("registry/h002_historical_replay_v2_rule.yaml").read_text())
    policy = rule["freeze_policy"]
    assert historical_freeze_v2(
        "2026-06-30",
        offset_days=policy["target_period_end_offset_days"],
        freeze_clock=policy["freeze_clock"],
    ) == "2026-06-06T15:11:38.303Z"
    assert historical_freeze_v2(
        "2025-12-31",
        offset_days=policy["target_period_end_offset_days"],
        freeze_clock=policy["freeze_clock"],
    ) == "2025-12-07T15:11:38.303Z"


def test_period_source_policy_switches_at_march_2025():
    integrated = {
        "data": [
            _integrated_row(
                period="31-Mar-2025",
                broadcast="25-Apr-2025 10:00:00",
                url="https://nsearchives.nseindia.com/integrated.xml",
            )
        ]
    }
    legacy = [
        _legacy_row(
            period="31-Dec-2024",
            broadcast="20-Jan-2025 10:00:00",
            url="https://nsearchives.nseindia.com/legacy.xml",
        )
    ]
    target = candidate_rows_for_period(
        integrated_payload=integrated,
        legacy_payload=legacy,
        symbol="ABC",
        period_end="2025-03-31",
        accounting_basis="Consolidated",
    )
    baseline = candidate_rows_for_period(
        integrated_payload=integrated,
        legacy_payload=legacy,
        symbol="ABC",
        period_end="2024-12-31",
        accounting_basis="Consolidated",
    )
    assert len(target) == 1 and target[0].source_feed == "INTEGRATED"
    assert len(baseline) == 1 and baseline[0].source_feed == "LEGACY_FINANCIAL_RESULTS"


def test_mixed_pair_uses_first_integrated_target_and_latest_legacy_baseline_at_freeze():
    integrated = {
        "data": [
            _integrated_row(
                period="30-Sep-2025",
                broadcast="20-Oct-2025 10:00:00",
                url="https://nsearchives.nseindia.com/target-first.xml",
            ),
            _integrated_row(
                period="30-Sep-2025",
                broadcast="22-Oct-2025 10:00:00",
                url="https://nsearchives.nseindia.com/target-revision.xml",
            ),
        ]
    }
    legacy = [
        _legacy_row(
            period="30-Sep-2024",
            broadcast="20-Oct-2024 10:00:00",
            url="https://nsearchives.nseindia.com/baseline-original.xml",
        ),
        _legacy_row(
            period="30-Sep-2024",
            broadcast="01-Aug-2025 10:00:00",
            url="https://nsearchives.nseindia.com/baseline-pre-freeze-revision.xml",
        ),
        _legacy_row(
            period="30-Sep-2024",
            broadcast="20-Sep-2025 10:00:00",
            url="https://nsearchives.nseindia.com/baseline-post-freeze-revision.xml",
        ),
    ]
    pair = select_mixed_historical_pair(
        integrated_payload=integrated,
        legacy_payload=legacy,
        symbol="ABC",
        target_period_end="2025-09-30",
        baseline_period_end="2024-09-30",
        freeze_at_utc="2025-09-06T15:11:38.303Z",
    )
    assert pair is not None
    assert pair.target.source_url.endswith("target-first.xml")
    assert pair.target.source_feed == "INTEGRATED"
    assert pair.baseline.source_url.endswith("baseline-pre-freeze-revision.xml")
    assert pair.baseline.source_feed == "LEGACY_FINANCIAL_RESULTS"


def test_legacy_non_consolidated_is_normalized_to_standalone():
    legacy = [
        _legacy_row(
            period="30-Jun-2024",
            broadcast="20-Jul-2024 10:00:00",
            url="https://nsearchives.nseindia.com/legacy-standalone.xml",
            basis="Non-Consolidated",
        )
    ]
    rows = candidate_rows_for_period(
        integrated_payload={"data": []},
        legacy_payload=legacy,
        symbol="ABC",
        period_end="2024-06-30",
        accounting_basis="Standalone",
    )
    assert len(rows) == 1
    assert rows[0].accounting_basis == "Standalone"
