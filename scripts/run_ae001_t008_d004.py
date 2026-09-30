from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_fundamental_combined import combine_t008_source_panels


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write(path: Path, payload: object) -> None:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize frozen T008-D004 four-period panel"
    )
    parser.add_argument("--d002-panel", type=Path, required=True)
    parser.add_argument("--d003-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    panel = combine_t008_source_panels(
        d002_panel=_load(args.d002_panel),
        d003_panel=_load(args.d003_panel),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    _write(args.output / "t008-d004-panel.json", panel)
    summary = {
        key: value
        for key, value in panel.items()
        if key != "records"
    }
    _write(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
