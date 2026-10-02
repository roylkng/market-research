from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_history import load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_industry_capture import (
    industry_readiness_summary,
    validate_industry_source_ledger,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify RM001-SC002 industry capture evidence"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    validate_industry_source_ledger(ledger)

    observed_summary = json.loads(
        args.summary.read_text(encoding="utf-8")
    )
    expected_summary = industry_readiness_summary(ledger)
    if observed_summary != expected_summary:
        raise SystemExit(
            "RM001-SC002 readiness summary differs from canonical ledger"
        )
    unsigned_summary = dict(observed_summary)
    stored_summary = unsigned_summary.pop("summary_sha256")
    if stored_summary != digest(unsigned_summary):
        raise SystemExit("RM001-SC002 readiness summary hash mismatch")

    for attempt in ledger["attempts"]:
        for path_field, sha_field in (
            ("constituent_raw_path", "constituent_raw_sha256"),
            ("security_raw_path", "security_raw_sha256"),
        ):
            path_text = attempt.get(path_field)
            expected_sha = attempt.get(sha_field)
            if path_text is None:
                continue
            path = Path(str(path_text))
            if not path.exists():
                raise SystemExit(
                    f"RM001-SC002 source file missing: {path}"
                )
            if sha256_bytes(path.read_bytes()) != expected_sha:
                raise SystemExit(
                    f"RM001-SC002 source file hash mismatch: {path}"
                )

        if attempt["status"] != "READY":
            continue
        snapshot_path = Path(str(attempt["snapshot_path"]))
        if not snapshot_path.exists():
            raise SystemExit(
                f"RM001-SC002 snapshot missing: {snapshot_path}"
            )
        snapshot = load_canonical_gzip_json(snapshot_path.read_bytes())
        unsigned = dict(snapshot)
        stored = unsigned.pop("snapshot_sha256")
        if stored != digest(unsigned):
            raise SystemExit(
                f"RM001-SC002 snapshot hash mismatch: {snapshot_path}"
            )
        if stored != attempt["snapshot_sha256"]:
            raise SystemExit(
                "RM001-SC002 ledger/snapshot SHA mismatch"
            )
        mapping = snapshot.get("mapping_rows")
        if not isinstance(mapping, list):
            raise SystemExit("RM001-SC002 mapping rows missing")
        if digest(mapping) != attempt["mapping_sha256"]:
            raise SystemExit(
                "RM001-SC002 mapping SHA mismatch"
            )
        if snapshot.get("status") != "READY":
            raise SystemExit(
                "RM001-SC002 READY ledger row points to non-READY snapshot"
            )

    print(
        json.dumps(
            {
                "ledger_id": ledger["ledger_id"],
                "attempt_count": ledger["attempt_count"],
                "ledger_sha256": ledger["ledger_sha256"],
                "ready_attempt_count": observed_summary[
                    "ready_attempt_count"
                ],
                "ready_observation_dates": observed_summary[
                    "distinct_ready_observation_date_count"
                ],
                "ready_target_sessions": observed_summary[
                    "distinct_ready_target_session_count"
                ],
                "additional_ready_observation_dates_needed": observed_summary[
                    "additional_ready_observation_dates_needed"
                ],
                "additional_ready_target_sessions_needed": observed_summary[
                    "additional_ready_target_sessions_needed"
                ],
                "prospective_industry_source_capture_ready": observed_summary[
                    "prospective_industry_source_capture_ready"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
