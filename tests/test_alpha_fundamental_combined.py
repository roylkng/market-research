import copy

import pytest

from marketlab.alpha import AlphaContractError, digest
import marketlab.alpha_fundamental_combined as combined


FEATURES = {
    "revenue_yoy": 0.1,
    "pbt_change_to_prior_revenue": 0.01,
    "total_profit_change_to_prior_revenue": 0.01,
    "pbt_margin": 0.12,
    "pbt_margin_delta_yoy": 0.01,
    "total_profit_margin_delta_yoy": 0.01,
}


def _record(symbol, target, baseline, diagnostic):
    row = {
        "schema_version": 1,
        "diagnostic_id": diagnostic,
        "symbol": symbol,
        "target_period_end": target,
        "baseline_period_end": baseline,
        "accounting_basis": "Consolidated",
        "target_exchange_published_at_utc": "2026-01-01T00:00:00Z",
        "baseline_exchange_published_at_utc": "2025-01-01T00:00:00Z",
        "target_source_url": "https://x/target.xml",
        "baseline_source_url": "https://x/base.xml",
        "target_discovery_row_sha256": "a" * 64,
        "baseline_discovery_row_sha256": "b" * 64,
        "discovery_raw_sha256": "c" * 64,
        "target_raw_sha256": "d" * 64,
        "baseline_raw_sha256": "e" * 64,
        "target_parser_version": "indas-xbrl-2025-v1",
        "baseline_parser_version": "indas-xbrl-2025-v1",
        "target_currency": "INR",
        "baseline_currency": "INR",
        "target_rounding": "Actuals",
        "baseline_rounding": "Actuals",
        "features": dict(FEATURES),
        "complete_feature_count": 6,
        "all_six_features_complete": True,
        "exceptional_items_to_revenue_diagnostic": None,
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    row["record_sha256"] = digest(row)
    return row


def _panel(diagnostic, records):
    panel = {
        "schema_version": 1,
        "diagnostic_id": diagnostic,
        "universe_sha256": combined.EXPECTED_UNIVERSE_SHA,
        "records": records,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _patch_sources(monkeypatch, d002, d003):
    monkeypatch.setattr(combined, "D002_PANEL_SHA", d002["panel_sha256"])
    monkeypatch.setattr(combined, "D003_PANEL_SHA", d003["panel_sha256"])
    monkeypatch.setattr(
        combined,
        "PERIOD_SOURCE",
        {
            "2025-09-30": {
                "diagnostic_id": "AE001-T008-D003-v1",
                "panel_sha256": d003["panel_sha256"],
                "run_id": 3,
                "artifact_id": 30,
            },
            "2025-12-31": {
                "diagnostic_id": "AE001-T008-D003-v1",
                "panel_sha256": d003["panel_sha256"],
                "run_id": 3,
                "artifact_id": 30,
            },
            "2026-03-31": {
                "diagnostic_id": "AE001-T008-D002-v1",
                "panel_sha256": d002["panel_sha256"],
                "run_id": 2,
                "artifact_id": 20,
            },
            "2026-06-30": {
                "diagnostic_id": "AE001-T008-D002-v1",
                "panel_sha256": d002["panel_sha256"],
                "run_id": 2,
                "artifact_id": 20,
            },
        },
    )


def test_combiner_uses_frozen_period_ownership_and_complete_rows(monkeypatch):
    d002 = _panel(
        "AE001-T008-D002-v1",
        [
            _record("C", "2026-03-31", "2025-03-31", "AE001-T008-D002-v1"),
            _record("D", "2026-06-30", "2025-06-30", "AE001-T008-D002-v1"),
        ],
    )
    d003 = _panel(
        "AE001-T008-D003-v1",
        [
            _record("A", "2025-09-30", "2024-09-30", "AE001-T008-D003-v1"),
            _record("B", "2025-12-31", "2024-12-31", "AE001-T008-D003-v1"),
        ],
    )
    _patch_sources(monkeypatch, d002, d003)
    monkeypatch.setattr(combined, "MIN_COMPLETE_PER_PERIOD", 1)
    monkeypatch.setattr(combined, "MIN_TOTAL_COMPLETE", 4)

    panel = combined.combine_t008_source_panels(
        d002_panel=d002,
        d003_panel=d003,
    )
    assert panel["record_count"] == 4
    assert panel["feasibility_pass"] is True
    assert {
        row["target_period_end"]: row["source_diagnostic_id"]
        for row in panel["records"]
    } == {
        "2025-09-30": "AE001-T008-D003-v1",
        "2025-12-31": "AE001-T008-D003-v1",
        "2026-03-31": "AE001-T008-D002-v1",
        "2026-06-30": "AE001-T008-D002-v1",
    }
    assert all(row["diagnostic_id"] == combined.D004_ID for row in panel["records"])


def test_combiner_rejects_tampered_source_record(monkeypatch):
    d002 = _panel(
        "AE001-T008-D002-v1",
        [_record("C", "2026-03-31", "2025-03-31", "AE001-T008-D002-v1")],
    )
    d003 = _panel(
        "AE001-T008-D003-v1",
        [_record("A", "2025-09-30", "2024-09-30", "AE001-T008-D003-v1")],
    )
    _patch_sources(monkeypatch, d002, d003)
    tampered = copy.deepcopy(d003)
    tampered["records"][0]["features"]["revenue_yoy"] = 0.99
    unsigned = dict(tampered)
    unsigned.pop("panel_sha256", None)
    tampered["panel_sha256"] = digest(unsigned)
    monkeypatch.setattr(combined, "D003_PANEL_SHA", tampered["panel_sha256"])
    patched = copy.deepcopy(combined.PERIOD_SOURCE)
    for spec in patched.values():
        if spec["diagnostic_id"] == "AE001-T008-D003-v1":
            spec["panel_sha256"] = tampered["panel_sha256"]
    monkeypatch.setattr(combined, "PERIOD_SOURCE", patched)

    with pytest.raises(AlphaContractError, match="source record hash mismatch"):
        combined.combine_t008_source_panels(
            d002_panel=d002,
            d003_panel=tampered,
        )


def test_combiner_rejects_return_opened_source_panel(monkeypatch):
    d002 = _panel("AE001-T008-D002-v1", [])
    d003 = _panel("AE001-T008-D003-v1", [])
    d002["return_outcomes_opened"] = True
    unsigned = dict(d002)
    unsigned.pop("panel_sha256", None)
    d002["panel_sha256"] = digest(unsigned)
    _patch_sources(monkeypatch, d002, d003)

    with pytest.raises(AlphaContractError, match="contains return outcomes"):
        combined.combine_t008_source_panels(
            d002_panel=d002,
            d003_panel=d003,
        )
