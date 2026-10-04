from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.ss001_size import build_company_size_panel
from scripts.run_ss001_d003_shard import SHARD_COUNT, shard_for_symbol


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d001-census", type=Path, required=True)
    parser.add_argument("--shards-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    census = _load(args.d001_census)
    if census.get("census_sha256") != (
        "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
    ):
        raise ValueError("SS001 D003 merger frozen census SHA mismatch")

    acquired = []
    seen_symbols: set[str] = set()
    seen_shards: set[int] = set()
    for path in sorted(args.shards_root.rglob("ss001-d003-shard-*.json")):
        payload = _load(path)
        if payload.get("shard_count") != SHARD_COUNT:
            raise ValueError(f"{path}: wrong shard_count")
        shard_index = payload.get("shard_index")
        if not isinstance(shard_index, int) or not 0 <= shard_index < SHARD_COUNT:
            raise ValueError(f"{path}: invalid shard_index")
        if shard_index in seen_shards:
            raise ValueError(f"duplicate shard_index={shard_index}")
        seen_shards.add(shard_index)
        rows = payload.get("rows")
        if not isinstance(rows, list):
            raise TypeError(f"{path}: rows must be a list")
        if payload.get("assigned_symbol_count") != len(rows):
            raise ValueError(f"{path}: assigned_symbol_count mismatch")
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError(f"{path}: acquired row must be an object")
            symbol = str(row.get("symbol") or "").upper()
            if not symbol or symbol in seen_symbols:
                raise ValueError(f"duplicate/empty acquired symbol: {symbol}")
            if shard_for_symbol(symbol) != shard_index:
                raise ValueError(f"{symbol}: row appears in wrong shard")
            seen_symbols.add(symbol)
            acquired.append(row)

    if seen_shards != set(range(SHARD_COUNT)):
        raise ValueError(f"missing shards: {sorted(set(range(SHARD_COUNT)) - seen_shards)}")
    if len(acquired) != 2319:
        raise ValueError(f"expected 2319 acquired identities, found {len(acquired)}")

    panel = build_company_size_panel(
        d001_census=census,
        acquired_rows=acquired,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss001-d003-size-panel.json").write_text(
        json.dumps(panel, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in panel.items() if key != "rows"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
