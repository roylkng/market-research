from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.analyst import seal_decision


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and seal one Analyst Decision Object")
    parser.add_argument("--in", dest="input_path", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("analyst decision input must be a JSON object")

    sealed = seal_decision(payload)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != sealed:
            raise ValueError("refusing to replace an existing analyst decision with different bytes")
        return
    output.write_text(
        json.dumps(sealed, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
