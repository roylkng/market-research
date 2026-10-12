"""H021 first-entry workflow smoke checks and no-retrospective-report invariants."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

PREFLIGHT = Path(".github/workflows/h021-original-market-source-preflight.yml")
ENTRY = Path(".github/workflows/h021-first-entry-observation.yml")


def _step(path: Path, name: str) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = config["jobs"]
    steps = next(iter(jobs.values()))["steps"]
    matches = [step for step in steps if step.get("name") == name]
    assert len(matches) == 1
    return matches[0]


def _valid_bash(script: str) -> None:
    subprocess.run(["bash", "-n"], input=script, text=True, check=True, capture_output=True)


def test_expired_preentry_preflight_has_no_future_cron() -> None:
    content = PREFLIGHT.read_text(encoding="utf-8")
    preamble = content.split("\njobs:", maxsplit=1)[0]
    assert "workflow_dispatch:" in preamble
    assert "schedule:" not in preamble
    assert "2026-10-12T03:45:00Z" in content
    assert "original-sources-format-ready-v1.json" in content


def test_postopen_noop_cannot_fail_due_to_blank_artifact_path() -> None:
    capture = _step(PREFLIGHT, "Rehearse actual frozen NSE stock ZIP and direct Nifty 500 index CSV")
    assert capture["if"] == "steps.gate.outputs.state == 'CAPTURE'"
    upload = _step(PREFLIGHT, "Preserve pre-entry source evidence only if actual pre-entry capture ran")
    assert upload["if"] == "always() && steps.gate.outputs.state == 'CAPTURE'"
    assert upload["with"]["path"] == "${{ env.PREFLIGHT_OUT }}"
    assert upload["with"]["if-no-files-found"] == "ignore"


def test_first_entry_occurs_only_after_completed_oct12_exchange_session() -> None:
    gate = _step(ENTRY, "Resolve immutable first entry gate")
    content = gate["run"]
    _valid_bash(content)
    assert "2026-10-12T10:00:00Z" in content
    assert "STATUS=CAPTURE" in content
    assert "ALREADY_CAPTURED" in content
    collector = _step(ENTRY, "Fetch original NSE UDiFF and Nifty 500 index data")
    assert collector["if"] == "steps.gate.outputs.status == 'CAPTURE'"
    assert "scripts/acquire_h021_first_entry.py" in collector["run"]
    _valid_bash(collector["run"])


def test_anchor_retries_unrelated_main_moves_but_never_relabels_sources() -> None:
    anchor = _step(ENTRY, "Anchor source receipts and immutable complete observation")
    content = anchor["run"]
    _valid_bash(content)
    assert "for RETRY in 1 2 3 4 5" in content
    assert 'REMOTE_SHA="$(git rev-parse origin/main)"' in content
    assert 'if [[ "$REMOTE_SHA" != "$BASE_SHA" ]]; then' in content
    assert "git rebase origin/main" in content
    assert 'BASE_SHA="$REMOTE_SHA"' in content
    assert "if git push origin HEAD:main; then" in content
    assert "sleep \"$((RETRY * 2))\"" in content
    assert '"origin/main:$TARGET"' in content
    assert "refusing overwrite" in content
    assert "source receipt retained in Actions artifact" in content
    for frozen_file in (
        "src/marketlab/h021_entry_observation.py",
        "src/marketlab/pf001_marketdata.py",
        "scripts/acquire_h021_first_entry.py",
        "research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json",
        "research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json",
        "research/prospective/universes/FY27-Q2-2026-09-06.json",
        "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json",
    ):
        assert frozen_file in content
    assert "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED" in content


def test_first_entry_has_nonempty_fixed_artifact_glob_even_on_capture_failure() -> None:
    upload = _step(ENTRY, "Retain independent evidence if push fails")
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == "/tmp/h021-first-entry-*"
    assert upload["with"]["if-no-files-found"] == "ignore"
