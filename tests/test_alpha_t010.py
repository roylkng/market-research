from dataclasses import asdict

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_d010_p4 import D010_DEFINITIONS
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_t010 import (
    AUGMENTED44_NAMES,
    BASE18_NAMES,
    BASE37_NAMES,
    D010_NAMES,
    build_t010_feature_panel,
    summarize_t010_source,
)


def _definitions(definitions):
    return [asdict(definition) for definition in definitions]


def _panel(*, names, definitions, panel_id, values):
    panel = {
        "schema_version": 1,
        "panel_id": panel_id,
        "feature_definitions": _definitions(definitions),
        "feature_set_sha256": digest(_definitions(definitions)),
        "session_count": 1,
        "feature_row_count": 1,
        "sessions": [
            {
                "session_date": "2026-09-25",
                "eligible_count": 1,
                "universe_sha256": "u" * 64,
            }
        ],
        "rows": [
            {
                "feature_session": "2026-09-25",
                "symbol": "TEST",
                "isin": "INE000000001",
                "universe_sha256": "u" * 64,
                "feature_set_sha256": "x" * 64,
                "values": {name: values.get(name) for name in names},
            }
        ],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _t005():
    definitions = [
        *PRICE_VOLUME_DEFINITIONS,
        *DELIVERY_DEFINITIONS,
        *FUTURES_DEFINITIONS,
    ]
    values = {
        name: float(index + 1) / 100.0
        for index, name in enumerate(BASE37_NAMES)
    }
    return _panel(
        names=BASE37_NAMES,
        definitions=definitions,
        panel_id="T005",
        values=values,
    )


def _d010():
    definitions = [*PRICE_VOLUME_DEFINITIONS, *D010_DEFINITIONS]
    values = {
        name: float(index + 1) / 100.0
        for index, name in enumerate(BASE18_NAMES)
    }
    values.update(
        {
            name: 0.2 + index / 100.0
            for index, name in enumerate(D010_NAMES)
        }
    )
    return _panel(
        names=[*BASE18_NAMES, *D010_NAMES],
        definitions=definitions,
        panel_id="D010",
        values=values,
    )


def test_t010_inner_join_builds_exact_44_feature_row(monkeypatch):
    t005 = _t005()
    d010 = _d010()
    monkeypatch.setattr(
        "marketlab.alpha_t010.EXPECTED_T005_PANEL_SHA256",
        t005["panel_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.alpha_t010.EXPECTED_D010_P4A_PANEL_SHA256",
        d010["panel_sha256"],
    )

    panel = build_t010_feature_panel(
        t005_feature_panel=t005,
        d010_feature_panel=d010,
    )
    assert panel["feature_row_count"] == 1
    assert panel["session_count"] == 1
    assert len(panel["feature_definitions"]) == 44
    assert set(panel["rows"][0]["values"]) == set(AUGMENTED44_NAMES)
    assert panel["max_overlapping_base_feature_abs_diff"] == pytest.approx(0.0)
    assert panel["outcomes_attached"] is False

    report = summarize_t010_source(panel)
    assert report["return_labels_opened"] is False
    assert report["model_fit_performed"] is False
    assert report["feature_count"] == 44


def test_t010_fails_closed_on_overlapping_base_feature_drift(monkeypatch):
    t005 = _t005()
    d010 = _d010()
    d010["rows"][0]["values"]["momentum_20"] += 1e-5
    unsigned = dict(d010)
    unsigned.pop("panel_sha256", None)
    d010["panel_sha256"] = digest(unsigned)

    monkeypatch.setattr(
        "marketlab.alpha_t010.EXPECTED_T005_PANEL_SHA256",
        t005["panel_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.alpha_t010.EXPECTED_D010_P4A_PANEL_SHA256",
        d010["panel_sha256"],
    )

    with pytest.raises(AlphaContractError, match="overlapping base feature differs"):
        build_t010_feature_panel(
            t005_feature_panel=t005,
            d010_feature_panel=d010,
        )


def test_t010_excludes_rows_missing_d010_common_identity(monkeypatch):
    t005 = _t005()
    d010 = _d010()
    d010["rows"] = []
    d010["feature_row_count"] = 0
    d010["sessions"] = []
    d010["session_count"] = 0
    unsigned = dict(d010)
    unsigned.pop("panel_sha256", None)
    d010["panel_sha256"] = digest(unsigned)

    monkeypatch.setattr(
        "marketlab.alpha_t010.EXPECTED_T005_PANEL_SHA256",
        t005["panel_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.alpha_t010.EXPECTED_D010_P4A_PANEL_SHA256",
        d010["panel_sha256"],
    )

    panel = build_t010_feature_panel(
        t005_feature_panel=t005,
        d010_feature_panel=d010,
    )
    assert panel["feature_row_count"] == 0
    assert panel["excluded_no_d010_row_count"] == 1
