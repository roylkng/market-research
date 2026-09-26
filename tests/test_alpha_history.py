from datetime import date, timedelta

from marketlab.alpha_history import (
    build_historical_feature_panel,
    canonical_gzip_json,
    cross_sectionalize_panel,
    load_canonical_gzip_json,
)
from marketlab.alpha_market import DailyEquityObservation


def _sessions(count=64):
    start = date(2026, 1, 1)
    sessions = []
    closes = {"A": 100.0, "B": 200.0}
    for index in range(count):
        day = (start + timedelta(days=index)).isoformat()
        equities = []
        for offset, symbol in enumerate(("A", "B")):
            prior = closes[symbol]
            closes[symbol] *= 1.001 + offset * 0.0005
            equities.append(
                DailyEquityObservation(
                    session_date=day,
                    symbol=symbol,
                    isin=f"INE{offset + 1:09d}",
                    open_price=prior,
                    high_price=max(prior, closes[symbol]) * 1.01,
                    low_price=min(prior, closes[symbol]) * 0.99,
                    close_price=closes[symbol],
                    previous_close=prior,
                    volume=100_000 + index + offset,
                    turnover_inr=30_000_000 + index + offset,
                    trade_count=1_000 + index + offset,
                )
            )
        sessions.append(
            {
                "session_date": day,
                "udiff_sha256": f"{index + 1:064x}",
                "benchmark_sha256": f"{index + 1000:064x}",
                "equities": equities,
            }
        )
    return sessions


def test_historical_panel_streams_after_sixty_prior_sessions():
    panel = build_historical_feature_panel(sessions=_sessions())
    assert panel["evidence_class"] == "HISTORICAL_RECONSTRUCTION_DEVELOPMENT"
    assert panel["historical_archives_captured_prospectively"] is False
    assert panel["session_count"] == 64
    assert panel["feature_row_count"] == 8
    assert {row["feature_session"] for row in panel["rows"]} == {
        _sessions()[60]["session_date"],
        _sessions()[61]["session_date"],
        _sessions()[62]["session_date"],
        _sessions()[63]["session_date"],
    }


def test_historical_panel_is_deterministic():
    first = build_historical_feature_panel(sessions=_sessions())
    second = build_historical_feature_panel(sessions=_sessions())
    assert first == second
    assert len(first["panel_sha256"]) == 64


def test_canonical_gzip_is_byte_deterministic():
    payload = {"b": 2, "a": [1, 2, 3]}
    first = canonical_gzip_json(payload)
    second = canonical_gzip_json(payload)
    assert first == second
    assert load_canonical_gzip_json(first) == payload


def test_cross_sectional_panel_ranks_each_session_independently():
    panel = build_historical_feature_panel(sessions=_sessions())
    ranked = cross_sectionalize_panel(panel)
    latest = panel["sessions"][-1]["session_date"]
    latest_rows = [row for row in ranked["rows"] if row["feature_session"] == latest]
    assert len(latest_rows) == 2
    values = sorted(row["values"]["momentum_20"] for row in latest_rows)
    assert values == [0.0, 1.0]
    assert ranked["outcomes_attached"] is False
