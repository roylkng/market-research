"""Frozen H021-only first H20 source measurement and fail-closed guardrails."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTCOME = ROOT / "research/prospective/h021/outcomes/2026-10-09-h20-source-only-diagnostic-v1.json"
SCRIPT = ROOT / "scripts/evaluate_h021_h20_price_only.py"
COMPARISON = (
    ROOT / "research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json"
)


def test_h021_h20_source_only_report_reproduces_from_sealed_originals() -> None:
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--verify", str(OUTCOME)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "H021 H20 source-only artifact verified" in run.stdout


def test_h021_source_only_not_misrepresented_as_validated_returns() -> None:
    packet = json.loads(OUTCOME.read_text(encoding="utf-8"))
    primary = json.loads(COMPARISON.read_text(encoding="utf-8"))
    assert packet["hypothesis_id"] == "H021"
    assert packet["horizon_calendar_matured"] is True
    assert packet["horizon_completed_sessions"] == 20
    assert packet["horizon_exit_close_date_ist"] == "2026-11-08"
    assert packet["outcome_economic_status"] == "BLOCKED_NOT_PROMOTABLE"
    assert packet["primary_coverage"]["eligible_economic_returns"] == 0
    assert packet["frozen_cost_sensitivity"]["fixed_h021_roundtrip_cost_pp"] is None
    assert packet["sector_relative_excess"]["values"] is None
    assert packet["live_capital_allowed"] is False
    assert packet["h021_primary_selection_modified"] is False
    assert packet["h013_h019_h020_pf001_or_ensemble_used"] is False
    assert [x["symbol"] for x in packet["price_only_selected_stock_observations"]] == (
        primary["primary_top_decile_symbols"]
    )
    assert all(
        row["economic_return_verified"] is False
        for row in packet["price_only_selected_stock_observations"]
    )
