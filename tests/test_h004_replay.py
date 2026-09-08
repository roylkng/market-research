import pandas as pd
import pytest

from marketlab.h004_replay import H004ReplayError, evaluate_h004_replay


def _frame() -> pd.DataFrame:
    rows = []
    quarters = ["2025-01-15", "2025-04-15", "2025-07-15", "2025-10-15"]
    for index, day in enumerate(quarters):
        rows.extend(
            [
                {
                    "symbol": f"HIT{index}",
                    "decision_date": day,
                    "primary_universe": True,
                    "stage1_eligible": True,
                    "stage2_trigger": True,
                    "explosive_20d_v1": True,
                    "lead_sessions_to_25pct": 4,
                    "return_20d_pct": 30,
                    "nifty500_excess_20d_pct": 20,
                    "positive_pnl_20d_pct": 10,
                    "momentum_baseline_trigger": False,
                },
                {
                    "symbol": f"MISS{index}",
                    "decision_date": day,
                    "primary_universe": True,
                    "stage1_eligible": False,
                    "stage2_trigger": False,
                    "explosive_20d_v1": True,
                    "lead_sessions_to_25pct": 5,
                    "return_20d_pct": 28,
                    "nifty500_excess_20d_pct": 18,
                    "positive_pnl_20d_pct": 0,
                    "momentum_baseline_trigger": False,
                },
                {
                    "symbol": f"FP{index}",
                    "decision_date": day,
                    "primary_universe": True,
                    "stage1_eligible": True,
                    "stage2_trigger": True,
                    "explosive_20d_v1": False,
                    "lead_sessions_to_25pct": None,
                    "return_20d_pct": 3,
                    "nifty500_excess_20d_pct": 1,
                    "positive_pnl_20d_pct": 1,
                    "momentum_baseline_trigger": True,
                },
                {
                    "symbol": f"BASE{index}",
                    "decision_date": day,
                    "primary_universe": True,
                    "stage1_eligible": False,
                    "stage2_trigger": False,
                    "explosive_20d_v1": False,
                    "lead_sessions_to_25pct": None,
                    "return_20d_pct": -2,
                    "nifty500_excess_20d_pct": -3,
                    "positive_pnl_20d_pct": 0,
                    "momentum_baseline_trigger": True,
                },
            ]
        )
    return pd.DataFrame(rows)


def test_replay_exposes_all_frozen_gate_metrics() -> None:
    result = evaluate_h004_replay(_frame())
    assert result.future_explosive_movers == 8
    assert result.stage1_signals == 8
    assert result.stage2_signals == 8
    assert result.explosive_mover_recall == pytest.approx(0.5)
    assert result.stage2_precision == pytest.approx(0.5)
    assert result.median_lead_sessions == pytest.approx(4.0)
    assert result.median_nifty500_excess_20d_pct > 0
    assert result.calendar_quarters_with_positive_median_excess == 4
    assert result.gate_recall
    assert result.gate_precision
    assert result.gate_lead_time
    assert result.gate_median_excess
    assert not result.gate_winner_concentration
    assert result.gate_beats_momentum
    assert not result.promoted


def test_replay_rejects_winner_only_sample() -> None:
    frame = _frame()
    frame = frame.loc[frame["explosive_20d_v1"]].copy()
    with pytest.raises(H004ReplayError, match="winner-only"):
        evaluate_h004_replay(frame)


def test_replay_rejects_missing_required_column() -> None:
    frame = _frame().drop(columns=["nifty500_excess_20d_pct"])
    with pytest.raises(H004ReplayError, match="missing required columns"):
        evaluate_h004_replay(frame)
