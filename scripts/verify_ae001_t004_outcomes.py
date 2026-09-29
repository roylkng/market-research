from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_t004_outcomes import validate_t004_outcome_ledger


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify AE001 T004 prospective outcome state"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    validate_t004_outcome_ledger(ledger)
    for row in ledger["outcomes"]:
        path = Path(str(row["artifact_path"]))
        if not path.exists():
            raise SystemExit(f"missing T004 outcome artifact: {path}")
        artifact = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        stored = str(artifact.get("artifact_sha256") or "")
        unsigned = dict(artifact)
        unsigned.pop("artifact_sha256", None)
        if stored != digest(unsigned):
            raise SystemExit(f"T004 outcome artifact hash mismatch: {path}")
        if stored != row["artifact_sha256"]:
            raise SystemExit(f"T004 outcome ledger/artifact hash mismatch: {path}")

    print(
        json.dumps(
            {
                "ledger_id": ledger["ledger_id"],
                "outcome_count": ledger["outcome_count"],
                "ledger_sha256": ledger["ledger_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
