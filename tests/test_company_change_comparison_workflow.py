from __future__ import annotations

from pathlib import Path

import yaml


def test_comparison_failure_cannot_skip_original_data_checkpoint():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/cc001-daily-operations.yml").read_text())
    steps = workflow["jobs"]["refresh-research-workspace"]["steps"]
    command = next(s["run"] for s in steps if s.get("name") == "Export research desk and checkpoint durable state")
    assert "if ! python -m marketlab.company_change_comparisons" in command
    assert 'export CC_COMPARISON_OK="$comparison_ok"' in command
    assert "'business_change_status': 'SUCCESS' if business else 'FAILED'" in command
    assert "'business_change_counts': business['counts'] if business else None" in command
    assert command.index("company_change_checkpoint save") < command.index('test "$comparison_ok" = true')
    assert command.index("push origin HEAD:refs/heads/cc001-state") < command.index('test "$comparison_ok" = true')
