"""Independent H021 source-backstop must preserve scientific source clock."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from marketlab.calendar_snapshot import load_calendar_snapshot
from scripts.resolve_h021_daily_session import resolve_session

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / (
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)
PRIMARY = ROOT / ".github/workflows/h021-daily-official-prices.yml"
BACKSTOP = ROOT / ".github/workflows/h021-original-daily-source-backstop.yml"
ORIGINAL = ROOT / "research/prospective/h021/daily-prices"


def _yaml(path: Path) -> dict:
    # BaseLoader keeps the YAML v1.1 "on" key as a string.
    obj = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(obj, dict)
    return obj


def test_backup_uses_exact_same_repository_concurrency_as_original():
    primary = _yaml(PRIMARY)
    backup = _yaml(BACKSTOP)
    assert backup["name"] != primary["name"]
    assert backup["concurrency"]["group"] == primary["concurrency"]["group"]
    assert backup["concurrency"]["cancel-in-progress"] == "false"
    assert backup["permissions"] == {"contents": "write"}
    assert backup["on"]["workflow_dispatch"] == ""
    assert "main" in backup["on"]["push"]["branches"]
    assert ".github/workflows/h021-original-daily-source-backstop.yml" in (
        backup["on"]["push"]["paths"]
    )
    assert backup["on"]["workflow_run"]["workflows"] == [
        "AE001 SC001 prospective source timing"
    ]
    assert backup["on"]["workflow_run"]["types"] == ["completed"]
    assert backup["on"]["workflow_run"]["branches"] == ["main"]
    assert len(backup["on"]["schedule"]) >= 2


def test_collects_original_bytes_but_never_generates_return_labels():
    steps = _yaml(BACKSTOP)["jobs"]["backstop"]["steps"]
    all_run = "\n".join(step.get("run", "") for step in steps)
    assert "scripts/resolve_h021_daily_session.py" in all_run
    assert "--allow-delayed-publication-recovery" in all_run
    assert "scripts/collect_h021_daily_official.py" in all_run
    assert "--session-date" in all_run
    assert "steps.candidate.outputs.state == 'CAPTURE'" in str(steps)
    assert "sha256sum" in all_run
    assert "cmp --" in all_run
    assert "git rebase origin/main" in all_run
    assert "git push origin HEAD:main" in all_run
    assert "marketlab.h021_daily_prices import official_market_transport_ready" in all_run
    assert "SOURCE_NOT_READY_NO_DERIVED_STOCK_PRICES" in all_run
    assert "source stock returns" not in all_run
    assert "score_ae001" not in all_run
    assert " --force" not in all_run


def _fixture_copy_original_observations(tmp_path: Path) -> Path:
    dest = tmp_path / "daily-prices"
    dest.mkdir(parents=True)
    for date_text in (
        "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"
    ):
        path = ORIGINAL / f"{date_text}-v1.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        assert original["session_date_ist"] == date_text
        assert original["live_capital_allowed"] is False
        (dest / path.name).write_bytes(path.read_bytes())
    return dest


def test_independent_backstop_selects_original_missing_oct19_without_backdating(
    tmp_path: Path,
):
    calendar = load_calendar_snapshot(CALENDAR)
    source = _fixture_copy_original_observations(tmp_path)
    resolution = resolve_session(
        calendar,
        source,
        as_of_utc=datetime(2026, 10, 19, 17, 0, tzinfo=UTC),
        allow_delayed_publication_recovery=True,
    )
    assert resolution["state"] == "CAPTURE"
    assert resolution["session_date"] == "2026-10-19"
    assert resolution["capture_mode"] == "NORMAL_AFTER_COMPLETED_EXCHANGE_CLOSE"
    assert resolution["attempts_so_far"] == 0
    assert resolution["outcomes_opened"] is False
    assert resolution["live_capital_allowed"] is False
    assert resolution["previous_complete_sessions"] == 4


def test_never_fetch_before_market_close_or_invent_oct20_holiday(
    tmp_path: Path,
):
    calendar = load_calendar_snapshot(CALENDAR)
    source = _fixture_copy_original_observations(tmp_path)
    before = resolve_session(
        calendar,
        source,
        as_of_utc=datetime(2026, 10, 19, 9, 59, tzinfo=UTC),
    )
    assert before["state"] == "NO_COMPLETED_PENDING_SESSION"
    assert before["session_date"] is None
    assert "2026-10-20" not in {
        s.session_date for s in calendar.sessions
    }
    assert "2026-10-19" in {
        s.session_date for s in calendar.sessions
    }


@pytest.mark.parametrize(
    "offset",
    [
        datetime(2026, 10, 18, 17, 0, tzinfo=UTC),
        datetime(2026, 10, 19, 9, 59, tzinfo=UTC),
    ],
)
def test_source_clock_declines_prior_to_next_market_close(tmp_path: Path, offset):
    source = _fixture_copy_original_observations(tmp_path)
    result = resolve_session(
        load_calendar_snapshot(CALENDAR),
        source,
        as_of_utc=offset,
    )
    assert result["state"] == "NO_COMPLETED_PENDING_SESSION"
