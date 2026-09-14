from __future__ import annotations

import pytest

from marketlab.h021_stockanalysis_acquisition import (
    CAPTURE,
    NO_SESSION,
    NOT_FINAL_SESSION,
    AnchorTarget,
    StructuralSourceDrift,
    finalize_capture,
    row_from_parser_error,
    source_blocked_row,
    success_row,
    weekly_session_decision,
)
from marketlab.h021_stockanalysis_parser import (
    ForecastIdentityError,
    ForecastLayoutError,
    ForecastTargetPeriodError,
    ParsedAnnualForecast,
    forecast_currency_from_html,
)


def _calendar() -> dict:
    return {
        "start_date": "2026-09-01",
        "end_date": "2026-10-31",
        "sessions": [
            {"session_date": "2026-09-11"},
            {"session_date": "2026-09-15"},
            {"session_date": "2026-09-16"},
            {"session_date": "2026-09-17"},
            {"session_date": "2026-09-18"},
            {"session_date": "2026-09-28"},
            {"session_date": "2026-09-29"},
            {"session_date": "2026-09-30"},
            {"session_date": "2026-10-01"},
            {"session_date": "2026-10-05"},
        ],
    }


def _target() -> AnchorTarget:
    return AnchorTarget(
        symbol="AAA",
        fiscal_period="FY2027",
        period_ending="2027-03-31",
        eps_currency="INR",
    )


def _draft_row() -> dict:
    return {
        "symbol": "AAA",
        "company_name": "Alpha Ltd.",
        "isin": "INE000000001",
        "series": "EQ",
        "constituent_industry": "Industrials",
        "universe_rank": 1,
        "batch_id": "B01",
        "data_state": "PENDING",
        "retrieval_notes": "",
        "fiscal_period": "",
        "period_ending": None,
        "consensus_eps": None,
        "eps_currency": None,
        "revenue_growth_forecast_pct": None,
        "profit_growth_estimate_pct": None,
        "analyst_count": None,
        "target_price_inr": None,
        "source_observed_market_date": None,
        "source_url": "",
        "source_status": "PENDING",
    }


def _parsed() -> ParsedAnnualForecast:
    return ParsedAnnualForecast(
        symbol="AAA",
        fiscal_period="FY2027",
        period_ending="2027-03-31",
        consensus_eps=12.5,
        eps_currency="INR",
        revenue_growth_forecast_pct=9.2,
        analyst_count=8,
        provider="S&P Global Market Intelligence",
        source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
        eps_currency_source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
    )


def test_weekly_session_gate_handles_holiday_and_final_session() -> None:
    assert weekly_session_decision("2026-09-14", _calendar()).state == NO_SESSION
    assert weekly_session_decision("2026-09-17", _calendar()).state == NOT_FINAL_SESSION
    assert weekly_session_decision("2026-09-18", _calendar()).state == CAPTURE


def test_weekly_session_gate_captures_thursday_before_friday_holiday() -> None:
    decision = weekly_session_decision("2026-10-01", _calendar())
    assert decision.state == CAPTURE
    assert decision.final_session_date == "2026-10-01"


def test_weekly_session_gate_fails_outside_frozen_calendar() -> None:
    with pytest.raises(ValueError, match="outside frozen calendar coverage"):
        weekly_session_decision("2026-11-02", _calendar())


def test_forecast_currency_helper_controls_financials_fallback() -> None:
    html = b"<html><body><p>Financial currency is INR.</p></body></html>"
    assert forecast_currency_from_html(html) == "INR"
    assert forecast_currency_from_html(b"<html><body>No currency</body></html>") is None


def test_success_row_is_partial_and_keeps_primary_fields_only() -> None:
    row = success_row(
        _draft_row(),
        target=_target(),
        parsed=_parsed(),
        source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
    )
    assert row["data_state"] == "PARTIAL"
    assert row["fiscal_period"] == "FY2027"
    assert row["period_ending"] == "2027-03-31"
    assert row["consensus_eps"] == pytest.approx(12.5)
    assert row["eps_currency"] == "INR"
    assert row["analyst_count"] == 8
    assert row["profit_growth_estimate_pct"] is None
    assert row["target_price_inr"] is None
    assert row["source_observed_market_date"] is None


def test_success_row_fails_closed_on_currency_change() -> None:
    parsed = _parsed()
    changed = ParsedAnnualForecast(**{**parsed.to_dict(), "eps_currency": "USD"})
    with pytest.raises(StructuralSourceDrift, match="EPS currency changed"):
        success_row(
            _draft_row(),
            target=_target(),
            parsed=changed,
            source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
        )


def test_expected_parser_failures_map_to_explicit_capture_states() -> None:
    identity = row_from_parser_error(
        _draft_row(),
        target=_target(),
        source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
        error=ForecastIdentityError("wrong page"),
    )
    assert identity["data_state"] == "IDENTITY_UNRESOLVED"
    assert identity["consensus_eps"] is None

    missing_period = row_from_parser_error(
        _draft_row(),
        target=_target(),
        source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
        error=ForecastTargetPeriodError("target absent"),
    )
    assert missing_period["data_state"] == "NO_COVERAGE"
    assert missing_period["period_ending"] is None


def test_structural_parser_drift_aborts_capture() -> None:
    with pytest.raises(StructuralSourceDrift, match="ForecastLayoutError"):
        row_from_parser_error(
            _draft_row(),
            target=_target(),
            source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
            error=ForecastLayoutError("table changed"),
        )


def test_source_blocked_row_never_carries_stale_values() -> None:
    draft = _draft_row()
    draft["consensus_eps"] = 99.0
    draft["analyst_count"] = 7
    row = source_blocked_row(
        draft,
        target=_target(),
        source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
        reason="HTTP 429",
    )
    assert row["data_state"] == "SOURCE_BLOCKED"
    assert row["consensus_eps"] is None
    assert row["analyst_count"] is None
    assert row["fiscal_period"] == "FY2027"


def test_finalize_capture_removes_draft_only_state() -> None:
    draft = {
        "draft_schema_version": 1,
        "draft_state": "ACQUISITION_INCOMPLETE",
        "captured_at_utc": None,
        "observations": [_draft_row()],
    }
    finalized = finalize_capture(
        draft,
        [_draft_row()],
        "2026-09-18T12:45:00+00:00",
    )
    assert "draft_schema_version" not in finalized
    assert "draft_state" not in finalized
    assert finalized["captured_at_utc"] == "2026-09-18T12:45:00+00:00"
