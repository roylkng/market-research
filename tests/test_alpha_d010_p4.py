from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_d010_p4 import (
    D010_DEFINITIONS,
    SHORT_P3B_REPORT_SHA256,
    SLB_P3_REPORT_SHA256,
    augment_feature_panel_with_d010,
    summarize_p4,
)
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS


def _market_and_sources(*, missing_short_index=None, duplicate_slb=False):
    start = date(2026, 8, 31)
    market_sessions = []
    short_sessions = []
    slb_sessions = []
    for index in range(22):
        day = start + timedelta(days=index)
        market_sessions.append(
            {
                "session_date": day.isoformat(),
                "udiff_sha256": f"{index + 1:064x}",
                "benchmark_sha256": f"{index + 101:064x}",
                "equities": [
                    {
                        "session_date": day.isoformat(),
                        "symbol": "TEST",
                        "isin": "INE000000001",
                        "open_price": 100.0,
                        "high_price": 102.0,
                        "low_price": 99.0,
                        "close_price": 101.0,
                        "previous_close": 100.0,
                        "volume": 1000.0,
                        "turnover_inr": 30_000_000.0,
                        "trade_count": 100.0,
                    }
                ],
                "benchmark": {
                    "benchmark_id": "nifty_500",
                    "index_name": "Nifty 500",
                    "session_date": day.isoformat(),
                    "open_price": 20_000.0,
                    "close_price": 20_010.0,
                },
            }
        )
        if index == 0:
            continue
        publication = day.isoformat()
        trade = (day - timedelta(days=1)).isoformat()
        short_ready = index != missing_short_index
        short_sessions.append(
            {
                "publication_session": publication,
                "trade_session": trade,
                "source_status": "READY" if short_ready else "UNAVAILABLE",
                "raw_sha256": f"{index + 201:064x}" if short_ready else None,
                "source_row_count": 1 if short_ready else 0,
                "trade_date_mapped_row_count": 1 if short_ready else 0,
                "trade_date_unmatched_row_count": 0,
                "publication_continuity_row_count": 1 if short_ready else 0,
                "publication_discontinuity_row_count": 0,
                "duplicate_symbol_row_count": 0,
                "duplicate_symbols": [],
                "rows": (
                    [
                        {
                            "source_row_index": 0,
                            "security_name": "Example",
                            "source_symbol": "TEST",
                            "trade_date": trade,
                            "quantity": float(50 + index),
                            "trade_date_mapped_isin": "INE000000001",
                            "publication_symbol": "TEST",
                            "trade_date_identity_status": "MAPPED_EQ",
                            "publication_continuity_status": "SAME_ISIN_PRESENT",
                        }
                    ]
                    if short_ready
                    else []
                ),
            }
        )
        slb_rows = [
            {
                "source_row_index": 0,
                "symbol": "TEST",
                "series": "X1",
                "outstanding_quantity": float(100 + index),
                "mapped_isin": "INE000000001",
                "identity_status": "MAPPED_EQ",
            }
        ]
        if duplicate_slb and index == 21:
            slb_rows.append(
                {
                    "source_row_index": 1,
                    "symbol": "TEST",
                    "series": "X1",
                    "outstanding_quantity": 1.0,
                    "mapped_isin": "INE000000001",
                    "identity_status": "MAPPED_EQ",
                }
            )
        slb_sessions.append(
            {
                "session_date": publication,
                "udiff_eq_count": 1,
                "short_selling": {
                    "source_status": "UNAVAILABLE",
                    "raw_sha256": None,
                    "row_count": 0,
                    "mapped_row_count": 0,
                    "unmatched_row_count": 0,
                    "duplicate_symbol_row_count": 0,
                    "duplicate_symbols": [],
                    "rows": [],
                },
                "slb_open_positions": {
                    "source_status": "READY",
                    "raw_sha256": f"{index + 301:064x}",
                    "row_count": len(slb_rows),
                    "mapped_row_count": len(slb_rows),
                    "unmatched_row_count": 0,
                    "duplicate_symbol_row_count": max(0, len(slb_rows) - 1),
                    "duplicate_symbol_series_row_count": max(
                        0, len(slb_rows) - 1
                    ),
                    "duplicate_symbols": ["TEST"] if len(slb_rows) > 1 else [],
                    "series_counts": {"X1": len(slb_rows)},
                    "rows": slb_rows,
                },
            }
        )

    market = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET",
        "sessions": market_sessions,
        "live_capital_allowed": False,
    }
    market["panel_sha256"] = digest(market)

    short = {
        "schema_version": 1,
        "panel_id": "AE001-D010-P3B-SHORT-PANEL-v1",
        "report_sha256": SHORT_P3B_REPORT_SHA256,
        "session_count": len(short_sessions),
        "sessions": short_sessions,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    short["panel_sha256"] = digest(short)

    slb = {
        "schema_version": 1,
        "panel_id": "AE001-D010-P3-SOURCE-PANEL-v1",
        "report_sha256": SLB_P3_REPORT_SHA256,
        "session_count": len(slb_sessions),
        "sessions": slb_sessions,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    slb["panel_sha256"] = digest(slb)

    final_day = market_sessions[-1]["session_date"]
    definitions = [
        {
            "name": definition.name,
            "family": definition.family,
            "version": definition.version,
            "description": definition.description,
            "lookback_sessions": definition.lookback_sessions,
            "availability_lag_sessions": definition.availability_lag_sessions,
        }
        for definition in PRICE_VOLUME_DEFINITIONS
    ]
    base = {
        "schema_version": 1,
        "panel_id": "AE001-ACTION-SAFE-BASE",
        "feature_definitions": definitions,
        "feature_set_sha256": digest(sorted(definitions, key=lambda row: row["name"])),
        "sessions": [
            {
                "session_date": final_day,
                "eligible_count": 1,
                "universe_sha256": "old",
            }
        ],
        "rows": [
            {
                "feature_session": final_day,
                "decision_timestamp": f"{final_day}T18:30:00+05:30",
                "symbol": "TEST",
                "isin": "INE000000001",
                "universe_sha256": "old",
                "feature_set_sha256": "old",
                "values": {
                    definition.name: 0.1
                    for definition in PRICE_VOLUME_DEFINITIONS
                },
                "known_at": f"{final_day}T18:00:00+05:30",
                "outcomes_attached": False,
            }
        ],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    base["panel_sha256"] = digest(base)
    return market, short, slb, base


def test_d010_p4_builds_exact_seven_features_on_common_base_row():
    market, short, slb, base = _market_and_sources()
    panel = augment_feature_panel_with_d010(
        feature_panel=base,
        market_panel=market,
        short_panel=short,
        slb_panel=slb,
    )
    assert panel["feature_row_count"] == 1
    assert len(panel["feature_definitions"]) == 25
    row = panel["rows"][0]
    assert {definition.name for definition in D010_DEFINITIONS}.issubset(
        row["values"]
    )
    assert row["values"]["short_volume_share_lag1"] == pytest.approx(0.071)
    assert row["values"]["short_volume_share_change_1"] == pytest.approx(0.001)
    assert row["values"]["slb_outstanding_days_volume20"] == pytest.approx(
        0.121
    )
    assert row["values"]["slb_outstanding_change_days_volume20"] == pytest.approx(
        0.001
    )
    assert row["values"]["slb_active_series_count"] == pytest.approx(1.0)
    assert panel["outcomes_attached"] is False


def test_ready_file_absence_is_numeric_zero():
    market, short, slb, base = _market_and_sources()
    short["sessions"][-1]["rows"] = []
    short["sessions"][-1]["source_row_count"] = 0
    short["sessions"][-1]["trade_date_mapped_row_count"] = 0
    short["sessions"][-1]["publication_continuity_row_count"] = 0
    unsigned = dict(short)
    unsigned.pop("panel_sha256", None)
    short["panel_sha256"] = digest(unsigned)

    slb["sessions"][-1]["slb_open_positions"]["rows"] = []
    slb["sessions"][-1]["slb_open_positions"]["row_count"] = 0
    slb["sessions"][-1]["slb_open_positions"]["mapped_row_count"] = 0
    unsigned = dict(slb)
    unsigned.pop("panel_sha256", None)
    slb["panel_sha256"] = digest(unsigned)

    panel = augment_feature_panel_with_d010(
        feature_panel=base,
        market_panel=market,
        short_panel=short,
        slb_panel=slb,
    )
    values = panel["rows"][0]["values"]
    assert values["short_volume_share_lag1"] == pytest.approx(0.0)
    assert values["slb_outstanding_days_volume20"] == pytest.approx(0.0)
    assert values["slb_active_series_count"] == pytest.approx(0.0)


def test_source_gap_breaks_d010_history_window():
    market, short, slb, base = _market_and_sources(missing_short_index=10)
    panel = augment_feature_panel_with_d010(
        feature_panel=base,
        market_panel=market,
        short_panel=short,
        slb_panel=slb,
    )
    assert panel["feature_row_count"] == 0
    assert panel["excluded_identity_history_row_count"] == 1


def test_duplicate_slb_identity_series_fails_closed():
    market, short, slb, base = _market_and_sources(duplicate_slb=True)
    with pytest.raises(AlphaContractError, match="duplicate SLB ISIN"):
        augment_feature_panel_with_d010(
            feature_panel=base,
            market_panel=market,
            short_panel=short,
            slb_panel=slb,
        )


def test_p4_summary_promotes_when_frozen_gates_are_met(monkeypatch):
    from marketlab import alpha_d010_p4 as module

    market, short, slb, base = _market_and_sources()
    panel = augment_feature_panel_with_d010(
        feature_panel=base,
        market_panel=market,
        short_panel=short,
        slb_panel=slb,
    )
    monkeypatch.setattr(module, "MIN_FEATURE_SESSIONS", 1)
    monkeypatch.setattr(module, "MIN_FEATURE_ROWS", 1)
    report = summarize_p4(panel)
    assert report["status"] == "PROMOTE_INCREMENTAL_ALPHA_TRIAL"
    assert report["feature_count"] == 25
    assert report["return_labels_opened"] is False
    assert report["model_fit_performed"] is False
