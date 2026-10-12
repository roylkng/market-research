"""Safety contract: first H021 source capture can begin on merged contract only."""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/h021-first-entry-observation.yml")


def test_first_entry_one_time_push_trigger_cannot_expand_to_market_outcomes() -> None:
    workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert workflow["name"] == "H021 first official entry source observation"
    trigger = workflow["on"]
    assert trigger["workflow_dispatch"] is None or trigger["workflow_dispatch"] == ""
    assert trigger["push"]["branches"] == ["main"]
    assert trigger["push"]["paths"] == [
        ".github/workflows/h021-first-entry-observation.yml"
    ]
    assert trigger["schedule"] == [
        {"cron": "45 12 * * 1-5"},
        {"cron": "15 13 * * 1-5"},
        {"cron": "45 13 * * 1-5"},
    ]
    assert workflow["permissions"] == {"contents": "write"}
    steps = workflow["jobs"]["capture"]["steps"]
    script = "\n".join(step.get("run", "") for step in steps)
    assert 'CLOCK" > "2026-10-12T10:00:00Z"' in script
    assert 'TODAY" > "2026-10-11"' in script
    assert 'TODAY" < "2026-10-31"' in script
    assert "ALREADY_CAPTURED" in script
    assert "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED" in script
    assert "first-entry-v1.json" in script
    assert "scripts/acquire_h021_first_entry.py" in script
    assert "source attempt" in script
    assert "git cat-file -e" in script
    assert "git push origin HEAD:main" in script
