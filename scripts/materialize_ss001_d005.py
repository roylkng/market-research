from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_size_asof import build_size_source_readiness


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"D005 source must be a JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-census", type=Path, required=True)
    parser.add_argument("--shareholding-census", type=Path, required=True)
    parser.add_argument("--share-count-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = build_size_source_readiness(
        market_census=_load(args.market_census),
        shareholding_census=_load(args.shareholding_census),
        share_count_panel=_load(args.share_count_panel),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss001-d005-panel.json").write_text(
        json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in output.items() if key != "rows"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
