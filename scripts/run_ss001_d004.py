from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.ss001_share_count import (
    ShareCountSourceError,
    build_share_count_panel,
    extract_share_counts,
)


def _read(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("GF001 D002 panel must be an object")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gf001-panel", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    panel = _read(args.gf001_panel)
    rows = panel.get("rows")
    if not isinstance(rows, list):
        raise TypeError("GF001 D002 rows must be a list")
    parsed = []
    total = sum(row.get("source_state") == "READY" for row in rows)

    for row in rows:
        if row.get("source_state") != "READY":
            continue
        symbol = str(row["symbol"]).upper()
        latest = row.get("latest")
        if not isinstance(latest, dict):
            raise TypeError("READY GF001 row missing latest source")
        sha = latest.get("raw_sha256")
        if not isinstance(sha, str) or len(sha) != 64:
            parsed.append({
                "symbol": symbol,
                "status": "RAW_UNAVAILABLE",
                "error": "LATEST_RAW_SOURCE_NOT_READY",
                "raw_sha256": None,
            })
            continue
        path = args.raw_root / "raw" / "xbrl" / "sha256" / f"{sha}.xml"
        if not path.is_file():
            parsed.append({
                "symbol": symbol,
                "status": "RAW_UNAVAILABLE",
                "error": "CONTENT_ADDRESSED_FILE_MISSING",
                "raw_sha256": None,
            })
            continue
        try:
            item = extract_share_counts(path.read_bytes(), expected_sha256=sha)
            parsed.append({"symbol": symbol, **item})
        except ShareCountSourceError as exc:
            parsed.append({
                "symbol": symbol,
                "status": "SHARE_COUNT_NOT_READY",
                "error": str(exc),
                "raw_sha256": None,
            })
        if len(parsed) % 250 == 0:
            print(f"[SS001-D004] {len(parsed)}/{total}", flush=True)

    result = build_share_count_panel(
        gf001_panel=panel,
        extracted_rows=parsed,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "ss001-d004-panel.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {k: v for k, v in result.items() if k != "rows"}
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
