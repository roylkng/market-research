"""Prevent H021 source-capture trigger regressions and bot feedback loops."""

from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/h021-daily-official-prices.yml")


def test_daily_source_capture_mergetrigger_is_narrow_and_safe() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "name: H021 daily official source path" in raw
    assert "\non:\n  workflow_dispatch:\n  push:\n" in raw
    push = raw.split("\n  push:\n", 1)[1].split("\n  schedule:\n", 1)[0]
    assert "    branches:\n      - main\n" in push
    assert "    paths:\n" in push
    paths = {
        line.strip().removeprefix("- ").strip()
        for line in push.split("    paths:\n", 1)[1].splitlines()
        if line.lstrip().startswith("- ")
    }
    expected = {
        ".github/workflows/h021-daily-official-prices.yml",
        "src/marketlab/h021_daily_prices.py",
        "scripts/resolve_h021_daily_session.py",
        "scripts/collect_h021_daily_official.py",
        "tests/test_h021_daily_prices.py",
        "tests/test_h021_delayed_source_recovery.py",
        "tests/test_h021_daily_mergetrigger.py",
    }
    assert paths == expected
    assert "\n  schedule:\n" in raw
    assert "permissions:\n  contents: write" in raw
    # Commits of official source bytes must not retrigger collection.
    assert not any(path.startswith("research/") or "*" in path for path in paths)


def test_next_exchange_session_is_never_assumed_trade_or_return() -> None:
    source = Path("scripts/resolve_h021_daily_session.py").read_text(
        encoding="utf-8"
    )
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'FIRST_FUTURE_SESSION = "2026-10-13"' in source
    assert "if close > current:" in source
    assert "if: steps.gate.outputs.state == 'CAPTURE'" in workflow
    assert "official_market_transport_ready" in workflow
    assert "SOURCE_TRANSPORT_READY_WITH_FIRST_COHORT_GAP" in workflow
    assert "H021_RAW_OUTPUT" in workflow
    assert "git add -f" in workflow
