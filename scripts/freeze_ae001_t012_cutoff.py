from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_prospective_futures_sources import (
    validate_futures_source_ledger,
)
from marketlab.alpha_t012 import (
    freeze_t012_cutoff,
    validate_t012_cutoff_freeze,
)
from marketlab.alpha_trials import (
    append_trial_event,
    trial_state,
    validate_trial_ledger,
)


PROTOCOL_ID = "AE001-T012-P1"


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze AE001 T012 cutoff from source-only SC002 timing evidence"
    )
    parser.add_argument("--cutoff-freeze", type=Path, required=True)
    parser.add_argument("--timing-summary", type=Path, required=True)
    parser.add_argument("--trial-ledger", type=Path, required=True)
    parser.add_argument("--sc002-ledger", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    current = _load(args.cutoff_freeze)
    timing = _load(args.timing_summary)
    trials = _load(args.trial_ledger)
    sc002 = _load(args.sc002_ledger)
    validate_t012_cutoff_freeze(current)
    validate_trial_ledger(trials)
    validate_futures_source_ledger(sc002)

    summary_unsigned = dict(timing)
    summary_stored = str(summary_unsigned.pop("summary_sha256", ""))
    if summary_stored != digest(summary_unsigned):
        raise AlphaContractError("SC002 timing summary hash mismatch")
    if timing.get("source_ledger_sha256") != sc002.get("ledger_sha256"):
        raise AlphaContractError(
            "SC002 timing summary is stale relative to source ledger"
        )

    state = trial_state(trials, "AE001-T012")
    if state["registration"] is None:
        raise AlphaContractError("T012 is not registered before cutoff freeze")

    amendments = [
        event
        for event in state["amendments"]
        if event["payload"].get("protocol_id") == PROTOCOL_ID
    ]

    if current["state"] == "FROZEN":
        if len(amendments) != 1:
            raise AlphaContractError(
                "frozen T012 cutoff must have exactly one T012-P1 amendment"
            )
        payload = amendments[0]["payload"]
        if payload.get("cutoff_freeze_sha256") != current["freeze_sha256"]:
            raise AlphaContractError("T012-P1 cutoff hash mismatch")
        if payload.get("source_timing_summary_sha256") != current[
            "source_timing_summary_sha256"
        ]:
            raise AlphaContractError("T012-P1 timing summary hash mismatch")
        print(
            json.dumps(
                {
                    "state": "ALREADY_FROZEN",
                    "changed": False,
                    "cutoff_ist": current["cutoff_ist"],
                    "cutoff_session_offset_days": current[
                        "cutoff_session_offset_days"
                    ],
                    "latest_timing_basis_session": current[
                        "latest_timing_basis_session"
                    ],
                    "freeze_sha256": current["freeze_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0

    if amendments:
        raise AlphaContractError(
            "T012-P1 exists before cutoff artifact is frozen"
        )

    if timing.get("state") != "SOURCE_TIMING_READY_FOR_SUCCESSOR_DESIGN":
        print(
            json.dumps(
                {
                    "state": "WAITING_FOR_SC002_TIMING_EVIDENCE",
                    "changed": False,
                    "distinct_ready_session_count": timing.get(
                        "distinct_ready_session_count"
                    ),
                    "minimum_distinct_ready_sessions": timing.get(
                        "minimum_distinct_ready_sessions"
                    ),
                    "additional_distinct_ready_sessions_needed": timing.get(
                        "additional_distinct_ready_sessions_needed"
                    ),
                },
                sort_keys=True,
            )
        )
        return 0

    frozen_at = datetime.now(UTC).isoformat()
    updated_freeze = freeze_t012_cutoff(
        current,
        timing_summary=timing,
        frozen_at_utc=frozen_at,
    )
    amendment_payload = {
        "protocol_id": PROTOCOL_ID,
        "status": "CUTOFF_FROZEN_FROM_SOURCE_ONLY_TIMING_EVIDENCE",
        "frozen_protocol": (
            "research/AE001_T012_LATE_FUTURES_CONFIRMATION_V1.md"
        ),
        "cutoff_freeze_sha256": updated_freeze["freeze_sha256"],
        "source_timing_summary_sha256": updated_freeze[
            "source_timing_summary_sha256"
        ],
        "source_ledger_sha256": updated_freeze["source_ledger_sha256"],
        "timing_basis_sessions": updated_freeze["timing_basis_sessions"],
        "latest_timing_basis_session": updated_freeze[
            "latest_timing_basis_session"
        ],
        "cutoff_ist": updated_freeze["cutoff_ist"],
        "cutoff_session_offset_days": updated_freeze[
            "cutoff_session_offset_days"
        ],
        "cutoff_rule": (
            "LATEST_FIRST_READY_PLUS_30_MINUTES_ROUNDED_UP_TO_NEXT_15_MINUTES"
        ),
        "timing_basis_sessions_may_enter_trial": False,
        "alpha_or_return_outcomes_used_to_select_cutoff": False,
        "manual_override_allowed": False,
        "live_capital_allowed": False,
    }
    updated_trials = append_trial_event(
        trials,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T012",
        recorded_at_utc=frozen_at,
        payload=amendment_payload,
    )

    _write(args.cutoff_freeze, updated_freeze)
    _write(args.trial_ledger, updated_trials)
    print(
        json.dumps(
            {
                "state": "FROZEN",
                "changed": True,
                "cutoff_ist": updated_freeze["cutoff_ist"],
                "cutoff_session_offset_days": updated_freeze[
                    "cutoff_session_offset_days"
                ],
                "timing_basis_sessions": updated_freeze[
                    "timing_basis_sessions"
                ],
                "latest_timing_basis_session": updated_freeze[
                    "latest_timing_basis_session"
                ],
                "freeze_sha256": updated_freeze["freeze_sha256"],
                "protocol_event_sha256": updated_trials["events"][-1][
                    "event_sha256"
                ],
                "trial_ledger_sha256": updated_trials["ledger_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
