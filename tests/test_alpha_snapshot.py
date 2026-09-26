from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError, validate_feature_snapshot
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_snapshot import (
    build_market_source_manifest,
    build_price_volume_snapshot,
)


def _observations(symbol="TEST", isin="INE000000001"):
    start = date(2026, 6, 1)
    close = 100.0
    rows = []
    for index in range(61):
        previous = close
        close = previous * 1.001
        session = start + timedelta(days=index)
        rows.append(
            DailyEquityObservation(
                session_date=session.isoformat(),
                symbol=symbol,
                isin=isin,
                open_price=previous,
                high_price=max(previous, close) * 1.01,
                low_price=min(previous, close) * 0.99,
                close_price=close,
                previous_close=previous,
                volume=100_000 + index,
                turnover_inr=30_000_000 + index,
                trade_count=1_000 + index,
            )
        )
    return rows


def _sources(rows, known_at="2026-09-25T17:45:00+05:30"):
    return [
        {
            "session_date": row.session_date,
            "sha256": f"{index + 1:064x}",
            "known_at": known_at,
        }
        for index, row in enumerate(rows)
    ]


def test_market_source_manifest_is_deterministic():
    rows = _observations()
    sources = _sources(rows)
    first = build_market_source_manifest(
        list(reversed(sources)),
        decision_timestamp="2026-09-25T18:30:00+05:30",
    )
    second = build_market_source_manifest(
        sources,
        decision_timestamp="2026-09-25T18:30:00+05:30",
    )
    assert first == second


def test_market_source_manifest_rejects_future_capture():
    rows = _observations()
    sources = _sources(rows)
    sources[-1]["known_at"] = "2026-09-25T18:31:00+05:30"
    with pytest.raises(AlphaContractError, match="after decision cutoff"):
        build_market_source_manifest(
            sources,
            decision_timestamp="2026-09-25T18:30:00+05:30",
        )


def test_price_volume_snapshot_is_hash_stable_and_valid():
    rows = _observations()
    current = rows[-1].session_date
    kwargs = {
        "observations": rows,
        "current_session": current,
        "decision_timestamp": "2026-09-25T18:30:00+05:30",
        "sources": _sources(rows),
        "industry_by_identity": {("TEST", "INE000000001"): "Industrials"},
    }
    first = build_price_volume_snapshot(**kwargs)
    second = build_price_volume_snapshot(**kwargs)
    assert first == second
    assert len(first["rows"]) == 1
    assert first["universe_sha256"] == second["universe_sha256"]
    validate_feature_snapshot(first)
