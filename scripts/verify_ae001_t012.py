from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_t012 import (
    validate_t012_cutoff_freeze,
    validate_t012_decision_ledger,
)
from marketlab.alpha_trials import trial_state, validate_trial_ledger


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify AE001 T012 cutoff, trial and decision state"
    )
    parser.add_argument("--cutoff-freeze", type=Path, required=True)
    parser.add_argument("--decision-ledger", type=Path, required=True)
    parser.add_argument("--trial-ledger", type=Path, required=True)
    args = parser.parse_args()

    cutoff = _load(args.cutoff_freeze)
    decisions = _load(args.decision_ledger)
    trials = _load(args.trial_ledger)
    validate_t012_cutoff_freeze(cutoff)
    validate_t012_decision_ledger(decisions)
    validate_trial_ledger(trials)
    state = trial_state(trials, "AE001-T012")
    if state["registration"] is None:
        raise SystemExit("T012 registration is missing")

    amendments = [
        event
        for event in state["amendments"]
        if event["payload"].get("protocol_id") == "AE001-T012-P1"
    ]
    if cutoff["state"] == "FROZEN":
        if len(amendments) != 1:
            raise SystemExit("frozen T012 cutoff lacks exact P1 amendment")
        if amendments[0]["payload"].get(
            "cutoff_freeze_sha256"
        ) != cutoff["freeze_sha256"]:
            raise SystemExit("T012 P1/cutoff hash mismatch")
    elif amendments:
        raise SystemExit("waiting T012 cutoff unexpectedly has P1")

    for row in decisions["decisions"]:
        path = Path(str(row["artifact_path"]))
        if not path.exists():
            raise SystemExit(f"missing T012 decision artifact: {path}")
        artifact = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        stored = str(artifact.get("artifact_sha256") or "")
        unsigned = dict(artifact)
        unsigned.pop("artifact_sha256", None)
        if stored != digest(unsigned):
            raise SystemExit(f"T012 artifact hash mismatch: {path}")
        if stored != row["artifact_sha256"]:
            raise SystemExit(f"T012 ledger/artifact mismatch: {path}")
        if artifact.get("cutoff_freeze_sha256") != cutoff["freeze_sha256"]:
            raise SystemExit(f"T012 decision uses different cutoff: {path}")
        if artifact.get("outcomes_attached") is not False:
            raise SystemExit(f"T012 decision contains outcomes: {path}")

    print(
        json.dumps(
            {
                "cutoff_state": cutoff["state"],
                "cutoff_ist": cutoff["cutoff_ist"],
                "cutoff_session_offset_days": cutoff[
                    "cutoff_session_offset_days"
                ],
                "latest_timing_basis_session": cutoff[
                    "latest_timing_basis_session"
                ],
                "decision_count": decisions["decision_count"],
                "decision_ledger_sha256": decisions["ledger_sha256"],
                "trial_ledger_sha256": trials["ledger_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
