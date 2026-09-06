import pandas as pd

from marketlab.evaluation import (
    evaluate_binary_groups,
    evaluate_continuous_signal,
    unexpected_earnings,
    validate_hypothesis_registry,
    winner_concentration,
)


def test_unexpected_earnings_formula():
    current = pd.Series([12.0, 5.0])
    year_ago = pd.Series([10.0, 7.0])
    price = pd.Series([100.0, 50.0])
    result = unexpected_earnings(current, year_ago, price)
    assert result.tolist() == [0.02, -0.04]


def test_registry_rejects_live_capital_and_duplicate_ids():
    document = {
        "live_capital_allowed": True,
        "hypotheses": [
            {
                "id": "H001",
                "status": "REJECTED",
                "mechanism": "x",
                "signal": {"formula": "x"},
                "decision": {"entry_delay_sessions": 2, "holding_period_sessions": 20},
                "benchmarks": ["nifty_50"],
                "live_capital": False,
            },
            {
                "id": "H001",
                "status": "INCONCLUSIVE",
                "mechanism": "y",
                "signal": {"formula": "y"},
                "decision": {"entry_delay_sessions": 2, "holding_period_sessions": 20},
                "benchmarks": ["nifty_50"],
                "live_capital": True,
            },
        ],
    }
    errors = validate_hypothesis_registry(document)
    assert any("live_capital_allowed" in error for error in errors)
    assert any("duplicate hypothesis id" in error for error in errors)
    assert any("live_capital" in error for error in errors)


def test_continuous_signal_evaluation_detects_monotonic_signal():
    frame = pd.DataFrame({"signal": [1, 2, 3, 4, 5], "excess": [2, 4, 6, 8, 10]})
    result = evaluate_continuous_signal(frame, signal_col="signal", excess_return_col="excess")
    assert result.n == 5
    assert result.pearson > 0.99
    assert result.spearman > 0.99


def test_binary_group_evaluation_and_winner_concentration():
    frame = pd.DataFrame(
        {
            "group": ["Positive UE"] * 4 + ["Negative UE"] * 4,
            "excess": [3.0, 2.0, 1.0, 0.5, -3.0, -2.0, -1.0, 0.2],
        }
    )
    result = evaluate_binary_groups(
        frame,
        group_col="group",
        excess_return_col="excess",
        bootstrap_iterations=500,
    )
    assert result.positive_mean > result.negative_mean
    assert result.spread > 0

    concentration = winner_concentration(frame["excess"], top_n=2)
    assert concentration["mean_without_top_n"] < concentration["full_mean"]
