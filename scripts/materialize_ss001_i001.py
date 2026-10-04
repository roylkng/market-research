from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_investability import build_investability_context


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    output = build_investability_context(_load(args.census))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"context={output['context_id']} "
        f"names={len(output['rows'])} "
        f"bands={output['liquidity_band_counts']}"
    )


if __name__ == "__main__":
    main()
