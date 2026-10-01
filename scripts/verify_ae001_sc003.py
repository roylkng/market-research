from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_sc003_preopen import (
    preopen_readiness_summary,
    validate_sc003_ledger,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify AE001 SC003 evidence")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    validate_sc003_ledger(ledger)
    observed = json.loads(args.summary.read_text(encoding="utf-8"))
    expected = preopen_readiness_summary(ledger)
    if observed != expected:
        raise SystemExit("SC003 readiness summary differs from canonical ledger")
    unsigned = dict(observed)
    stored = unsigned.pop("summary_sha256")
    if stored != digest(unsigned):
        raise SystemExit("SC003 summary hash mismatch")

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
                "successor_preopen_design_ready": observed[
                    "successor_preopen_design_ready"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
