"""Prevent H021 source-capture trigger regressions and bot feedback loops."""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/h021-daily-official-prices.yml")


def test_daily_source_capture_mergetrigger_is_narrow_and_safe() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    # BaseLoader avoids YAML-1.1 coercion of the literal 'on' key.
    config = yaml.load(raw, Loader=yaml.BaseLoader)
    assert config["name"] == "H021 daily official source path"
    events = config["on"]
    assert "workflow_dispatch" in events
    assert events["push"]["branches"] == ["main"]
    expected = {
        ".github/workflows/h021-daily-official-prices.yml",
        "src/marketlab/h021_daily_prices.py",
        "scripts/resolve_h021_daily_session.py",
        "scripts/collect_h021_daily_official.py",
        "tests/test_h021_daily_prices.py",
        "tests/test_h021_delayed_source_recovery.py",
    }
    assert set(events["push"]["paths"]) == expected
    assert len(events["schedule"]) >= 2
    assert config["permissions"]["contents"] == "write"
    # The GitHub bot's append-only original-market-source evidence must not
    # independently trigger the workflow again, causing a runaway loop.
    assert not any(
        item.startswith("research/") or "*" in item
        for item in events["push"]["paths"]
    )


def test_next_exchange_session_is_never_assumed_trade_or_return() -> None:
    source = Path("scripts/resolve_h021_daily_session.py").read_text(
        encoding="utf-8"
    )
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'FIRST_FUTURE_SESSION = "2026-10-13"' in source
    assert "if close > current:" in source
    assert 'if: steps.gate.outputs.state == \'CAPTURE\'' in workflow
    assert "official_market_transport_ready" in workflow
    assert "SOURCE_TRANSPORT_READY_WITH_FIRST_COHORT_GAP" in workflow
    assert "H021_RAW_OUTPUT" in workflow
    assert "git add -f" in workflow
