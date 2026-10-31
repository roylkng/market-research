"""Regression gate: asynchronous downstream packets cannot invalidate H021 acquisition.

Only frozen H021 inputs and immutable capture/comparison histories belong in
the source-drift guard. Generated future-cohort/source packets and other
downstream materializations are not acquisition-rule changes.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/h021-weekly-consensus-capture.yml"


def _critical_path_blocks() -> list[list[str]]:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    sections = re.findall(
        r"CRITICAL_PATHS=\(\s*\n(.*?)^\s*\)",
        workflow,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert len(sections) == 2, "both pre-anchor and retry guards must be protected"
    return [re.findall(r'^\s*"([^"]+)"\s*$', block, flags=re.MULTILINE) for block in sections]


def test_h021_guard_excludes_generated_future_cohort_packets() -> None:
    blocks = _critical_path_blocks()
    forbidden_broad_paths = {
        "research/prospective/h021",
        "research/prospective/ae001-h021",
        "research/prospective/dr001-h021",
    }
    required = {
        ".github/workflows/h021-weekly-consensus-capture.yml",
        "research/H021_PROSPECTIVE_PROTOCOL_V1.md",
        "research/H021_COMPARISON_CONTRACT_V1.md",
        "research/H021_WEEKLY_ACQUISITION_CONTRACT_V1.md",
        "research/prospective/h021/capture-batches-v1.json",
        "research/prospective/h021/weekly-acquisition-v1.json",
        "research/prospective/h021/captures",
        "research/prospective/h021/comparisons",
        "research/prospective/universes/FY27-Q2-2026-09-06.json",
        "scripts/acquire_h021_weekly_capture.py",
        "scripts/seal_h021_capture.py",
        "scripts/compare_h021_captures.py",
    }
    for paths in blocks:
        assert not (set(paths) & forbidden_broad_paths)
        assert required <= set(paths)


def test_git_diff_pathspec_ignores_generated_future_packets_but_detects_rule_drift(tmp_path: Path) -> None:
    paths = _critical_path_blocks()[0]
    assert paths == _critical_path_blocks()[1]

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=tmp_path, check=True,
            capture_output=True, text=True,
        )
        return result.stdout.strip()

    def save(path: str, value: str) -> None:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")

    git("init", "-q")
    git("config", "user.name", "H021 regression")
    git("config", "user.email", "test-h021@invalid.example")
    packet = "research/prospective/h021/future-cohorts/source-packets/2026-10-16/2026-10-30-v1.json"
    config = "research/prospective/h021/capture-batches-v1.json"
    save(packet, "{}")
    save(config, "{}")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")

    save(packet, '{"new_packet": true}')
    git("add", ".")
    git("commit", "-qm", "unrelated downstream packet")
    assert git("diff", "--name-only", base, "HEAD", "--", *paths) == ""

    save(config, '{"changed": true}')
    git("add", ".")
    git("commit", "-qm", "frozen batch drift")
    assert git("diff", "--name-only", base, "HEAD", "--", *paths) == config
