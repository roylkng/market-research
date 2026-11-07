from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_daily_paths_are_initialized_on_runner_not_in_job_env():
    workflow = yaml.safe_load((ROOT / ".github/workflows/cc001-daily-operations.yml").read_text())
    job = workflow["jobs"]["refresh-research-workspace"]
    assert "runner." not in str(job.get("env", {}))
    init = next(s for s in job["steps"] if s.get("name") == "Initialize runner workspace paths")
    assert "$RUNNER_TEMP" in init["run"]
    assert "$GITHUB_ENV" in init["run"]
    assert "CC_WORKSPACE=" in init["run"]
    assert "CC_STATE=" in init["run"]
    assert job["steps"].index(init) < next(i for i, s in enumerate(job["steps"]) if s.get("id") == "state")
