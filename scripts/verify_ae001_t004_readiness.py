from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_t004_readiness import validate_t004_readiness


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify canonical AE001 T004 operational readiness"
    )
    parser.add_argument("--readiness", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.readiness.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("T004 readiness must be a JSON object")
    validate_t004_readiness(payload)
    print(
        json.dumps(
            {
                "readiness_id": payload["readiness_id"],
                "session_date": payload["session_date"],
                "state": payload["state"],
                "readiness_sha256": payload["readiness_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
