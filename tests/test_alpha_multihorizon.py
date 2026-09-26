from datetime import date, timedelta

from marketlab.alpha import digest
from marketlab.alpha_corporate_actions import ACTION_LEDGER_ID
from marketlab.alpha_multihorizon import (
    build_action_safe_horizon_examples,
    run_action_safe_horizon_walkforward,
)
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
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
            open_price = prior
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
                    volume=100_000,
                    turnover_inr=30_000_000,
                    trade_count=1_000,
                )
            )
        benchmark_open = 20_000.0
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
                "equities": equities,
                "benchmark": benchmark,
            }
        )
    return result


def _ledger(start, end, action_symbol=None, action_date=None):
    records = []
    if action_symbol:
        records.append(
            {
                "symbol": action_symbol,
                "status": "READY",
                "actions": [
                    {"ex_date": action_date, "subject": "BONUS 1:1"}
                ],
                "unresolved_subjects": [],
            }
        )
    unsigned = {
        "schema_version": 1,
        "ledger_id": ACTION_LEDGER_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "coverage_start_date": start,
        "coverage_end_date": end,
        "source_chunks": [],
        "record_count": len(records),
        "records": records,
        "no_record_means_no_share_changing_action_in_covered_source": True,
        "historical_source_retrieved_prospectively": False,
        "live_capital_allowed": False,
    }
    return {**unsigned, "ledger_sha256": digest(unsigned)}


def _feature_panel(market):
    rows = []
    feature_names = [definition.name for definition in PRICE_VOLUME_DEFINITIONS]
    for day_index in range(60, 120):
        day = market[day_index]["session_date"]
        for symbol_index in range(12):
            rows.append(
                {
                    "feature_session": day,
                    "symbol": f"S{symbol_index:02d}",
                    "isin": f"INE{symbol_index:09d}",
                    "values": {
                        name: symbol_index / 11.0
                        for name in feature_names
                    },
                }
            )
    ledger = _ledger(
        market[0]["session_date"],
        market[-1]["session_date"],
    )
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-ACTION-SAFE",
        "corporate_action_ledger_sha256": ledger["ledger_sha256"],
        "feature_definitions": [
            {
                "name": definition.name,
                "family": definition.family,
                "version": definition.version,
                "description": definition.description,
                "lookback_sessions": definition.lookback_sessions,
                "availability_lag_sessions": definition.availability_lag_sessions,
            }
            for definition in PRICE_VOLUME_DEFINITIONS
        ],
        "rows": rows,
        "outcomes_attached": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel, ledger


def test_multihorizon_examples_block_action_inside_holding_window():
    market = _market()
    panel, _ = _feature_panel(market)
    action_day = market[66]["session_date"]
    ledger = _ledger(
        market[0]["session_date"],
        market[-1]["session_date"],
        action_symbol="S00",
        action_date=action_day,
    )
    panel["corporate_action_ledger_sha256"] = ledger["ledger_sha256"]
    panel["panel_sha256"] = digest(
        {key: value for key, value in panel.items() if key != "panel_sha256"}
    )
    examples, exclusions = build_action_safe_horizon_examples(
        feature_panel=panel,
        market_panel={"sessions": market},
        action_ledger=ledger,
        horizons=(1, 5, 20),
    )
    assert examples[1]
    assert exclusions["H5:CORPORATE_ACTION_BLOCKED"] > 0
    assert exclusions["H20:CORPORATE_ACTION_BLOCKED"] > 0


def test_multihorizon_walkforward_purges_by_horizon_exit():
    market = _market()
    panel, ledger = _feature_panel(market)
    report = run_action_safe_horizon_walkforward(
        feature_panel=panel,
        market_panel={"panel_sha256": "x", "sessions": market},
        action_ledger=ledger,
        folds_by_horizon={
            5: [
                {
                    "start": market[90]["session_date"],
                    "end": market[99]["session_date"],
                }
            ],
            20: [
                {
                    "start": market[100]["session_date"],
                    "end": market[109]["session_date"],
                }
            ],
        },
    )
    assert set(report["horizons"]) == {"5", "20"}
    assert (
        report["horizons"]["20"]["folds"][0]["training_last_exit_session"]
        < report["horizons"]["20"]["folds"][0]["start"]
    )
    assert report["live_capital_allowed"] is False
