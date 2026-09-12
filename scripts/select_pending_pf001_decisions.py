from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from marketlab.analyst import validate_decision
from marketlab.paperfund_state import validate_fund_state

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _decision_date_ist(decision: dict) -> str:
    parsed = datetime.fromisoformat(str(decision["decision_timestamp"]))
    if parsed.tzinfo is None:
        raise ValueError("decision_timestamp must be offset-aware")
    return parsed.astimezone(INDIA_TZ).date().isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select sealed, unconsumed PF001 decisions executable before a session"
    )
    parser.add_argument("--state", required=True)
    parser.add_argument("--decision-dir", required=True)
    parser.add_argument("--session-date", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    state_payload = _load_json(Path(args.state))
    if not isinstance(state_payload, dict):
        raise TypeError("fund state must be an object")
    state_errors = validate_fund_state(state_payload)
    if state_errors:
        raise ValueError({"fund_state_errors": state_errors})

    consumed = {
        str(event["decision_id"])
        for event in state_payload["events"]
        if isinstance(event, dict) and isinstance(event.get("decision_id"), str)
    }
    book = str(state_payload["book"])
    selected: list[dict] = []
    decision_dir = Path(args.decision_dir)
    for path in sorted(decision_dir.rglob("*.json")):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            raise TypeError(f"decision file must contain an object: {path}")
        errors = validate_decision(payload)
        if errors:
            raise ValueError({"path": str(path), "decision_errors": errors})
        decision_id = str(payload["decision_id"])
        if decision_id in consumed:
            continue
        if payload["validation_role"] != book:
            continue
        if payload["analyst_action"] != "PORTFOLIO_ELIGIBLE":
            continue
        if _decision_date_ist(payload) >= args.session_date:
            continue
        selected.append(payload)

    selected.sort(key=lambda row: (row["decision_timestamp"], row["symbol"]))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(selected, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
