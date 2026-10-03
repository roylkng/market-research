from marketlab.alpha import digest
from marketlab.research_radar import (
    build_research_priority_radar,
    render_radar_markdown,
)


def _universe():
    industries = [f"Industry {index}" for index in range(10)]
    members = []
    for index in range(100):
        symbol = f"S{index:03d}"
        members.append(
            {
                "symbol": symbol,
                "isin": f"INE{index:09d}",
                "company_name": f"Company {index}",
                "constituent_industry": industries[index % len(industries)],
                "ffmc": float(1000 - index),
                "rank": index + 1,
                "series": "EQ",
                "source_rank": index + 1,
            }
        )
    payload = {
        "schema_version": 1,
        "cohort_id": "FY27-Q2-2026-09-06",
        "selection_size": 100,
        "members": members,
    }
    payload["sha256"] = digest(payload)
    return payload


def _consensus():
    observations = []
    for index in range(100):
        observations.append(
            {
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
                "consensus_eps": 10.0,
                "revenue_growth_forecast_pct": float(index),
                "profit_growth_estimate_pct": float(index) / 2.0,
                "analyst_count": 8,
                "target_price_inr": 250.0 + index,
                "data_state": "OBSERVED",
            }
        )
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "logical_capture_id": "2026-09-25-full-u001-v1",
        "capture_date_ist": "2026-09-25",
        "source_version": "H021-public-stockanalysis-spgi-plus-trendlyne-secondary-v1",
        "universe_git_blob_sha": "8026e81faee3e913d2fba1dba72d60603b69fa07",
        "observations": observations,
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }


def _market():
    sessions = []
    for day in range(61):
        equities = []
        for index in range(100):
            base = 100.0 + index
            close = base * (1.0 + 0.001 * day * (index + 1) / 100.0)
            equities.append(
                {
                    "symbol": f"S{index:03d}",
                    "isin": f"INE{index:09d}",
                    "open_price": close * 0.995,
                    "high_price": close * 1.01,
                    "low_price": close * 0.99,
                    "close_price": close,
                    "previous_close": close * 0.999,
                    "volume": 1_000_000 + index,
                    "turnover_inr": (1_000_000 + index) * close * (1 + day / 100),
                    "trade_count": 1000 + index,
                }
            )
        sessions.append(
            {
                "session_date": f"2026-{7 + day // 30:02d}-{1 + day % 30:02d}",
                "equities": equities,
                "benchmark": {
                    "close_price": 1000.0 * (1.0 + 0.0002 * day),
                },
            }
        )
    sessions = sorted(sessions, key=lambda row: row["session_date"])
    # Replace synthetic dates with strictly valid/canonical session-like dates.
    from datetime import date, timedelta

    start = date(2026, 8, 1)
    for index, session in enumerate(sessions):
        session["session_date"] = (start + timedelta(days=index)).isoformat()
    panel = {"sessions": sessions, "panel_id": "TEST"}
    panel["panel_sha256"] = digest(panel)
    return panel


def test_rr001_builds_three_non_outcome_research_queues():
    radar = build_research_priority_radar(
        universe=_universe(),
        consensus_snapshot=_consensus(),
        market_panel=_market(),
        consensus_payload_sha256="a" * 64,
    )
    assert radar["classification"] == "RESEARCH_PRIORITY_ONLY_NO_EXPECTED_RETURN"
    assert radar["universe_member_count"] == 100
    assert radar["outcomes_opened"] is False
    assert radar["portfolio_eligibility_allowed"] is False
    assert radar["live_capital_allowed"] is False
    assert len(radar["shortlists"]["short"]) == 15
    assert len(radar["shortlists"]["mid"]) == 15
    assert len(radar["shortlists"]["long"]) == 15
    assert len(radar["radar_sha256"]) == 64


def test_rr001_missing_consensus_is_not_imputed_or_promoted():
    consensus = _consensus()
    consensus["observations"][99]["analyst_count"] = 3
    consensus["observations"][99]["revenue_growth_forecast_pct"] = 999.0
    radar = build_research_priority_radar(
        universe=_universe(),
        consensus_snapshot=consensus,
        market_panel=_market(),
        consensus_payload_sha256="a" * 64,
    )
    row = next(
        item for item in radar["company_records"] if item["symbol"] == "S099"
    )
    assert row["consensus_primary_reliable"] is False
    assert row["revenue_growth_forecast_pct"] is None
    assert row["profit_growth_estimate_pct"] is None
    assert row["consensus_target_upside"] is None


def test_rr001_sector_balancing_caps_each_industry_at_two():
    radar = build_research_priority_radar(
        universe=_universe(),
        consensus_snapshot=_consensus(),
        market_panel=_market(),
        consensus_payload_sha256="a" * 64,
    )
    for horizon in ("short", "mid", "long"):
        counts = {}
        for row in radar["shortlists"][horizon]:
            counts[row["industry"]] = counts.get(row["industry"], 0) + 1
        assert max(counts.values()) <= 2


def test_rr001_markdown_states_research_only_boundary():
    radar = build_research_priority_radar(
        universe=_universe(),
        consensus_snapshot=_consensus(),
        market_panel=_market(),
        consensus_payload_sha256="a" * 64,
    )
    rendered = render_radar_markdown(radar)
    assert "not a return forecast" in rendered
    assert "Short-horizon research queue" in rendered
    assert "Mid-horizon research queue" in rendered
    assert "Long-horizon research queue" in rendered
