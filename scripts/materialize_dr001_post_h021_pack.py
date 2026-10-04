from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.dr001_post_h021 import build_post_h021_evidence_pack


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre-evidence", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    output = build_post_h021_evidence_pack(
        _load(args.pre_evidence),
        _load(args.comparison),
        _load(args.gate),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"pack={output['pack_id']} "
        f"current={output['current_capture_date_ist']} "
        f"companies={len(output['companies'])}"
    )


if __name__ == "__main__":
    main()
