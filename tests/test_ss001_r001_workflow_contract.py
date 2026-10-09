from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "ss001-r001-manual-llm-shard.yml"
)


def _workflow() -> dict:
    parsed = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _steps() -> list[dict]:
    return _workflow()["jobs"]["evidence-bound-shard"]["steps"]


def test_hosted_llm_transport_is_manual_only_and_preflight_by_default() -> None:
    workflow = _workflow()
    # YAML 1.1 may parse the GitHub Actions 'on' key as boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    mode = triggers["workflow_dispatch"]["inputs"]["mode"]
    assert mode["default"] == "preflight"
    assert mode["options"] == ["preflight", "infer"]

    permissions = workflow["permissions"]
    assert permissions == {"contents": "read", "actions": "read"}


def test_hosted_llm_transport_has_manual_cost_budget() -> None:
    steps = _steps()
    setup = next(step for step in steps if step.get("name") == (
        "Validate manual dispatch and pin provider configuration"
    ))
    assert "if not 1 <= count <= 78:" in setup["run"]
    assert 'if mode == "infer" and not os.environ.get("MARKETLAB_LLM_API_KEY"):' in (
        setup["run"]
    )
    assert 'urlparse(endpoint).scheme != "https"' in setup["run"]

    inputs = _workflow().get("on", _workflow().get(True))[
        "workflow_dispatch"
    ]["inputs"]
    assert inputs["max_requests"]["default"] == "5"
    assert inputs["retry_failed"]["default"] is False


def test_model_calls_are_guarded_and_frozen_queue_is_pinned() -> None:
    steps = _steps()
    source = next(step for step in steps if step.get("name") == (
        "Download exact frozen 1,240-page queue"
    ))
    assert source["with"]["name"] == "ss001-d007-l001-p2-queue-37884584355"
    assert source["with"]["run-id"] == 37884584355

    inference = next(step for step in steps if step.get("name") == (
        "Execute explicitly authorized shard budget"
    ))
    assert "inputs.mode == 'infer'" in inference["if"]
    assert "--run-shard" in inference["run"]
    assert "--max-requests" in inference["run"]

    preflight = next(step for step in steps if step.get("name") == (
        "Verify frozen queue and existing receipts without model calls"
    ))
    assert "--dry-run" in preflight["run"]


def test_receipt_resumption_is_explicit_and_credentials_stay_in_secrets() -> None:
    steps = _steps()
    restore = next(step for step in steps if step.get("name") == (
        "Restore prior append-only receipts when explicitly supplied"
    ))
    assert "inputs.previous_run_id != ''" in restore["if"]
    assert "inputs.previous_run_id" in restore["with"]["name"]
    assert "inputs.previous_run_id" in str(restore["with"]["run-id"])

    env = _workflow()["jobs"]["evidence-bound-shard"]["env"]
    assert "secrets.MARKETLAB_LLM_API_KEY" in env["MARKETLAB_LLM_API_KEY"]
    assert "vars.SS001_R001_MODEL_ID" in env["R001_MODEL_ID"]
    assert "vars.SS001_R001_API_ENDPOINT" in env["R001_API_ENDPOINT"]
