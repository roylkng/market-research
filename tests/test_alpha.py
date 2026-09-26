import pytest

from marketlab.alpha import (
    AlphaContractError,
    FeatureDefinition,
    append_feature_row,
    cross_sectional_percentile,
    new_feature_snapshot,
    validate_feature_snapshot,
)


def _definitions():
    return [
        FeatureDefinition(
            name="momentum_20",
            family="price_trend",
            version="v1",
            description="Twenty completed-session close momentum.",
            lookback_sessions=20,
        ),
        FeatureDefinition(
            name="turnover_surprise_20",
            family="volatility_liquidity",
            version="v1",
            description="Current traded value relative to trailing twenty sessions.",
            lookback_sessions=20,
        ),
    ]


def _snapshot():
    return new_feature_snapshot(
        session_date="2026-09-25",
        decision_timestamp="2026-09-25T18:30:00+05:30",
        universe_id="AE001-U001-DYNAMIC",
        universe_sha256="u" * 64,
        definitions=_definitions(),
    )


def _sources(known_at="2026-09-25T17:45:00+05:30"):
    return {
        "momentum_20": [{"sha256": "a" * 64, "known_at": known_at}],
        "turnover_surprise_20": [{"sha256": "b" * 64, "known_at": known_at}],
    }


def test_feature_snapshot_accepts_only_information_known_by_cutoff():
    snapshot = append_feature_row(
        _snapshot(),
        symbol="TEST",
        isin="INE000000001",
        industry="Industrials",
        values={"momentum_20": 0.12, "turnover_surprise_20": 1.4},
        known_at={
            "momentum_20": "2026-09-25T17:45:00+05:30",
            "turnover_surprise_20": "2026-09-25T17:45:00+05:30",
        },
        source_refs=_sources(),
    )
    validate_feature_snapshot(snapshot)


def test_feature_snapshot_rejects_future_feature_timestamp():
    with pytest.raises(AlphaContractError, match="after decision cutoff"):
        append_feature_row(
            _snapshot(),
            symbol="TEST",
            isin="INE000000001",
            industry=None,
            values={"momentum_20": 0.12, "turnover_surprise_20": 1.4},
            known_at={
                "momentum_20": "2026-09-25T18:31:00+05:30",
                "turnover_surprise_20": "2026-09-25T17:45:00+05:30",
            },
            source_refs=_sources(),
        )


def test_feature_snapshot_rejects_future_source_timestamp():
    with pytest.raises(AlphaContractError, match="source became known after decision cutoff"):
        append_feature_row(
            _snapshot(),
            symbol="TEST",
            isin="INE000000001",
            industry=None,
            values={"momentum_20": 0.12, "turnover_surprise_20": 1.4},
            known_at={
                "momentum_20": "2026-09-25T17:45:00+05:30",
                "turnover_surprise_20": "2026-09-25T17:45:00+05:30",
            },
            source_refs=_sources("2026-09-25T18:31:00+05:30"),
        )


def test_feature_snapshot_requires_exact_feature_set():
    with pytest.raises(AlphaContractError, match="definition set"):
        append_feature_row(
            _snapshot(),
            symbol="TEST",
            isin="INE000000001",
            industry=None,
            values={"momentum_20": 0.12},
            known_at={
                "momentum_20": "2026-09-25T17:45:00+05:30",
                "turnover_surprise_20": "2026-09-25T17:45:00+05:30",
            },
            source_refs=_sources(),
        )


def test_duplicate_symbol_isin_identity_is_rejected():
    snapshot = append_feature_row(
        _snapshot(),
        symbol="TEST",
        isin="INE000000001",
        industry=None,
        values={"momentum_20": 0.12, "turnover_surprise_20": 1.4},
        known_at={
            "momentum_20": "2026-09-25T17:45:00+05:30",
            "turnover_surprise_20": "2026-09-25T17:45:00+05:30",
        },
        source_refs=_sources(),
    )
    with pytest.raises(AlphaContractError, match="duplicate feature row"):
        append_feature_row(
            snapshot,
            symbol="TEST",
            isin="INE000000001",
            industry=None,
            values={"momentum_20": 0.2, "turnover_surprise_20": 1.1},
            known_at={
                "momentum_20": "2026-09-25T17:45:00+05:30",
                "turnover_surprise_20": "2026-09-25T17:45:00+05:30",
            },
            source_refs=_sources(),
        )


def test_cross_sectional_percentile_is_tie_aware_and_preserves_missing():
    ranked = cross_sectional_percentile(
        {"A": 10.0, "B": 20.0, "C": 20.0, "D": 40.0, "MISSING": None}
    )
    assert ranked["A"] == pytest.approx(0.0)
    assert ranked["B"] == pytest.approx(0.5)
    assert ranked["C"] == pytest.approx(0.5)
    assert ranked["D"] == pytest.approx(1.0)
    assert ranked["MISSING"] is None
