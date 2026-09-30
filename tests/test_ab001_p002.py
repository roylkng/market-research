from datetime import date, timedelta

import pytest

from marketlab.ab001_p002 import (
    _causal_h024_events,
    _common_prediction_streams,
    _h024_event_lift,
)
from marketlab.alpha import AlphaContractError
from marketlab.alpha_diagnostics import newey_west_mean_inference
from marketlab.alpha_model import ModelExample


def _sessions(count=30):
    start = date(2026, 5, 14)
    return [
        (start + timedelta(days=index)).isoformat()
        for index in range(count)
    ]


def _source_panel(records):
    rows = list(records)
    next_id = 1000
    while len(rows) < 785:
        rows.append(
            {
                "app_id": str(next_id),
                "symbol": "FILLER",
                "exchange_disseminated_at_ist": "14-May-2026 10:00:00",
            }
        )
        next_id += 1
    return {"records": rows}


def _event(
    *,
    app_id,
    symbol="TEST",
    isin="INE000000001",
    known="14-May-2026 17:00:00",
    entry="2026-05-15",
):
    return {
        "event_id": f"E-{app_id}",
        "symbol": symbol,
        "entry_isin": isin,
        "entry_session_date": entry,
        "app_ids": [str(app_id)],
        "exchange_disseminated_at_ist": known,
    }


def _example(
    symbol,
    isin,
    *,
    session="2026-05-14",
    entry="2026-05-15",
    exit_session="2026-06-03",
    target=0.01,
):
    return ModelExample(
        symbol=symbol,
        isin=isin,
        feature_session=session,
        entry_session=entry,
        exit_session=exit_session,
        horizon_sessions=20,
        features={"x": 0.5},
        target_excess_return=target,
    )


def test_h024_causal_filter_excludes_after_cutoff_non_session_and_identity_gap():
    sessions = _sessions()
    source_records = [
        {
            "app_id": "1",
            "symbol": "TEST",
            "exchange_disseminated_at_ist": "14-May-2026 17:00:00",
        },
        {
            "app_id": "2",
            "symbol": "LATE",
            "exchange_disseminated_at_ist": "14-May-2026 19:00:00",
        },
        {
            "app_id": "3",
            "symbol": "OFFDAY",
            "exchange_disseminated_at_ist": "13-May-2026 12:00:00",
        },
        {
            "app_id": "4",
            "symbol": "WRONGISIN",
            "exchange_disseminated_at_ist": "14-May-2026 12:00:00",
        },
        {
            "app_id": "5",
            "symbol": "BADENTRY",
            "exchange_disseminated_at_ist": "14-May-2026 12:00:00",
        },
    ]
    panel = {
        "events": [
            _event(app_id="1"),
            _event(
                app_id="2",
                symbol="LATE",
                isin="INE000000002",
                known="14-May-2026 19:00:00",
            ),
            _event(
                app_id="3",
                symbol="OFFDAY",
                isin="INE000000003",
                known="13-May-2026 12:00:00",
            ),
            _event(
                app_id="4",
                symbol="WRONGISIN",
                isin="INE999999999",
                known="14-May-2026 12:00:00",
            ),
            _event(
                app_id="5",
                symbol="BADENTRY",
                isin="INE000000005",
                known="14-May-2026 12:00:00",
                entry="2026-05-16",
            ),
        ]
    }
    examples = [
        _example("TEST", "INE000000001"),
        _example("WRONGISIN", "INE000000004"),
        _example("BADENTRY", "INE000000005"),
    ]
    identities, diagnostics = _causal_h024_events(
        event_panel=panel,
        source_panel=_source_panel(source_records),
        examples=examples,
        market_session_dates=sessions,
    )
    assert identities == {
        "2026-05-14": {("TEST", "INE000000001")}
    }
    reasons = diagnostics["reason_counts"]
    assert reasons["AE001_EOD_H20_COMMON_EVENT"] == 1
    assert reasons["AFTER_1830_IST"] == 1
    assert reasons["DISCLOSED_NON_SESSION_DATE"] == 1
    assert reasons["NO_COMMON_COMPLETE_AE001_ROW"] == 1
    assert reasons["ENTRY_NOT_IMMEDIATE_NEXT_SESSION"] == 1


def test_h024_source_earliest_filing_is_authoritative_and_mismatch_fails_closed():
    sessions = _sessions()
    panel = {
        "events": [
            {
                **_event(
                    app_id="1",
                    known="14-May-2026 17:30:00",
                ),
                "app_ids": ["1", "2"],
            }
        ]
    }
    sources = _source_panel(
        [
            {
                "app_id": "1",
                "symbol": "TEST",
                "exchange_disseminated_at_ist": "14-May-2026 17:00:00",
            },
            {
                "app_id": "2",
                "symbol": "TEST",
                "exchange_disseminated_at_ist": "14-May-2026 17:30:00",
            },
        ]
    )
    with pytest.raises(
        AlphaContractError,
        match="source-derived H024 timestamps differ",
    ):
        _causal_h024_events(
            event_panel=panel,
            source_panel=sources,
            examples=[_example("TEST", "INE000000001")],
            market_session_dates=sessions,
        )


def test_common_streams_are_exact_full_cross_section_with_binary_h024_score():
    sessions = ["2026-05-14", "2026-05-15", "2026-05-16"]
    examples = []
    for session_index, session in enumerate(sessions):
        for stock_index in range(10):
            examples.append(
                _example(
                    f"S{stock_index:02d}",
                    f"INE{stock_index:09d}",
                    session=session,
                    target=(stock_index + session_index) / 1000.0,
                )
            )
    ae001 = [
        {
            "model_id": "A1",
            "model_sha256": "a" * 64,
            "symbol": row.symbol,
            "isin": row.isin,
            "feature_session": row.feature_session,
            "entry_session": row.entry_session,
            "exit_session": row.exit_session,
            "horizon_sessions": 20,
            "prediction": index / 100.0,
            "target_excess_return": row.target_excess_return,
            "prediction_role": "OOS",
            "oos_only": True,
            "live_capital_allowed": False,
        }
        for index, row in enumerate(examples)
    ]
    event_identity = ("S07", "INE000000007")
    event_sessions = {
        session: {event_identity}
        for session in sessions
    }
    left, right, diagnostics = _common_prediction_streams(
        ae001_predictions=ae001,
        examples=examples,
        event_identities=event_sessions,
    )
    assert len(left) == len(right) == 30
    assert diagnostics["common_session_count"] == 3
    assert diagnostics["common_stock_session_count"] == 30
    assert sum(float(row["prediction"]) for row in right) == pytest.approx(3.0)
    selected_by_session = {
        session: [
            (row["symbol"], row["isin"])
            for row in right
            if row["feature_session"] == session
            and row["prediction"] == 1.0
        ]
        for session in sessions
    }
    assert all(
        selected == [event_identity]
        for selected in selected_by_session.values()
    )


def test_h024_event_lift_uses_event_vs_non_event_targets_and_hac():
    rows = []
    for session_index in range(25):
        session = f"2026-05-{session_index + 1:02d}"
        for stock_index in range(10):
            event = stock_index == 0
            rows.append(
                {
                    "feature_session": session,
                    "prediction": 1.0 if event else 0.0,
                    "target_excess_return": (
                        0.03 + session_index * 0.0001
                        if event
                        else 0.01
                    ),
                }
            )
    report = _h024_event_lift(rows)
    assert report["session_count"] == 25
    assert report["event_observation_count"] == 25
    assert report["mean_session_event_lift"] > 0.019
    inference = report["newey_west_event_lift_inference"]
    assert inference["count"] == 25
    assert inference["newey_west_lag"] == 19
    assert inference["mean"] > 0


def test_newey_west_horizon_20_lag_is_capped_only_by_sample_size():
    inference = newey_west_mean_inference(
        [0.01 + index * 0.0001 for index in range(10)],
        max_lag=19,
    )
    assert inference["newey_west_lag"] == 9
