from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.events import sha256_bytes
from marketlab.h023_acquisition import (
    H023AcquisitionError,
    fetch_master,
    master_session,
)
from marketlab.ss001_shareholding_census import (
    build_shareholding_source_census,
    summarize_shareholding_master,
    validate_d001_census,
)


def _write_bytes(root: Path, *, symbol: str, raw: bytes) -> tuple[str, str]:
    sha = sha256_bytes(raw)
    path = root / "shareholding-master" / "sha256" / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"SS001 D002 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen SS001-D002 full-market shareholding source census"
    )
    parser.add_argument("--d001-census", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    d001 = json.loads(args.d001_census.read_text(encoding="utf-8"))
    if not isinstance(d001, dict):
        raise AlphaContractError("SS001 D002 D001 census must be an object")
    input_rows = validate_d001_census(d001)
    symbols = sorted(str(row["symbol"]).upper() for row in input_rows)

    captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    session = master_session(args.timeout_seconds)
    acquired = []

    for index, symbol in enumerate(symbols, start=1):
        if index == 1 or index % 50 == 0 or index == len(symbols):
            print(f"[shareholding] {index:04d}/{len(symbols)} {symbol}", flush=True)
        try:
            response = fetch_master(
                session,
                symbol=symbol,
                timeout=args.timeout_seconds,
                attempts=args.attempts,
            )
            raw = response.content
            if not raw:
                raise H023AcquisitionError("empty shareholding master response")
            sha, raw_path = _write_bytes(
                args.raw_dir,
                symbol=symbol,
                raw=raw,
            )
            payload = response.json()
        except (H023AcquisitionError, ValueError) as exc:
            acquired.append(
                {
                    "symbol": symbol,
                    "source_state": "REQUEST_FAILED",
                    "raw_master_sha256": None,
                    "raw_master_path": None,
                    "latest": None,
                    "prior": None,
                    "has_adjacent_prior": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        try:
            row = summarize_shareholding_master(
                payload,
                symbol=symbol,
                raw_sha256=sha,
            )
            row["raw_master_path"] = raw_path
            row["error"] = None
        except (H023AcquisitionError, AlphaContractError, TypeError, ValueError) as exc:
            row = {
                "symbol": symbol,
                "source_state": "PARSE_FAILED",
                "raw_master_sha256": sha,
                "raw_master_path": raw_path,
                "latest": None,
                "prior": None,
                "has_adjacent_prior": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        acquired.append(row)

    census = build_shareholding_source_census(
        d001,
        acquired,
        captured_at_utc=captured_at,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    panel_path = args.output / "ss001-d002-shareholding-sources.json"
    panel_path.write_text(
        json.dumps(
            census,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in census.items() if key != "rows"}
    (args.output / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
