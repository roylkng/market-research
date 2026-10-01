from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.rm001_size_timing import (
    size_timing_summary,
    validate_size_source_ledger,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify RM001-SC001 size timing evidence"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    validate_size_source_ledger(ledger)
    observed = json.loads(args.summary.read_text(encoding="utf-8"))
    expected = size_timing_summary(ledger)
    if observed != expected:
        raise SystemExit("RM001-SC001 summary differs from canonical ledger")
    unsigned = dict(observed)
    stored = unsigned.pop("summary_sha256")
    if stored != digest(unsigned):
        raise SystemExit("RM001-SC001 summary hash mismatch")

    print(
        json.dumps(
            {
                "ledger_id": ledger["ledger_id"],
                "attempt_count": ledger["attempt_count"],
                "ledger_sha256": ledger["ledger_sha256"],
                "ready_sessions": observed[
                    "distinct_ready_before_cutoff_session_count"
                ],
                "additional_ready_sessions_needed": observed[
                    "additional_ready_sessions_needed"
                ],
                "prospective_size_source_timing_ready": observed[
                    "prospective_size_source_timing_ready"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
