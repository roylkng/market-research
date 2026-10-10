from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketlab.timing import compute_snapshot


def _frame(values: np.ndarray) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-01", periods=len(values), tz="UTC")
    return pd.DataFrame(
        {"adj_close": values, "volume": np.full(len(values), 1_000_000)},
        index=index,
    )


def _analyze(stock: pd.DataFrame, benchmark: pd.DataFrame) -> dict:
    return compute_snapshot(
        stock, benchmark, symbol="EXAMPLE",
        as_of_session=stock.index[-1].date().isoformat(),
    )


def test_falling_series_is_not_research_entry_confirmed() -> None:
    sessions = 260
    benchmark = _frame(np.linspace(100.0, 120.0, sessions))
    stock = _frame(np.linspace(180.0, 90.0, sessions))
    result = _analyze(stock, benchmark)
    assert result["action"] == "WAIT_FALLING"
    assert result["flags"]["falling"] is True
    assert result["policies"]["D_multivariate_v1"] is False
    assert result["live_capital_allowed"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["probability_calibrated"] is False
    assert result["return_outcomes_opened"] is False


def test_insufficient_history_fails_closed() -> None:
    benchmark = _frame(np.linspace(100.0, 110.0, 260))
    stock = _frame(np.linspace(100.0, 105.0, 100))
    result = _analyze(stock, benchmark)
    assert result["action"] == "BLOCKED_DATA"
    assert "insufficient" in result["reason"]
    assert result["portfolio_eligibility_allowed"] is False


def test_future_price_rows_cannot_change_snapshot() -> None:
    sessions = 260
    n = np.arange(sessions)
    benchmark = _frame(100.0 + n * .04 + np.sin(n / 7))
    stock = _frame(100.0 + n * .06 + 3 * np.sin(n / 8))
    cutoff = stock.index[-1].date().isoformat()
    baseline = compute_snapshot(stock, benchmark, symbol="EXAMPLE", as_of_session=cutoff)
    more_index = pd.bdate_range(stock.index[-1] + pd.Timedelta(days=1), periods=20, tz="UTC")
    future_stock = pd.DataFrame(
        {"adj_close": np.linspace(200.0, 50.0, 20), "volume": 9_000_000},
        index=more_index,
    )
    future_bench = pd.DataFrame(
        {"adj_close": np.linspace(130.0, 90.0, 20), "volume": 9_000_000},
        index=more_index,
    )
    after = compute_snapshot(
        pd.concat([stock, future_stock]),
        pd.concat([benchmark, future_bench]),
        symbol="EXAMPLE",
        as_of_session=cutoff,
    )
    assert after == baseline


def test_missing_latest_session_and_bad_data_fail_closed() -> None:
    stock = _frame(np.linspace(100.0, 140.0, 260))
    bench = _frame(np.linspace(100.0, 125.0, 260))
    result = compute_snapshot(
        stock, bench,
        symbol="EXAMPLE",
        as_of_session="2030-01-01",
    )
    assert result["action"] == "BLOCKED_DATA"
    assert "last verified common bar" in result["reason"]

    bad = stock.copy()
    bad.loc[bad.index[-5], "adj_close"] = np.nan
    assert _analyze(bad, bench)["action"] == "BLOCKED_DATA"

    no_volume = stock.copy()
    no_volume.loc[no_volume.index[-1], "volume"] = 0
    assert _analyze(no_volume, bench)["action"] == "BLOCKED_DATA"

    negative = stock.copy()
    negative.loc[negative.index[-100], "adj_close"] = -1
    assert _analyze(negative, bench)["action"] == "BLOCKED_DATA"


def test_duplicate_or_unordered_history_rejected() -> None:
    stock = _frame(np.linspace(100.0, 140.0, 260))
    bench = _frame(np.linspace(100.0, 120.0, 260))
    dup = pd.concat([stock, stock.iloc[-1:]])
    with pytest.raises(ValueError, match="not unique"):
        _analyze(dup, bench)

    reverse = stock.iloc[::-1]
    with pytest.raises(ValueError, match="not unique"):
        _analyze(reverse, bench)


def test_no_implicit_lookahead_from_missing_asof_argument() -> None:
    stock = _frame(np.linspace(100.0, 140.0, 260))
    bench = _frame(np.linspace(100.0, 125.0, 260))
    with pytest.raises(TypeError):
        compute_snapshot(stock, bench, symbol="EXAMPLE")


def test_breakout_diagnostic_is_not_authorized_trade() -> None:
    n = np.arange(260)
    stock = _frame(100 + n * .2 + np.sin(n / 9))
    bench = _frame(100 + n * .07)
    result = _analyze(stock, bench)
    assert result["action"] in {
        "PAPER_ENTRY_ELIGIBLE_TREND",
        "PAPER_ENTRY_ELIGIBLE_REVERSAL",
        "WAIT_PULLBACK",
        "WAIT_CONFIRMATION",
        "WAIT_PULLBACK_CONFIRMATION",
    }
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
    assert result["probability_calibrated"] is False


def test_offline_cli_is_source_hashed_and_disables_capital(tmp_path) -> None:
    import json
    import subprocess
    import sys

    stock = _frame(np.linspace(100.0, 135.0, 260))
    bench = _frame(np.linspace(100.0, 118.0, 260))
    stock_csv = tmp_path / "stock.csv"
    bench_csv = tmp_path / "benchmark.csv"
    output = tmp_path / "timing.json"
    for frame, path in ((stock, stock_csv), (bench, bench_csv)):
        table = frame.copy()
        table.insert(0, "date", [value.date().isoformat() for value in frame.index])
        table.to_csv(path, index=False)
    subprocess.run(
        [
            sys.executable, "scripts/evaluate_h020_offline.py",
            "--stock-csv", str(stock_csv),
            "--benchmark-csv", str(bench_csv),
            "--as-of-session", stock.index[-1].date().isoformat(),
            "--symbol", "DEVELOPMENT",
            "--output", str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["id"] == "H020-TIMING-READONLY-v1"
    assert len(payload["stock_source_sha256"]) == 64
    assert payload["result"]["action"]
    assert payload["return_outcomes_opened"] is False
    assert payload["portfolio_eligibility_allowed"] is False
    assert payload["adjusted_price_and_corporate_actions_independently_verified"] is False
