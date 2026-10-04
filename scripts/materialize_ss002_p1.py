from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss002_p1 import build_p1_census


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d001-census", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    d001 = json.loads(args.d001_census.read_text(encoding="utf-8"))
    if not isinstance(d001, dict):
        raise TypeError("SS002 P1 D001 census must be an object")

    output = build_p1_census(d001)
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
        f"census={output['census_id']} "
        f"primary={output['current_actionable_primary_event_count']} "
        f"symbols={output['current_actionable_primary_symbol_count']} "
        f"pass={output['feasibility_pass']}"
    )


if __name__ == "__main__":
    main()
