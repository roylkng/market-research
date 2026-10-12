"""Safety contract: first H021 source capture can begin on merged contract only."""

from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/h021-first-entry-observation.yml")


def test_first_entry_one_time_push_trigger_cannot_expand_to_market_outcomes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert workflow.startswith("name: H021 first official entry source observation\n")
    trigger = workflow.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "  workflow_dispatch:\n" in trigger
    assert trigger.count("  push:\n") == 1
    assert (
        "  push:\n"
        "    branches:\n"
        "      - main\n"
        "    paths:\n"
        "      # Run once immediately after this reviewed capture-contract amendment\n"
        "      # reaches main; keep all other main updates from retriggering it.\n"
        "      - .github/workflows/h021-first-entry-observation.yml\n"
    ) in trigger
    assert trigger.count("    - cron:") == 3
    for expected in ("45 12 * * 1-5", "15 13 * * 1-5", "45 13 * * 1-5"):
        assert f"    - cron: '{expected}'" in trigger
    assert "permissions:\n  contents: write\n" in workflow
    script = workflow.split("\n    steps:", 1)[1]
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
