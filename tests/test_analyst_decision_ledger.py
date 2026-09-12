from __future__ import annotations

import json
from pathlib import Path

from marketlab.analyst import validate_decision


def test_all_sealed_analyst_decisions_are_valid() -> None:
    root = Path("research/analyst-decisions/v1")
    decision_files = sorted(root.glob("*.json"))
    assert decision_files, "expected at least one sealed analyst decision"

    seen_ids: set[str] = set()
    for path in decision_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), f"{path} must contain a JSON object"
        errors = validate_decision(payload)
        assert errors == [], f"{path}: {errors}"

        decision_id = str(payload["decision_id"])
        assert path.stem == decision_id, f"{path} filename must equal decision_id"
        assert decision_id not in seen_ids, f"duplicate decision_id: {decision_id}"
        seen_ids.add(decision_id)
