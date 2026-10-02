from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha_announcement_semantics import (
    EXPECTED_ANNOUNCEMENT_PANEL_SHA256,
    HASH_DIMENSIONS,
    SEMANTIC_DEFINITION_SHA256,
)
from marketlab.alpha_t012 import (
    D003_REPORT_SHA256,
    PRIMARY_FOLDS,
    PRIMARY_LAG,
    PROTOCOL_ID,
    RIDGE_L2,
    SECONDARY_FOLDS,
    SECONDARY_LAG,
    TRIAL_ID,
    TRIAL_STATUS,
)
from marketlab.alpha_trials import (
    append_trial_event,
    trial_state,
    validate_trial_ledger,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("T012 trial ledger must be a JSON object")
    validate_trial_ledger(payload)
    return payload


def _write(path: Path, payload: object) -> None:
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


def _folds(value) -> list[list[str]]:
    return [[start, end] for start, end in value]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register frozen AE001 T012 before outcome materialization"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger = _load(args.ledger)
    existing = [
        event
        for event in ledger["events"]
        if event["trial_id"] == TRIAL_ID
    ]
    if existing:
        state = trial_state(ledger, TRIAL_ID)
        print(
            json.dumps(
                {
                    "state": "ALREADY_REGISTERED",
                    "trial_id": TRIAL_ID,
                    "registration_event_sha256": state["registration"][
                        "event_sha256"
                    ],
                    "amendment_count": state["amendment_count"],
                    "result_count": state["result_count"],
                    "ledger_sha256": ledger["ledger_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0

    now = datetime.now(UTC).isoformat()
    registration_payload = {
        "status": TRIAL_STATUS,
        "name": "hashed_postclose_announcement_semantics",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "source_window": ["2025-09-01", "2026-09-25"],
        "base_feature_set": "CORE27",
        "new_feature_count": HASH_DIMENSIONS,
        "challenger_feature_set": "CORE91",
        "model": {"type": "ridge", "l2": RIDGE_L2},
        "primary": {
            "horizon_sessions": 1,
            "folds": _folds(PRIMARY_FOLDS),
            "newey_west_lag": PRIMARY_LAG,
        },
        "secondary": {
            "horizon_sessions": 5,
            "folds": _folds(SECONDARY_FOLDS),
            "newey_west_lag": SECONDARY_LAG,
            "rescues_primary": False,
        },
        "outcomes_for_t012_opened_before_registration": False,
        "live_capital_allowed": False,
    }
    ledger = append_trial_event(
        ledger,
        event_type="TRIAL_REGISTERED",
        trial_id=TRIAL_ID,
        recorded_at_utc=now,
        payload=registration_payload,
    )
    p1_payload = {
        "protocol_id": PROTOCOL_ID,
        "announcement_panel_sha256": EXPECTED_ANNOUNCEMENT_PANEL_SHA256,
        "d003_report_sha256": D003_REPORT_SHA256,
        "semantic_feature_definition_sha256": SEMANTIC_DEFINITION_SHA256,
        "semantic_hash_dimensions": HASH_DIMENSIONS,
        "same_day_postclose_window": "GT_15_30_AND_LTE_18_30_IST",
        "tokenization": "UNICODE_NFKC_LOWER_ASCII_ALNUM_UNIGRAM_BIGRAM",
        "distinct_ngrams_per_announcement": True,
        "per_announcement_l2_normalization": True,
        "session_aggregation": "SUM",
        "fitted_vocabulary": False,
        "llm_used": False,
        "sentiment_dictionary": False,
        "manual_direction_labels": False,
        "live_capital_allowed": False,
    }
    ledger = append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id=TRIAL_ID,
        recorded_at_utc=now,
        payload=p1_payload,
    )
    _write(args.ledger, ledger)
    validate_trial_ledger(ledger)
    state = trial_state(ledger, TRIAL_ID)
    print(
        json.dumps(
            {
                "state": "REGISTERED",
                "trial_id": TRIAL_ID,
                "registration_event_sha256": state["registration"][
                    "event_sha256"
                ],
                "protocol_event_sha256": state["amendments"][0][
                    "event_sha256"
                ],
                "ledger_sha256": ledger["ledger_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
