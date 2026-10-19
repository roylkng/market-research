"""HG009 P002 must follow both primary and independent original H021 sources."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_daily_prices import official_market_transport_ready
from scripts.materialize_hg009_daily import _next_available_source

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hg009-p002-daily.yml"
ORIGINAL_ROOT = ROOT / "research/prospective/h021/daily-prices"
DERIVED_ROOT = ROOT / "research/hg009/daily"
CALENDAR = ROOT / (
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)


def test_shared_original_source_trigger_admits_both_independent_primaries() -> None:
    flow = yaml.load(
        WORKFLOW.read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    triggers = flow["on"]["workflow_run"]
    assert triggers["workflows"] == [
        "H021 daily official source path",
        "H021 independent NSE original daily source backstop",
    ]
    assert triggers["types"] == ["completed"]
    assert triggers["branches"] == ["main"]
    assert "research/prospective/h021/daily-prices/**" in (
        flow["on"]["push"]["paths"]
    )
    assert "github.event.workflow_run.conclusion == 'success'" in (
        flow["jobs"]["derive"]["if"]
    )
    assert flow["concurrency"]["cancel-in-progress"] == "false"


def test_oct19_recovery_remains_original_nse_source_not_a_trade(tmp_path: Path):
    original = json.loads(
        (ORIGINAL_ROOT / "2026-10-19-v1.json").read_text(encoding="utf-8")
    )
    assert official_market_transport_ready(original)
    assert original["session_date_ist"] == "2026-10-19"
    assert original["stock_source"]["status"] == "OK"
    assert original["index_source"]["status"] == "OK"
    assert original["horizon_return_calculated"] is False
    assert original["trades_filled"] is False
    assert original["live_capital_allowed"] is False

    # Independent test fixtures do not depend on whether a future
    # daily-derived October 19 packet has been committed after the test.
    backstop_originals = tmp_path / "research/prospective/h021/daily-prices"
    backstop_originals.mkdir(parents=True)
    src = ORIGINAL_ROOT / "2026-10-19-v1.json"
    (backstop_originals / src.name).write_bytes(src.read_bytes())
    observations = Path("research/hg009/daily")
    derived = tmp_path / observations
    derived.mkdir(parents=True)
    for day in ("2026-10-15", "2026-10-16"):
        item = DERIVED_ROOT / f"{day}-v1.json"
        (derived / item.name).write_bytes(item.read_bytes())
    day, missed = _next_available_source(
        root=tmp_path,
        now=datetime(2026, 10, 19, 18, 8, tzinfo=UTC),
        calendar=load_calendar_snapshot(CALENDAR),
        observations=observations,
    )
    assert day == "2026-10-19"
    assert missed == []
