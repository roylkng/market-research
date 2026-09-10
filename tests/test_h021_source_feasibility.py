from __future__ import annotations

from scripts.run_h021_source_feasibility import parse_consensus_html


def test_parse_public_consensus_summary() -> None:
    html = """
    <html><body>
      <h1>Example - stock price prediction</h1>
      <p>Example has a share price target of Rs 100, revenue growth forecast of 18.1%,
      and profit growth estimate of 24.3% for FY27, based on top 9 analyst calls.</p>
      <h3>EPS forecast</h3>
      <div>Current EPS 20.5 Avg. Estimate 27.4 Low Estimate 24.0 High Estimate 31.2</div>
    </body></html>
    """
    parsed = parse_consensus_html(html)
    assert parsed.revenue_growth_forecast_pct == 18.1
    assert parsed.profit_growth_estimate_pct == 24.3
    assert parsed.analyst_count == 9
    assert parsed.current_eps == 20.5
    assert parsed.average_eps_estimate == 27.4
    assert parsed.low_eps_estimate == 24.0
    assert parsed.high_eps_estimate == 31.2
    assert not parsed.premium_marker
    assert not parsed.historical_point_in_time_eps_found


def test_current_30_day_revision_claim_is_not_historical_snapshot() -> None:
    html = """
    <html><body>
      Consensus EPS estimate has been revised 5.4% higher over the last 30 days.
      EPS forecast Current EPS 10 Avg. Estimate 12
    </body></html>
    """
    parsed = parse_consensus_html(html)
    assert parsed.average_eps_estimate == 12.0
    assert not parsed.historical_point_in_time_eps_found


def test_premium_marker_does_not_imply_historical_access() -> None:
    html = """
    <html><body>
      <h3>EPS forecast</h3>
      Current EPS 4.0 Avg. Estimate 6.0
      Forecaster is a Premium Feature. You need to upgrade your subscription plan.
    </body></html>
    """
    parsed = parse_consensus_html(html)
    assert parsed.premium_marker
    assert not parsed.historical_point_in_time_eps_found


def test_requires_dated_eps_consensus_pair_for_historical_marker() -> None:
    html = """
    <html><body>
      2026-06-30 EPS consensus estimate 18.4
      2026-07-31 EPS consensus estimate 19.1
    </body></html>
    """
    parsed = parse_consensus_html(html)
    assert parsed.historical_point_in_time_eps_found
