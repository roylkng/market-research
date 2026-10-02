from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.rm001_v3_prospective import validate_prospective_v3_ledger


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify prospective RM001-v3 canonical risk states"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    validate_prospective_v3_ledger(ledger)
    for row in ledger["states"]:
        path = Path(str(row["state_artifact_path"]))
        if not path.exists():
            raise SystemExit(f"missing prospective RM001-v3 state: {path}")
        raw = path.read_bytes()
        payload = json.loads(gzip.decompress(raw).decode("utf-8"))
        stored = str(payload.get("state_sha256") or "")
        unsigned = dict(payload)
        unsigned.pop("state_sha256", None)
        if stored != digest(unsigned):
            raise SystemExit(f"prospective RM001-v3 state hash mismatch: {path}")
        if stored != row["v3_risk_state_sha256"]:
            raise SystemExit(
                f"prospective RM001-v3 ledger/state hash mismatch: {path}"
            )

    print(
        json.dumps(
            {
                "ledger_id": ledger["ledger_id"],
                "state_count": ledger["state_count"],
                "ledger_sha256": ledger["ledger_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
