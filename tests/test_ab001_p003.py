from datetime import date, timedelta

import pytest

from marketlab.ab001_p003 import (
    _reconstruct_oos_pair,
)
from marketlab.alpha_model import ModelExample


def _examples():
    rows = []
    start = date(2025, 9, 1)
    for index in range(130):
        day = start + timedelta(days=index)
        rows.append(
            ModelExample(
                symbol=f"S{index:03d}",
                isin=f"INE{index:09d}",
                feature_session=day.isoformat(),
                entry_session=(day + timedelta(days=1)).isoformat(),
                exit_session=(day + timedelta(days=5)).isoformat(),
                horizon_sessions=5,
                features={
                    "core": float(index) / 100.0,
                    "futures": float(index % 7) / 10.0,
                },
                target_excess_return=float(index) / 10000.0,
            )
        )
    for offset in range(5):
        day = date(2026, 4, 1) + timedelta(days=offset)
        rows.append(
            ModelExample(
                symbol=f"A{offset}",
                isin=f"INEA{offset:08d}",
                feature_session=day.isoformat(),
                entry_session=(day + timedelta(days=1)).isoformat(),
                exit_session=(day + timedelta(days=5)).isoformat(),
                horizon_sessions=5,
                features={"core": 0.1 + offset, "futures": 0.2 - offset * 0.01},
                target_excess_return=0.01 + offset * 0.001,
            )
        )
    for offset in range(5):
        day = date(2026, 7, 1) + timedelta(days=offset)
        rows.append(
            ModelExample(
                symbol=f"B{offset}",
                isin=f"INEB{offset:08d}",
                feature_session=day.isoformat(),
                entry_session=(day + timedelta(days=1)).isoformat(),
                exit_session=(day + timedelta(days=5)).isoformat(),
                horizon_sessions=5,
                features={"core": 0.3 + offset, "futures": 0.4 + offset * 0.02},
                target_excess_return=0.02 + offset * 0.001,
            )
        )
    return rows


def test_p003_residual_is_exactly_additive_and_row_aligned():
    core, delta, full, lineage = _reconstruct_oos_pair(
        examples=_examples(),
        base_names=["core"],
        full_names=["core", "futures"],
    )
    assert len(core) == len(delta) == len(full) == 10
    assert len(lineage) == 2
    for core_row, delta_row, full_row in zip(core, delta, full, strict=True):
        assert (
            core_row["feature_session"],
            core_row["symbol"],
            core_row["isin"],
            core_row["entry_session"],
            core_row["exit_session"],
        ) == (
            full_row["feature_session"],
            full_row["symbol"],
            full_row["isin"],
            full_row["entry_session"],
            full_row["exit_session"],
        )
        assert float(core_row["target_excess_return"]) == pytest.approx(
            float(full_row["target_excess_return"])
        )
        assert (
            float(core_row["prediction"]) + float(delta_row["prediction"])
        ) == pytest.approx(float(full_row["prediction"]), abs=1e-15)
        assert delta_row["prediction_role"] == "OOS"
        assert delta_row["oos_only"] is True


def test_p003_training_is_purged_before_each_validation_fold():
    _, _, _, lineage = _reconstruct_oos_pair(
        examples=_examples(),
        base_names=["core"],
        full_names=["core", "futures"],
    )
    assert lineage[0]["training_last_exit_session"] < lineage[0]["start"]
    assert lineage[1]["training_last_exit_session"] < lineage[1]["start"]
    assert lineage[1]["training_example_count"] > lineage[0]["training_example_count"]
