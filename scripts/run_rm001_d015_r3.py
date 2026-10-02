from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.rm001_d015_r3 import (
    PARENT_RAW_SHA256,
    SECURITY_RAW_SHA256,
    build_d015_r3_report,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run frozen RM001 D015-R3 dummy-separation diagnostic"
    )
    parser.add_argument("--parent-raw", type=Path, required=True)
    parser.add_argument("--security-raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    parent_raw = args.parent_raw.read_bytes()
    security_raw = args.security_raw.read_bytes()
    if sha256_bytes(parent_raw) != PARENT_RAW_SHA256:
        raise RuntimeError("D015-R3 parent raw SHA mismatch")
    if sha256_bytes(security_raw) != SECURITY_RAW_SHA256:
        raise RuntimeError("D015-R3 Security File SHA mismatch")

    report = build_d015_r3_report(
        parent_raw=parent_raw,
        security_raw=security_raw,
    )
    _write_json(args.output, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
