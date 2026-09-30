import pytest

from marketlab.ab001 import (
    build_alpha_library,
    dynamic_blend,
    incremental_alpha_contribution,
    normalize_oos_alpha_source,
    pairwise_alpha_diagnostics,
    standalone_alpha_reports,
)
from marketlab.alpha import AlphaContractError


def _predictions(
    *,
    sessions=30,
    names=20,
    mode="positive",
    reverse_session=None,
):
    rows = []
    for day in range(1, sessions + 1):
        session = f"2026-01-{day:02d}"
        for index in range(names):
            target = (index - (names - 1) / 2.0) / 1000.0
            if reverse_session == session:
                target = -target
            if mode == "positive":
                prediction = float(index)
            elif mode == "positive_shifted":
                prediction = float(index) + (0.1 if index % 2 else -0.1)
            elif mode == "negative":
                prediction = -float(index)
            elif mode == "flat_noise":
                prediction = float((index * 7 + day * 3) % names)
            else:
                raise AssertionError(mode)
            rows.append(
                {
                    "model_id": f"MODEL-{mode}",
                    "model_sha256": "f" * 64,
                    "symbol": f"S{index:03d}",
                    "isin": f"INE{index:09d}",
                    "feature_session": session,
                    "entry_session": session,
                    "exit_session": session,
                    "horizon_sessions": 1,
                    "prediction": prediction,
                    "target_excess_return": target,
                    "prediction_role": "OOS",
                    "oos_only": True,
                    "live_capital_allowed": False,
                }
            )
    return rows


def _library(*, reverse_session=None):
    return build_alpha_library(
        [
            {
                "alpha_id": "ALPHA_A",
                "alpha_version": "v1",
                "source_artifact_sha256": "a" * 64,
                "predictions": _predictions(
                    mode="positive",
                    reverse_session=reverse_session,
                ),
            },
            {
                "alpha_id": "ALPHA_B",
                "alpha_version": "v1",
                "source_artifact_sha256": "b" * 64,
                "predictions": _predictions(
                    mode="positive_shifted",
                    reverse_session=reverse_session,
                ),
            },
            {
                "alpha_id": "ALPHA_C",
                "alpha_version": "v1",
                "source_artifact_sha256": "c" * 64,
                "predictions": _predictions(
                    mode="negative",
                    reverse_session=reverse_session,
                ),
            },
        ]
    )


def test_normalize_oos_alpha_source_is_tie_aware_and_centered():
    rows = [
        {
            "symbol": "A",
            "isin": "INE000000001",
            "feature_session": "2026-01-01",
            "horizon_sessions": 1,
            "prediction": 1.0,
            "target_excess_return": 0.01,
            "prediction_role": "OOS",
            "oos_only": True,
        },
        {
            "symbol": "B",
            "isin": "INE000000002",
            "feature_session": "2026-01-01",
            "horizon_sessions": 1,
            "prediction": 2.0,
            "target_excess_return": 0.02,
            "prediction_role": "OOS",
            "oos_only": True,
        },
        {
            "symbol": "C",
            "isin": "INE000000003",
            "feature_session": "2026-01-01",
            "horizon_sessions": 1,
            "prediction": 2.0,
            "target_excess_return": 0.03,
            "prediction_role": "OOS",
            "oos_only": True,
        },
        {
            "symbol": "D",
            "isin": "INE000000004",
            "feature_session": "2026-01-01",
            "horizon_sessions": 1,
            "prediction": 4.0,
            "target_excess_return": 0.04,
            "prediction_role": "OOS",
            "oos_only": True,
        },
    ]
    normalized = normalize_oos_alpha_source(
        alpha_id="A1",
        alpha_version="v1",
        source_artifact_sha256="a" * 64,
        predictions=rows,
    )
    scores = {row["symbol"]: row["normalized_score"] for row in normalized}
    assert scores["A"] == pytest.approx(-1.0)
    assert scores["B"] == pytest.approx(0.0)
    assert scores["C"] == pytest.approx(0.0)
    assert scores["D"] == pytest.approx(1.0)


def test_ab001_rejects_development_predictions():
    row = _predictions(sessions=1, names=5)[0]
    row["prediction_role"] = "DEVELOPMENT"
    row["oos_only"] = False
    with pytest.raises(AlphaContractError, match="OOS-only"):
        normalize_oos_alpha_source(
            alpha_id="BAD",
            alpha_version="v1",
            source_artifact_sha256="d" * 64,
            predictions=[row],
        )


def test_standalone_and_pairwise_reports_capture_redundancy():
    library = _library()
    reports = standalone_alpha_reports(
        library,
        horizon_sessions=1,
    )
    assert reports["ALPHA_A"]["mean_rank_ic"] == pytest.approx(1.0)
    assert reports["ALPHA_C"]["mean_rank_ic"] == pytest.approx(-1.0)

    pairs = pairwise_alpha_diagnostics(
        library,
        horizon_sessions=1,
    )
    indexed = {
        (row["left_alpha_id"], row["right_alpha_id"]): row
        for row in pairs
    }
    assert indexed[("ALPHA_A", "ALPHA_B")][
        "mean_daily_spearman_prediction_correlation"
    ] > 0.99
    assert indexed[("ALPHA_A", "ALPHA_C")][
        "mean_daily_spearman_prediction_correlation"
    ] == pytest.approx(-1.0)


def test_incremental_identical_alpha_has_zero_paired_improvement():
    predictions = _predictions(mode="positive")
    library = build_alpha_library(
        [
            {
                "alpha_id": "A",
                "alpha_version": "v1",
                "source_artifact_sha256": "a" * 64,
                "predictions": predictions,
            },
            {
                "alpha_id": "A_COPY",
                "alpha_version": "v1",
                "source_artifact_sha256": "b" * 64,
                "predictions": predictions,
            },
        ]
    )
    result = incremental_alpha_contribution(
        library,
        existing_alpha_ids=["A"],
        candidate_alpha_id="A_COPY",
        horizon_sessions=1,
        newey_west_lag=0,
    )
    inference = result["challenger_minus_baseline_inference"]["metrics"]
    assert inference["rank_ic"]["mean"] == pytest.approx(0.0)
    assert inference["top_minus_bottom_spread"]["mean"] == pytest.approx(0.0)


def test_dynamic_blend_uses_only_prior_oos_evidence():
    # Session 21's outcome is deliberately reversed. Its weight must still be
    # determined only from sessions 1-20.
    library = _library(reverse_session="2026-01-21")
    blend = dynamic_blend(
        library,
        alpha_ids=["ALPHA_A", "ALPHA_B", "ALPHA_C"],
        horizon_sessions=1,
        lookback_sessions=60,
    )
    by_session = {
        row["feature_session"]: row
        for row in blend["weights_by_session"]
    }

    first = by_session["2026-01-01"]
    assert first["weighting_status"] == (
        "INSUFFICIENT_TRAILING_EVIDENCE_EQUAL_WEIGHT_FALLBACK"
    )
    assert first["weights"] == {
        "ALPHA_A": pytest.approx(1 / 3),
        "ALPHA_B": pytest.approx(1 / 3),
        "ALPHA_C": pytest.approx(1 / 3),
    }

    session_21 = by_session["2026-01-21"]
    assert session_21["weighting_status"] == (
        "TRAILING_EFFICACY_CORRELATION_SHRUNK"
    )
    assert session_21["efficacy"]["ALPHA_A"] > 0.9
    assert session_21["efficacy"]["ALPHA_B"] > 0.9
    assert session_21["efficacy"]["ALPHA_C"] == pytest.approx(0.0)
    assert max(session_21["weights"].values()) <= 0.5000000001
    assert sum(session_21["weights"].values()) == pytest.approx(1.0)
    assert session_21["weights"]["ALPHA_C"] == pytest.approx(0.0)


def test_dynamic_blend_fails_closed_on_mixed_outcome_maturity():
    source_a = _predictions(sessions=1, names=5)
    source_b = _predictions(sessions=1, names=5)
    source_b[0]["target_excess_return"] = None
    library = build_alpha_library(
        [
            {
                "alpha_id": "A",
                "alpha_version": "v1",
                "source_artifact_sha256": "a" * 64,
                "predictions": source_a,
            },
            {
                "alpha_id": "B",
                "alpha_version": "v1",
                "source_artifact_sha256": "b" * 64,
                "predictions": source_b,
            },
        ]
    )
    with pytest.raises(AlphaContractError, match="mixed maturity"):
        dynamic_blend(
            library,
            alpha_ids=["A", "B"],
            horizon_sessions=1,
        )
