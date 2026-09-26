from dataclasses import asdict
from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_history import build_historical_feature_panel
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_walkforward import (
    build_one_session_examples,
    run_ridge_walkforward,
)
from marketlab.marketdata import IndexDailyPrice


def _market(sessions=180, symbols=12):
    start = date(2026, 1, 1)
    prices = {f"S{index:02d}": 100.0 + index for index in range(symbols)}
    result = []
    for day_index in range(sessions):
        day = (start + timedelta(days=day_index)).isoformat()
        equities = []
        for symbol_index in range(symbols):
            symbol = f"S{symbol_index:02d}"
            prior = prices[symbol]
            # Stable cross-sectional relation: higher symbol index has stronger intraday drift.
            open_price = prior * (1.0 + 0.0001 * ((day_index % 3) - 1))
            close_price = open_price * (1.0 + symbol_index * 0.0002)
            prices[symbol] = close_price
            equities.append(
                DailyEquityObservation(
                    session_date=day,
                    symbol=symbol,
                    isin=f"INE{symbol_index:09d}",
                    open_price=open_price,
                    high_price=max(open_price, close_price) * 1.01,
                    low_price=min(open_price, close_price) * 0.99,
                    close_price=close_price,
                    previous_close=prior,
                    volume=100_000 + symbol_index * 1_000 + day_index,
                    turnover_inr=30_000_000 + symbol_index * 100_000 + day_index,
                    trade_count=1_000 + symbol_index * 10 + day_index,
                )
            )
        benchmark_open = 20_000 + day_index
        benchmark = IndexDailyPrice(
            benchmark_id="nifty_500",
            index_name="Nifty 500",
            session_date=day,
            open_price=benchmark_open,
            close_price=benchmark_open * 1.0002,
        )
        result.append(
            {
                "session_date": day,
                "udiff_sha256": f"{day_index + 1:064x}",
                "benchmark_sha256": f"{day_index + 5000:064x}",
                "equities": equities,
                "benchmark": benchmark,
            }
        )
    return result


def _sealed_market_panel(sessions):
    normalized = []
    for session in sessions:
        normalized.append(
            {
                **{
                    key: value
                    for key, value in session.items()
                    if key not in {"equities", "benchmark"}
                },
                "equities": [
                    asdict(row) if isinstance(row, DailyEquityObservation) else row
                    for row in session["equities"]
                ],
                "benchmark": (
                    asdict(session["benchmark"])
                    if isinstance(session["benchmark"], IndexDailyPrice)
                    else session["benchmark"]
                ),
            }
        )
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET-PANEL",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "sessions": normalized,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def test_one_session_examples_use_next_session_open_to_close():
    market = _market()
    features = build_historical_feature_panel(sessions=market)
    examples, exclusions = build_one_session_examples(
        feature_panel=features,
        market_panel=_sealed_market_panel(market),
    )
    assert examples
    first = examples[0]
    assert first.entry_session == first.exit_session
    assert first.entry_session > first.feature_session
    assert exclusions["NONFINITE_TARGET"] == 0


def test_walkforward_is_purged_and_oos():
    market = _market()
    features = build_historical_feature_panel(sessions=market)
    report = run_ridge_walkforward(
        feature_panel=features,
        market_panel=_sealed_market_panel(market),
        folds=[
            {"start": market[100]["session_date"], "end": market[129]["session_date"]},
            {"start": market[130]["session_date"], "end": market[159]["session_date"]},
        ],
        l2=1.0,
    )
    assert report["oos_prediction_count"] > 0
    assert report["ridge"]["session_count"] > 0
    assert all(
        fold["training_last_exit_session"] < fold["start"]
        for fold in report["folds"]
    )
    assert all(
        prediction["prediction_role"] == "OOS"
        for prediction in report["oos_predictions"]
    )
    assert report["live_capital_allowed"] is False
    assert len(report["input_market_panel_sha256"]) == 64
    assert len(report["input_feature_panel_sha256"]) == 64
    assert len(report["ranked_feature_panel_sha256"]) == 64
    assert report["folds"][0]["ridge_model"]["model_sha256"] == report["folds"][0]["model_sha256"]
    assert "NOT_A_TURNOVER_OR_IMPLEMENTABLE_PNL_MODEL" in report["cost_stress_interpretation"]


def test_walkforward_rejects_tampered_input_panel():
    market = _market()
    features = build_historical_feature_panel(sessions=market)
    sealed = _sealed_market_panel(market)
    sealed["sessions"][0]["session_date"] = "1999-01-01"
    with pytest.raises(AlphaContractError, match="market panel hash mismatch"):
        run_ridge_walkforward(
            feature_panel=features,
            market_panel=sealed,
            folds=[
                {"start": market[100]["session_date"], "end": market[129]["session_date"]}
            ],
        )
