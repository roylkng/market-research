from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_prospective_sources import validate_source_ledger


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify AE001 SC001 source ledger")
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.ledger.read_text(encoding="utf-8"))
    validate_source_ledger(payload)
    print(
        json.dumps(
            {
                "ledger_id": payload["ledger_id"],
                "attempt_count": payload["attempt_count"],
                "ledger_sha256": payload["ledger_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
