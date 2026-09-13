from __future__ import annotations

import io
import zipfile
from copy import deepcopy
from datetime import date

import pytest

from marketlab import h022_outcomes


def _udiff_zip(rows: list[str]) -> bytes:
    header = (
        "TradDt,Sgmt,Src,FinInstrmTp,ISIN,TckrSymb,SctySrs,"
        "OpnPric,HghPric,LwPric,ClsPric\n"
    )
    payload = (header + "\n".join(rows) + "\n").encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BhavCopy_NSE_CM_test.csv", payload)
    return out.getvalue()


def test_calendar_freezes_muhurat_and_ad_hoc_holiday() -> None:
    sessions = h022_outcomes.build_frozen_sessions(
        start_date=date(2025, 10, 20), end_date=date(2026, 1, 16)
    )
    by_date = {row.session_date: row for row in sessions}

    assert by_date["2025-10-21"].special is True
    assert by_date["2025-10-21"].open_timestamp_utc == "2025-10-21T08:15:00Z"
    assert "2025-10-22" not in by_date
    assert "2026-01-15" not in by_date


def test_entry_is_same_day_only_if_publication_precedes_open() -> None:
    sessions = h022_outcomes.build_frozen_sessions(
        start_date=date(2025, 10, 1), end_date=date(2025, 10, 3)
    )

    same_day = h022_outcomes.first_entry_session("2025-10-01T03:00:00+00:00", sessions)
    assert same_day is not None
    assert same_day[1].session_date == "2025-10-01"

    after_open = h022_outcomes.first_entry_session("2025-10-01T04:00:00+00:00", sessions)
    assert after_open is not None
    assert after_open[1].session_date == "2025-10-03"


def test_entry_session_counts_as_holding_session_one() -> None:
    sessions = h022_outcomes.build_frozen_sessions(
        start_date=date(2025, 10, 1), end_date=date(2026, 2, 1)
    )
    exit_session = h022_outcomes.horizon_session(sessions, entry_index=0, horizon=20)
    assert exit_session == sessions[19]


def test_corporate_action_after_entry_blocks_horizon() -> None:
    payload = [
        {
            "symbol": "AAA",
            "subject": "Sub-Division of equity shares from Rs 10 to Rs 5",
            "exDate": "15-Oct-2025",
        },
        {
            "symbol": "AAA",
            "subject": "Interim Dividend",
            "exDate": "20-Oct-2025",
        },
    ]
    audit = h022_outcomes.parse_share_action_audit(payload, symbol="AAA")
    blocked = h022_outcomes.blocked_actions(
        audit, entry_date="2025-10-01", exit_date="2025-10-31"
    )

    assert audit["status"] == "READY"
    assert len(blocked) == 1
    assert blocked[0]["ex_date"] == "2025-10-15"


def test_action_on_entry_date_does_not_block_post_ex_open() -> None:
    payload = [
        {"symbol": "AAA", "subject": "Bonus issue", "exDate": "01-Oct-2025"}
    ]
    audit = h022_outcomes.parse_share_action_audit(payload, symbol="AAA")
    assert h022_outcomes.blocked_actions(
        audit, entry_date="2025-10-01", exit_date="2025-10-31"
    ) == ()


def test_udiff_prefers_isin_but_can_fall_back_to_current_symbol() -> None:
    raw = _udiff_zip(
        [
            "2025-10-01,CM,NSE,STK,OLDISIN000001,AAA,EQ,100,110,95,108",
            "2025-10-01,CM,NSE,STK,OTHER0000001,BBB,EQ,200,210,195,205",
        ]
    )
    bar = h022_outcomes.parse_udiff_identity_bar(
        raw,
        session_date=date(2025, 10, 1),
        symbol="AAA",
        expected_isin="CURRENTISIN01",
    )
    assert bar is not None
    assert bar["identity_mode"] == "CURRENT_SYMBOL_EQ_FALLBACK"
    assert bar["isin_observed"] == "OLDISIN000001"
    assert bar["open"] == 100.0
    assert bar["close"] == 108.0


def test_primary_classification_precedence_rejects_negative_top_mean() -> None:
    primary = {
        "mature_signal_count": 250,
        "complete_count": 240,
        "complete_share_of_mature": 0.96,
        "top_quintile_mean_excess_pp": -0.1,
        "top_minus_bottom_mean_excess_pp": 5.0,
        "top_quintile_median_excess_pp": 1.0,
        "top_quintile_benchmark_beat_rate": 0.60,
        "cluster_bootstrap_ci_95_low_pp": 1.0,
    }
    assert h022_outcomes.classify_primary(primary) == "REJECTED"


def test_primary_classification_requires_coverage() -> None:
    primary = {
        "mature_signal_count": 250,
        "complete_count": 199,
        "complete_share_of_mature": 0.99,
        "top_quintile_mean_excess_pp": 10.0,
        "top_minus_bottom_mean_excess_pp": 10.0,
        "top_quintile_median_excess_pp": 10.0,
        "top_quintile_benchmark_beat_rate": 1.0,
        "cluster_bootstrap_ci_95_low_pp": 5.0,
    }
    assert h022_outcomes.classify_primary(primary) == "INSUFFICIENT_COVERAGE"


def test_primary_classification_locks_promising_beat_rate_threshold() -> None:
    primary = {
        "mature_signal_count": 250,
        "complete_count": 240,
        "complete_share_of_mature": 0.96,
        "top_quintile_mean_excess_pp": 4.0,
        "top_minus_bottom_mean_excess_pp": 3.0,
        "top_quintile_median_excess_pp": 1.0,
        "top_quintile_benchmark_beat_rate": 0.549,
        "cluster_bootstrap_ci_95_low_pp": -1.0,
    }
    assert h022_outcomes.classify_primary(primary) == "INCONCLUSIVE"

    primary["top_quintile_benchmark_beat_rate"] = 0.55
    assert h022_outcomes.classify_primary(primary) == "PROMISING"


def test_outcome_report_does_not_mutate_feature_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(h022_outcomes, "validate_feature_panel", lambda _panel: None)
    monkeypatch.setattr(h022_outcomes, "CHALLENGE_SIGNAL_COUNT", 1)
    monkeypatch.setattr(h022_outcomes, "FEATURE_PANEL_SHA256", "test-panel")

    feature_panel = {
        "panel_sha256": "test-panel",
        "records": [
            {
                "source_id": "s1",
                "symbol": "AAA",
                "exchange_published_at_utc": "2025-10-01T03:00:00Z",
                "historical_split": "CHALLENGE",
                "feature_status": "SIGNAL",
                "primary_signal": 2.0,
            }
        ],
    }
    original = deepcopy(feature_panel)
    sessions = h022_outcomes.build_frozen_sessions(
        start_date=date(2025, 10, 1), end_date=date(2026, 9, 11)
    )
    entry_index, entry = h022_outcomes.first_entry_session(
        "2025-10-01T03:00:00Z", sessions
    ) or (-1, None)
    assert entry is not None

    stock_bars: dict[tuple[str, str], dict[str, object] | None] = {
        (entry.session_date, "AAA"): {"open": 100.0, "close": 101.0}
    }
    benchmark_bars = {entry.session_date: {"open": 1000.0, "close": 1005.0}}
    for horizon in h022_outcomes.HORIZONS:
        exit_session = h022_outcomes.horizon_session(
            sessions, entry_index=entry_index, horizon=horizon
        )
        assert exit_session is not None
        stock_bars[(exit_session.session_date, "AAA")] = {
            "open": 100.0,
            "close": 110.0,
        }
        benchmark_bars[exit_session.session_date] = {"open": 1000.0, "close": 1050.0}

    report = h022_outcomes.build_outcome_report(
        feature_panel,
        sessions=sessions,
        stock_bars=stock_bars,
        benchmark_bars=benchmark_bars,
        corporate_actions={"AAA": {"status": "READY", "actions": [], "unresolved_subjects": []}},
    )

    assert feature_panel == original
    assert report["records"][0]["horizons"]["60"]["status"] == "COMPLETE"
