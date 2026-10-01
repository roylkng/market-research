from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_prospective_d010_sources import (
    validate_sc004_source_ledger,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify AE001 SC004 short/SLB source ledger"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.ledger.read_text(encoding="utf-8"))
    validate_sc004_source_ledger(payload)
    eligible_sessions = sorted(
        {
            str(row["publication_session"])
            for row in payload["attempts"]
            if row.get("eligible_before_cutoff") is True
        }
    )
    print(
        json.dumps(
            {
                "ledger_id": payload["ledger_id"],
                "attempt_count": payload["attempt_count"],
                "eligible_session_count": len(eligible_sessions),
                "eligible_sessions": eligible_sessions,
                "ledger_sha256": payload["ledger_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
