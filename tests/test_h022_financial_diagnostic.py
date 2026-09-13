from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab import h022_financial_diagnostic as diagnostic


def _sealed_panel(records: list[dict[str, object]]) -> dict[str, object]:
    panel: dict[str, object] = {
        "schema_version": 1,
        "diagnostic_id": "H022-D002",
        "hypothesis_id": "H022",
        "records": deepcopy(records),
    }
    panel["panel_sha256"] = diagnostic._canonical_hash(panel)
    return panel


def test_recovery_classification_locks_promising_style_shape() -> None:
    base = {
        "observation_count": 120,
        "top_minus_bottom_mean_excess_pp": 2.0,
        "top_quintile_median_excess_pp": 0.1,
        "top_quintile_benchmark_beat_rate": 0.55,
    }
    assert diagnostic._recovery_classification(base) == "RECOVERS_PROMISING_STYLE"

    too_few = dict(base, observation_count=99)
    assert (
        diagnostic._recovery_classification(too_few)
        == "INSUFFICIENT_ADDITIONAL_NONFINANCIAL_ROWS"
    )

    weak_spread = dict(base, top_minus_bottom_mean_excess_pp=1.99)
    assert (
        diagnostic._recovery_classification(weak_spread)
        == "DOES_NOT_RECOVER_PROMISING_STYLE"
    )

    weak_median = dict(base, top_quintile_median_excess_pp=0.0)
    assert (
        diagnostic._recovery_classification(weak_median)
        == "DOES_NOT_RECOVER_PROMISING_STYLE"
    )

    weak_beat = dict(base, top_quintile_benchmark_beat_rate=0.549)
    assert (
        diagnostic._recovery_classification(weak_beat)
        == "DOES_NOT_RECOVER_PROMISING_STYLE"
    )


def test_additional_regression_recovers_distinct_financial_slope() -> None:
    rows: list[dict[str, object]] = []
    for index, signal in enumerate((-2.0, -1.0, 1.0, 2.0)):
        rows.append(
            {
                "source_id": f"n{index}",
                "symbol": f"N{index}",
                "h022_signal": signal,
                "future_60d_excess_pp": 3.0 * signal,
                "composition_group": "ADDITIONAL_HISTORICAL_NIFTY200",
                "industry": "Capital Goods",
            }
        )
        rows.append(
            {
                "source_id": f"f{index}",
                "symbol": f"F{index}",
                "h022_signal": signal,
                "future_60d_excess_pp": -2.0 * signal,
                "composition_group": "ADDITIONAL_HISTORICAL_NIFTY200",
                "industry": "Financial Services",
            }
        )
    nonfinancial, financial, interaction = diagnostic._additional_coefficients(rows)
    assert nonfinancial > 0
    assert financial < 0
    assert interaction < 0


def test_summary_uses_frozen_financial_label_and_excludes_null_industry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[dict[str, object]] = []
    for index in range(10):
        signal = float(index - 5)
        records.append(
            {
                "source_id": f"c{index}",
                "symbol": f"C{index}",
                "h022_signal": signal,
                "future_60d_excess_pp": signal,
                "composition_group": "CURRENT_U001",
                "industry": "Capital Goods",
            }
        )
        records.append(
            {
                "source_id": f"n{index}",
                "symbol": f"N{index}",
                "h022_signal": signal,
                "future_60d_excess_pp": 2.0 * signal,
                "composition_group": "ADDITIONAL_HISTORICAL_NIFTY200",
                "industry": "Healthcare",
            }
        )
        records.append(
            {
                "source_id": f"f{index}",
                "symbol": f"F{index}",
                "h022_signal": signal,
                "future_60d_excess_pp": -signal,
                "composition_group": "ADDITIONAL_HISTORICAL_NIFTY200",
                "industry": "Financial Services",
            }
        )
    records.append(
        {
            "source_id": "missing-industry",
            "symbol": "MISSING",
            "h022_signal": 1.0,
            "future_60d_excess_pp": 100.0,
            "composition_group": "ADDITIONAL_HISTORICAL_NIFTY200",
            "industry": None,
        }
    )
    panel = _sealed_panel(records)

    monkeypatch.setattr(diagnostic, "PANEL_SHA256", panel["panel_sha256"])
    monkeypatch.setattr(diagnostic, "EXPECTED_RECORD_COUNT", len(records))
    monkeypatch.setattr(diagnostic, "BOOTSTRAP_ITERATIONS", 100)
    monkeypatch.setattr(diagnostic, "MIN_RECOVERY_OBSERVATIONS", 10)

    summary = diagnostic.summarize_financial_composition(panel)
    assert summary["labelled_observation_count"] == 30
    assert summary["excluded_null_industry_count"] == 1
    assert summary["cells"]["CURRENT_U001_NONFINANCIAL"]["observation_count"] == 10
    assert summary["cells"]["ADDITIONAL_NONFINANCIAL"]["observation_count"] == 10
    assert summary["cells"]["ADDITIONAL_FINANCIAL"]["observation_count"] == 10
    assert (
        summary["additional_nonfinancial_recovery_classification"]
        == "RECOVERS_PROMISING_STYLE"
    )


def test_summary_fails_if_current_u001_contains_financial_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [
        {
            "source_id": "c1",
            "symbol": "CUR",
            "h022_signal": 1.0,
            "future_60d_excess_pp": 1.0,
            "composition_group": "CURRENT_U001",
            "industry": "Financial Services",
        },
        {
            "source_id": "n1",
            "symbol": "NONFIN",
            "h022_signal": -1.0,
            "future_60d_excess_pp": -1.0,
            "composition_group": "ADDITIONAL_HISTORICAL_NIFTY200",
            "industry": "Healthcare",
        },
        {
            "source_id": "f1",
            "symbol": "FIN",
            "h022_signal": 1.0,
            "future_60d_excess_pp": 1.0,
            "composition_group": "ADDITIONAL_HISTORICAL_NIFTY200",
            "industry": "Financial Services",
        },
    ]
    panel = _sealed_panel(records)
    monkeypatch.setattr(diagnostic, "PANEL_SHA256", panel["panel_sha256"])
    monkeypatch.setattr(diagnostic, "EXPECTED_RECORD_COUNT", len(records))

    with pytest.raises(
        diagnostic.H022FinancialDiagnosticError,
        match="current U001 unexpectedly contains Financial Services",
    ):
        diagnostic.summarize_financial_composition(panel)
