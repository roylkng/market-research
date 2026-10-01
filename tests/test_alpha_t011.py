from dataclasses import asdict

import pytest

from marketlab.alpha import digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_t011 import (
    AUGMENTED37_NAMES,
    BASE27_NAMES,
    LAGGED_FUTURES_MAP,
    build_t011_lagged_feature_panel,
    summarize_t011_source,
)


def _panel(definitions, rows, panel_id):
    defs = [asdict(definition) for definition in definitions]
    panel = {
        "schema_version": 1,
        "panel_id": panel_id,
        "feature_definitions": defs,
        "feature_set_sha256": digest(defs),
        "rows": rows,
        "sessions": [],
        "session_count": 0,
        "feature_row_count": len(rows),
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _inputs():
    base_defs = [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    t005_defs = [*base_defs, *FUTURES_DEFINITIONS]
    base_values = {
        definition.name: (index + 1) / 100.0
        for index, definition in enumerate(base_defs)
    }
    futures_values = {
        definition.name: 0.2 + index / 100.0
        for index, definition in enumerate(FUTURES_DEFINITIONS)
    }
    current = _panel(
        base_defs,
        [
            {
                "feature_session": "2026-09-25",
                "symbol": "TEST",
                "isin": "INE000000001",
                "values": base_values,
                "universe_sha256": "u" * 64,
            }
        ],
        "CURRENT27",
    )
    t005 = _panel(
        t005_defs,
        [
            {
                "feature_session": "2026-09-24",
                "symbol": "TEST",
                "isin": "INE000000001",
                "values": {**base_values, **futures_values},
                "universe_sha256": "v" * 64,
            }
        ],
        "T005",
    )
    market = {
        "schema_version": 1,
        "panel_id": "MARKET",
        "sessions": [
            {"session_date": "2026-09-24"},
            {"session_date": "2026-09-25"},
        ],
        "live_capital_allowed": False,
    }
    market["panel_sha256"] = digest(market)
    return market, current, t005, futures_values


def _patch_hashes(monkeypatch, market, current, t005):
    monkeypatch.setattr(
        "marketlab.alpha_t011.EXPECTED_MARKET_PANEL_SHA256",
        market["panel_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.alpha_t011.EXPECTED_CURRENT27_PANEL_SHA256",
        current["panel_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.alpha_t011.EXPECTED_T005_PANEL_SHA256",
        t005["panel_sha256"],
    )


def test_t011_copies_only_previous_completed_session_futures(monkeypatch):
    market, current, t005, futures_values = _inputs()
    _patch_hashes(monkeypatch, market, current, t005)
    panel = build_t011_lagged_feature_panel(
        market_panel=market,
        current27_panel=current,
        t005_panel=t005,
    )
    assert panel["feature_row_count"] == 1
    assert panel["session_count"] == 1
    row = panel["rows"][0]
    assert row["lagged_futures_source_session"] == "2026-09-24"
    assert set(row["values"]) == set(AUGMENTED37_NAMES)
    for source_name, expected in futures_values.items():
        assert row["values"][LAGGED_FUTURES_MAP[source_name]] == pytest.approx(
            expected
        )
    assert panel["max_copied_futures_abs_diff"] == pytest.approx(0.0)


def test_t011_requires_exact_isin_continuity(monkeypatch):
    market, current, t005, _ = _inputs()
    t005["rows"][0]["isin"] = "INE999999999"
    unsigned = dict(t005)
    unsigned.pop("panel_sha256", None)
    t005["panel_sha256"] = digest(unsigned)
    _patch_hashes(monkeypatch, market, current, t005)
    panel = build_t011_lagged_feature_panel(
        market_panel=market,
        current27_panel=current,
        t005_panel=t005,
    )
    assert panel["feature_row_count"] == 0
    assert panel["excluded_missing_lagged_futures_row_count"] == 1


def test_t011_source_summary_never_opens_outcomes(monkeypatch):
    market, current, t005, _ = _inputs()
    _patch_hashes(monkeypatch, market, current, t005)
    panel = build_t011_lagged_feature_panel(
        market_panel=market,
        current27_panel=current,
        t005_panel=t005,
    )
    monkeypatch.setattr("marketlab.alpha_t011.MIN_FEATURE_SESSIONS", 1)
    monkeypatch.setattr("marketlab.alpha_t011.MIN_FEATURE_ROWS", 1)
    report = summarize_t011_source(panel)
    assert report["status"] == "READY_FOR_P1_SOURCE_FREEZE"
    assert report["return_labels_opened"] is False
    assert report["model_fit_performed"] is False


def test_t011_base_feature_count_is_27():
    assert len(BASE27_NAMES) == 27
