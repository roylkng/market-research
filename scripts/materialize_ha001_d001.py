from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ha001_asset_census import build_asset_anomaly_census


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize frozen HA001-D001 source-only asset research leads"
    )
    parser.add_argument("--fa001-panel", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.fa001_panel.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise TypeError("FA001 D002 panel must be a JSON object")

    census = build_asset_anomaly_census(source)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "ha001-d001-census.json").write_text(
        json.dumps(census, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )

    summary = {
        key: value
        for key, value in census.items()
        if key not in {"rows", "flagged_symbol_lists"}
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
