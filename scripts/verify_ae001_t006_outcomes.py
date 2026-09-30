from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_t006_outcomes import validate_t006_outcome_ledger


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify AE001 T006 prospective outcome ledger"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.ledger.read_text(encoding="utf-8"))
    validate_t006_outcome_ledger(payload)
    print(
        json.dumps(
            {
                "ledger_id": payload["ledger_id"],
                "outcome_count": payload["outcome_count"],
                "ledger_sha256": payload["ledger_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
