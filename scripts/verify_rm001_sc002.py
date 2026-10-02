from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_history import load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_industry_timing import (
    industry_readiness_summary,
    validate_industry_source_ledger,
)


def _verify_raw(path_text: object, expected_sha: object, label: str) -> None:
    if expected_sha is None:
        if path_text is not None:
            raise SystemExit(f"{label}: null SHA with non-null path")
        return
    path = Path(str(path_text or ""))
    if not path.exists():
        raise SystemExit(f"{label}: missing raw file {path}")
    if sha256_bytes(path.read_bytes()) != expected_sha:
        raise SystemExit(f"{label}: raw SHA mismatch {path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify RM001-SC002 industry timing evidence"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    validate_industry_source_ledger(ledger)

    observed_summary = json.loads(args.summary.read_text(encoding="utf-8"))
    expected_summary = industry_readiness_summary(ledger)
    if observed_summary != expected_summary:
        raise SystemExit(
            "RM001-SC002 summary differs from canonical ledger"
        )
    unsigned_summary = dict(observed_summary)
    summary_sha = unsigned_summary.pop("summary_sha256")
    if summary_sha != digest(unsigned_summary):
        raise SystemExit("RM001-SC002 summary hash mismatch")

    for attempt in ledger["attempts"]:
        _verify_raw(
            attempt["constituent_raw_repo_path"],
            attempt["constituent_raw_sha256"],
            "constituent",
        )
        _verify_raw(
            attempt["security_raw_repo_path"],
            attempt["security_raw_sha256"],
            "security",
        )
        snapshot_sha = attempt.get("industry_snapshot_sha256")
        snapshot_path_text = attempt.get("industry_snapshot_repo_path")
        if snapshot_sha is None:
            if snapshot_path_text is not None:
                raise SystemExit(
                    "RM001-SC002 null snapshot SHA with non-null path"
                )
            continue
        snapshot_path = Path(str(snapshot_path_text or ""))
        if not snapshot_path.exists():
            raise SystemExit(
                f"RM001-SC002 snapshot file missing: {snapshot_path}"
            )
        snapshot = load_canonical_gzip_json(snapshot_path.read_bytes())
        unsigned = dict(snapshot)
        stored = unsigned.pop("snapshot_sha256")
        if stored != digest(unsigned) or stored != snapshot_sha:
            raise SystemExit(
                f"RM001-SC002 snapshot hash mismatch: {snapshot_path}"
            )
        if snapshot["constituent_raw_sha256"] != attempt[
            "constituent_raw_sha256"
        ]:
            raise SystemExit("RM001-SC002 constituent/snapshot SHA mismatch")
        if snapshot["security_raw_sha256"] != attempt[
            "security_raw_sha256"
        ]:
            raise SystemExit("RM001-SC002 security/snapshot SHA mismatch")
        if int(snapshot["row_count"]) != int(
            attempt["projected_eq_row_count"]
        ):
            raise SystemExit("RM001-SC002 snapshot row-count mismatch")
        if int(snapshot["industry_label_count"]) != int(
            attempt["industry_label_count"]
        ):
            raise SystemExit(
                "RM001-SC002 snapshot industry-count mismatch"
            )

    print(
        json.dumps(
            {
                "ledger_id": ledger["ledger_id"],
                "attempt_count": ledger["attempt_count"],
                "ledger_sha256": ledger["ledger_sha256"],
                "ready_sessions": observed_summary[
                    "ready_before_cutoff_session_count"
                ],
                "additional_ready_sessions_needed": observed_summary[
                    "additional_ready_sessions_needed"
                ],
                "prospective_industry_source_ready": observed_summary[
                    "prospective_industry_source_ready"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
