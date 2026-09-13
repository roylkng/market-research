from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab import h022, h022_outcomes


def _feature_panel(published: str) -> dict:
    row = {
        "schema_version": 1,
        "hypothesis_id": "H022",
        "feature_version": h022.FEATURE_VERSION,
        "symbol": "AAA",
        "source_id": "source-2",
        "exchange_published_at_utc": published,
        "historical_split": "CHALLENGE",
        "survivor_panel": True,
        "prior_source_id": "source-1",
        "prior_exchange_published_at_utc": "2025-12-01T12:00:00Z",
        "feature_status": "SIGNAL",
        "primary_signal": 1.0,
        "current": {},
        "prior": {},
        "deltas": {},
    }
    panel = {
        "schema_version": 1,
        "hypothesis_id": "H022",
        "feature_version": h022.FEATURE_VERSION,
        "source_report_sha256": h022.SOURCE_REPORT_SHA256,
        "source_rule_id": h022.SOURCE_RULE_ID,
        "source_rule_sha256": h022.SOURCE_RULE_SHA256,
        "source_bundle_sha256": h022.SOURCE_BUNDLE_SHA256,
        "universe_bias": "CURRENT_2026_U001_SURVIVOR_PANEL",
        "outcome_data_attached": False,
        "record_count": 1,
        "signal_count": 1,
        "no_prior_count": 0,
        "ambiguous_prior_count": 0,
        "design_signal_count": 0,
        "challenge_signal_count": 1,
        "records": [row],
    }
    panel["panel_sha256"] = h022._canonical_hash(panel)
    return panel


def _universe() -> dict:
    members = [
        {"symbol": "AAA", "isin": "INE000A01001", "series": "EQ"},
    ]
    members.extend(
        {"symbol": f"X{index:03d}", "isin": f"INE{index:06d}A01", "series": "EQ"}
        for index in range(99)
    )
    return {"members": members}


def _patch_panel(monkeypatch: pytest.MonkeyPatch, panel: dict) -> None:
    monkeypatch.setattr(h022, "EXPECTED_SOURCE_COUNT", 1)
    monkeypatch.setattr(h022_outcomes, "FEATURE_PANEL_SHA256", panel["panel_sha256"])


def _sessions(count: int = 130) -> list[dict]:
    # Synthetic consecutive dates are sufficient to test session counting.
    from datetime import date, timedelta

    start = date(2026, 1, 5)
    return [
        {
            "session_date": (start + timedelta(days=index)).isoformat(),
            "open": 1000.0 + index,
            "close": 1000.5 + index,
        }
        for index in range(count)
        if start + timedelta(days=index) <= h022_outcomes.CUTOFF_SESSION
    ]


def test_publication_before_open_can_use_same_session(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = _feature_panel("2026-01-05T03:00:00Z")  # 08:30 IST
    _patch_panel(monkeypatch, panel)
    sessions = _sessions()
    stock = {
        "2026-01-05": {"AAA": {"isin": "INE000A01001", "series": "EQ", "open": 100.0, "close": 101.0}},
        "2026-03-05": {"AAA": {"isin": "INE000A01001", "series": "EQ", "open": 110.0, "close": 120.0}},
    }
    outcome = h022_outcomes.build_outcome_panel(panel, _universe(), sessions, stock, [])
    assert outcome["records"][0]["entry_session"] == "2026-01-05"


def test_publication_after_open_waits_for_next_session(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = _feature_panel("2026-01-05T05:00:00Z")  # 10:30 IST
    _patch_panel(monkeypatch, panel)
    sessions = _sessions()
    stock = {
        "2026-01-06": {"AAA": {"isin": "INE000A01001", "series": "EQ", "open": 100.0, "close": 101.0}},
        "2026-03-06": {"AAA": {"isin": "INE000A01001", "series": "EQ", "open": 110.0, "close": 120.0}},
    }
    outcome = h022_outcomes.build_outcome_panel(panel, _universe(), sessions, stock, [])
    assert outcome["records"][0]["entry_session"] == "2026-01-06"


def test_share_changing_action_blocks_primary_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = _feature_panel("2026-01-05T05:00:00Z")
    _patch_panel(monkeypatch, panel)
    sessions = _sessions()
    entry_date = "2026-01-06"
    exit_date = sessions[60]["session_date"]
    stock = {
        entry_date: {"AAA": {"isin": "INE000A01001", "series": "EQ", "open": 100.0, "close": 101.0}},
        exit_date: {"AAA": {"isin": "INE000A01001", "series": "EQ", "open": 110.0, "close": 120.0}},
    }
    actions = [{"symbol": "AAA", "ex_date": "2026-02-01", "subject": "Bonus 1:1"}]
    outcome = h022_outcomes.build_outcome_panel(panel, _universe(), sessions, stock, actions)
    assert outcome["records"][0]["outcome_status"] == "BLOCKED_PRIMARY_CORPORATE_ACTION"


def test_feature_panel_digest_change_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = _feature_panel("2026-01-05T05:00:00Z")
    _patch_panel(monkeypatch, panel)
    tampered = deepcopy(panel)
    tampered["records"][0]["primary_signal"] = 7.0
    with pytest.raises(h022.H022Error, match="hash mismatch"):
        h022_outcomes.build_outcome_panel(tampered, _universe(), _sessions(), {}, [])


def test_summary_uses_challenge_complete_clear_rows_only() -> None:
    records = []
    for index in range(20):
        signal = float(index)
        excess = (index - 9.5) / 100.0
        records.append(
            {
                "symbol": f"S{index:02d}",
                "source_id": f"src-{index}",
                "historical_split": "CHALLENGE",
                "feature_status": "SIGNAL",
                "primary_signal": signal,
                "entry_session": "2026-01-05",
                "outcome_status": "COMPLETE_PRIMARY",
                "horizons": {
                    "60": {
                        "status": "COMPLETE",
                        "exit_session": "2026-03-05",
                        "excess_return": excess,
                        "corporate_action_status": "CLEAR",
                    }
                },
            }
        )
    result = h022_outcomes.summarize_challenge({"records": records})
    assert result["complete_primary_count"] == 20
    assert result["top_minus_bottom_mean_excess_pp"] > 0
    assert result["spearman_rho"] == pytest.approx(1.0)
    assert result["top_quintile_beat_rate"] == 1.0
