"""Verify H021 source replay reacts to original-source workflow completion only."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/h021-first-entry-source-replay.yml")


def _steps() -> list[dict]:
    config = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return config["jobs"]["replay"]["steps"]


def _step(title: str) -> dict:
    entries = [step for step in _steps() if step.get("name") == title]
    assert len(entries) == 1
    return entries[0]


def test_waits_for_original_real_complete_entry_packet() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_run:" in raw
    assert "H021 first official entry source observation" in raw
    assert "workflow_dispatch:" in raw
    assert "schedule:" in raw
    gate = _step("Resolve real first-source availability without fictitious OHLC")
    code = gate["run"]
    assert "WAITING_FOR_REAL_OFFICIAL_POST_CLOSE_SOURCES" in code
    assert "ALREADY_REPLAYED" in code
    assert "origin/main:$FIRST" in code
    assert "origin/main:$OUT" in code
    subprocess.run(
        ["bash", "-n"], input=code, text=True, check=True, capture_output=True
    )


def test_replay_never_anchors_without_original_source_bytes() -> None:
    verify = _step("Recheck stored original exchange bytes independently of summary")
    assert verify["if"] == "steps.gate.outputs.status == 'REPLAY'"
    assert "scripts/replay_h021_first_official_entry.py" in verify["run"]
    assert "validate_first_h021_replay" in verify["run"]
    assert "p['selected_stock_source_count']==10" in verify["run"]
    assert "p['expected_returns_calculated'] is False" in verify["run"]
    subprocess.run(
        ["bash", "-n"], input=verify["run"], text=True, check=True, capture_output=True
    )


def test_original_entry_remains_immutable_when_git_main_moves() -> None:
    stage = _step("Anchor exact original-source replay once without mutating first capture")
    script = stage["run"]
    assert stage["if"] == "steps.gate.outputs.status == 'REPLAY'"
    assert "for RETRY in 1 2 3 4 5" in script
    assert "git diff --quiet" in script
    assert "git rebase origin/main" in script
    assert "if git push origin HEAD:main; then" in script
    assert "2026-10-12-first-entry-v1.json" in script
    assert "entry-observations/raw/sha256" in script
    assert "first-entry-intent-v1.json" not in script  # use exact frozen path below
    assert "2026-10-09-primary-entry-intent-v1.json" in script
    assert "if git cat-file -e" in script
    subprocess.run(
        ["bash", "-n"], input=script, text=True, check=True, capture_output=True
    )


def test_artifact_path_never_missing_on_skipped_pre_source_replay() -> None:
    artifact = _step("Retain original replay evidence if Git anchoring fails")
    assert artifact["if"] == "always() && steps.gate.outputs.status == 'REPLAY'"
    assert artifact["with"]["path"] == "/tmp/h021-first-raw-source-replay-v1.json"
    assert artifact["with"]["if-no-files-found"] == "ignore"
