from __future__ import annotations

import json
from pathlib import Path

from marketlab.h021_stockanalysis_probe import (
    REQUIRED_TEXT_MARKERS,
    forecast_url,
    inspect_forecast_page,
    robots_allows,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "research/prospective/h021/stockanalysis-direct-probe-v1.json"


def test_forecast_url_encodes_special_nse_symbols() -> None:
    assert forecast_url("RELIANCE") == "https://stockanalysis.com/quote/nse/RELIANCE/forecast/"
    assert forecast_url("M&M") == "https://stockanalysis.com/quote/nse/M%26M/forecast/"


def test_robots_check_respects_disallowed_paths() -> None:
    robots = """User-agent: *
Disallow: /e/
Disallow: /p/
"""
    user_agent = "marketlab-h021-research/1.0"
    assert robots_allows(
        robots,
        user_agent,
        "https://stockanalysis.com/quote/nse/RELIANCE/forecast/",
    )
    assert not robots_allows(
        robots,
        user_agent,
        "https://stockanalysis.com/p/private-path",
    )


def test_inspector_requires_identity_and_frozen_markers() -> None:
    body = (
        "<html><body><h1>Reliance Industries Limited (NSE:RELIANCE)</h1>"
        "<h2>Financial Forecast</h2><p>EPS Forecast</p><p>Revenue Forecast</p>"
        "<p>No. Analysts</p><p>Data Source: S&P Global Market Intelligence</p>"
        "</body></html>"
    ).encode()
    result = inspect_forecast_page(
        symbol="RELIANCE",
        requested_url=forecast_url("RELIANCE"),
        status_code=200,
        final_url=forecast_url("RELIANCE"),
        content_type="text/html; charset=utf-8",
        body=body,
    )
    assert result["identity_verified"]
    assert all(result["required_marker_presence"].values())
    assert result["probe_pass"]

    wrong_identity = inspect_forecast_page(
        symbol="TCS",
        requested_url=forecast_url("TCS"),
        status_code=200,
        final_url=forecast_url("TCS"),
        content_type="text/html",
        body=body,
    )
    assert not wrong_identity["identity_verified"]
    assert not wrong_identity["probe_pass"]


def test_inspector_fails_on_missing_financial_marker() -> None:
    body = (
        "<html><body>NSE:RELIANCE Financial Forecast EPS Forecast Revenue Forecast "
        "No. Analysts</body></html>"
    ).encode()
    result = inspect_forecast_page(
        symbol="RELIANCE",
        requested_url=forecast_url("RELIANCE"),
        status_code=200,
        final_url=forecast_url("RELIANCE"),
        content_type="text/html",
        body=body,
    )
    assert not result["required_marker_presence"]["S&P Global Market Intelligence"]
    assert not result["probe_pass"]


def test_frozen_probe_config_contains_no_outcome_inputs() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert config["schema_version"] == 1
    assert config["hypothesis_id"] == "H021-DIRECT-SOURCE-PROBE"
    assert config["symbols"] == ["RELIANCE", "INFY", "TCS", "M&M", "NESTLEIND"]
    assert config["required_text_markers"] == list(REQUIRED_TEXT_MARKERS)
    assert config["outcomes_opened"] is False
    assert config["live_capital_allowed"] is False
    serialized = json.dumps(config).lower()
    for forbidden in ("stock_return", "nifty_return", "h013", "h019", "h020", "pf001"):
        assert forbidden not in serialized
