from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.po001_i006 import run_po001_i006


def _fixtures(session_count=70):
    start = date(2026, 1, 1)
    rg_rows = []
    # 60 calm prior sessions, then the OOS sessions.
    for index in range(60 + session_count):
        day = (start + timedelta(days=index)).isoformat()
        vol = 0.02 if index < 60 else (0.04 if index % 2 == 0 else 0.02)
        rg_rows.append(
            {
                "session_date": day,
                "known_at": f"{day}T18:00:00+05:30",
                "eligible_equity_count": 1000,
                "source_window_sha256": f"{index + 1:064x}",
                "values": {
                    "nifty500_realized_vol_20": vol,
                },
            }
        )
    rg = {
        "schema_version": 1,
        "panel_id": "AE001-RG001-v1",
        "rows": rg_rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    rg["panel_sha256"] = digest(rg)

    records = []
    for offset in range(session_count):
        index = 60 + offset
        day = rg_rows[index]["session_date"]
        # High-volatility sessions are deliberately adverse in this fixture.
        top_return = -0.03 if rg_rows[index]["values"]["nifty500_realized_vol_20"] > 0.03 else 0.02
        for stock_index in range(10):
            records.append(
                {
                    "alpha_id": "AB001-P003-FUTURES-DELTA",
                    "horizon_sessions": 5,
                    "feature_session": day,
                    "symbol": f"S{stock_index:02d}",
                    "isin": f"INE{stock_index:09d}",
                    "normalized_score": 1.0 - stock_index / 10.0,
                    "target_excess_return": (
                        top_return if stock_index == 0 else 0.0
                    ),
                }
            )
    library = {
        "records": records,
        "library_sha256": "library-hash",
    }
    p003 = {
        "report_sha256": "report-hash",
        "library": library,
    }
    return p003, rg


def test_i006_scales_only_active_notional_and_keeps_no_leverage(monkeypatch):
    p003, rg = _fixtures()
    monkeypatch.setattr(
        "marketlab.po001_i006.EXPECTED_P003_REPORT_SHA",
        "report-hash",
    )
    monkeypatch.setattr(
        "marketlab.po001_i006.EXPECTED_P003_LIBRARY_SHA",
        "library-hash",
    )
    monkeypatch.setattr(
        "marketlab.po001_i006.EXPECTED_RG001_PANEL_SHA",
        rg["panel_sha256"],
    )

    report = run_po001_i006(
        p003_report=p003,
        rg001_panel=rg,
    )
    assert report["eligible_session_count"] == 70
    assert report["exposure"]["minimum"] > 0
    assert report["exposure"]["minimum"] < 1
    assert report["exposure"]["median"] <= 1
    assert report["interpretation"]["stock_ranking_changed"] is False
    assert report["interpretation"]["alpha_refit_performed"] is False
    for row in report["observations"]:
        assert 0 < row["active_exposure_multiplier"] <= 1
        assert row["benchmark_sleeve_weight"] == pytest.approx(
            1.0 - row["active_exposure_multiplier"]
        )
        assert row["treatment_realized_5d_excess"] == pytest.approx(
            row["active_exposure_multiplier"]
            * row["control_realized_5d_excess"]
        )


def test_i006_uses_only_prior_60_regime_rows(monkeypatch):
    p003, rg = _fixtures(session_count=40)
    monkeypatch.setattr(
        "marketlab.po001_i006.EXPECTED_P003_REPORT_SHA",
        "report-hash",
    )
    monkeypatch.setattr(
        "marketlab.po001_i006.EXPECTED_P003_LIBRARY_SHA",
        "library-hash",
    )
    monkeypatch.setattr(
        "marketlab.po001_i006.EXPECTED_RG001_PANEL_SHA",
        rg["panel_sha256"],
    )

    # First eligible OOS session sees exactly the calm prior-60 median 0.02.
    report = run_po001_i006(
        p003_report=p003,
        rg001_panel=rg,
    )
    first = report["observations"][0]
    assert first["reference_prior60_median_vol20"] == pytest.approx(0.02)
    if first["current_vol20"] == pytest.approx(0.04):
        assert first["active_exposure_multiplier"] == pytest.approx(0.5)


def test_i006_requires_at_least_40_eligible_sessions(monkeypatch):
    p003, rg = _fixtures(session_count=20)
    monkeypatch.setattr(
        "marketlab.po001_i006.EXPECTED_P003_REPORT_SHA",
        "report-hash",
    )
    monkeypatch.setattr(
        "marketlab.po001_i006.EXPECTED_P003_LIBRARY_SHA",
        "library-hash",
    )
    monkeypatch.setattr(
        "marketlab.po001_i006.EXPECTED_RG001_PANEL_SHA",
        rg["panel_sha256"],
    )
    with pytest.raises(AlphaContractError, match="fewer than 40"):
        run_po001_i006(
            p003_report=p003,
            rg001_panel=rg,
        )
