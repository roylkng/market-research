from datetime import date

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_corporate_actions import (
    acquire_corporate_action_ledger,
    blocked_actions,
    filter_feature_panel_for_corporate_actions,
    parse_share_changing_actions,
)


def test_parse_share_changing_actions_ignores_dividends():
    parsed = parse_share_changing_actions(
        [
            {
                "symbol": "AAA",
                "series": "EQ",
                "subject": "Dividend - Rs 5 Per Share",
                "exDate": "10-Sep-2026",
            },
            {
                "symbol": "AAA",
                "series": "EQ",
                "subject": "BONUS 1:1",
                "exDate": "12-Sep-2026",
            },
        ]
    )
    assert list(parsed) == ["AAA"]
    assert parsed["AAA"]["actions"] == [
        {"ex_date": "2026-09-12", "subject": "BONUS 1:1"}
    ]


def test_acquisition_chunks_and_hashes_exact_raw_evidence():
    calls = []

    def fetcher(start, end):
        calls.append((start, end))
        payload = [
            {
                "symbol": "AAA",
                "series": "EQ",
                "purpose": "Rights 1:5",
                "exDate": "15-Sep-2026",
            }
        ]
        raw = f"{start}:{end}".encode()
        return payload, raw, "https://www.nseindia.com/api/corporates-corporateActions"

    ledger = acquire_corporate_action_ledger(
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 20),
        fetcher=fetcher,
        chunk_days=10,
    )
    assert len(calls) == 2
    assert ledger["record_count"] == 1
    assert len(ledger["ledger_sha256"]) == 64


def test_blocked_actions_fail_closed_for_unresolved_symbol():
    index = {
        "AAA": {
            "symbol": "AAA",
            "status": "UNRESOLVED",
            "actions": [],
            "unresolved_subjects": ["BONUS"],
        }
    }
    with pytest.raises(AlphaContractError, match="unresolved"):
        blocked_actions(
            index,
            symbol="AAA",
            start_exclusive="2026-09-01",
            end_inclusive="2026-09-20",
        )


def test_action_safe_feature_panel_removes_lookback_crossing_action():
    sessions = [
        {"session_date": f"2026-01-{day:02d}"}
        for day in range(1, 32)
    ] + [
        {"session_date": f"2026-02-{day:02d}"}
        for day in range(1, 31)
    ]
    # Use simple ISO dates beyond real month lengths only as ordered identifiers
    # would be invalid for date.fromisoformat, so replace with real sequential dates.
    from datetime import timedelta

    start = date(2026, 1, 1)
    sessions = [
        {"session_date": (start + timedelta(days=index)).isoformat()}
        for index in range(61)
    ]
    current = sessions[-1]["session_date"]
    old = sessions[0]["session_date"]
    market = {"sessions": sessions}
    feature = {
        "schema_version": 1,
        "panel_id": "TEST",
        "feature_definitions": [{"name": "x"}],
        "rows": [
            {
                "feature_session": current,
                "symbol": "AAA",
                "isin": "INE000000001",
                "universe_sha256": "old",
                "values": {"x": 0.5},
            },
            {
                "feature_session": current,
                "symbol": "BBB",
                "isin": "INE000000002",
                "universe_sha256": "old",
                "values": {"x": 0.7},
            },
        ],
        "panel_sha256": "ignored",
    }
    action_date = sessions[30]["session_date"]
    unsigned = {
        "schema_version": 1,
        "ledger_id": "AE001-CORPORATE-ACTIONS-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "coverage_start_date": old,
        "coverage_end_date": current,
        "source_chunks": [],
        "record_count": 1,
        "records": [
            {
                "symbol": "AAA",
                "status": "READY",
                "actions": [
                    {"ex_date": action_date, "subject": "BONUS 1:1"}
                ],
                "unresolved_subjects": [],
            }
        ],
        "no_record_means_no_share_changing_action_in_covered_source": True,
        "historical_source_retrieved_prospectively": False,
        "live_capital_allowed": False,
    }
    ledger = {**unsigned, "ledger_sha256": digest(unsigned)}
    safe = filter_feature_panel_for_corporate_actions(
        feature_panel=feature,
        market_panel=market,
        action_ledger=ledger,
        lookback_sessions=60,
    )
    assert safe["feature_row_count"] == 1
    assert safe["rows"][0]["symbol"] == "BBB"
    assert safe["corporate_action_blocked_feature_row_count"] == 1
