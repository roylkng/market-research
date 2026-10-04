from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.ss001_size import SS001SizeError, parse_trade_info_market_cap

SHARD_COUNT = 6


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def shard_for_symbol(symbol: str, *, shard_count: int = SHARD_COUNT) -> int:
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    digest = hashlib.sha256(symbol.strip().upper().encode("utf-8")).digest()
    return int.from_bytes(digest, "big") % shard_count


def _retain(root: Path, raw: bytes) -> tuple[str, str]:
    sha = sha256_bytes(raw)
    path = root / "quote-trade-info" / "sha256" / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"SS001 D003 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d001-census", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=SHARD_COUNT)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--pause-seconds", type=float, default=0.01)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.shard_count != SHARD_COUNT:
        raise ValueError(f"SS001 D003 requires shard_count={SHARD_COUNT}")
    if not 0 <= args.shard_index < args.shard_count:
        raise ValueError("shard_index is outside frozen shard range")

    census = _load(args.d001_census)
    if census.get("census_id") != "SS001-D001-v1":
        raise ValueError("SS001 D003 requires frozen D001 census")
    if census.get("census_sha256") != (
        "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
    ):
        raise ValueError("SS001 D003 frozen census SHA mismatch")
    rows = census.get("rows")
    if not isinstance(rows, list) or len(rows) != 2319:
        raise TypeError("SS001 D003 D001 rows must contain 2,319 identities")

    assigned = [
        row
        for row in rows
        if isinstance(row, dict)
        and shard_for_symbol(str(row.get("symbol") or ""), shard_count=args.shard_count)
        == args.shard_index
    ]
    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    acquired = []

    for index, row in enumerate(assigned, start=1):
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("SS001 D003 D001 row lacks symbol")
        try:
            payload, raw = client.quote_equity_trade_info_with_raw(symbol)
            raw_sha, raw_path = _retain(args.raw_dir, raw)
            parsed = parse_trade_info_market_cap(payload, symbol=symbol, raw=raw)
            if parsed["raw_sha256"] != raw_sha:
                raise SS001SizeError("trade-info raw SHA mismatch")
            acquired.append({**parsed, "raw_path": raw_path})
        except (NSEAcquisitionError, SS001SizeError) as exc:
            acquired.append(
                {
                    "symbol": symbol,
                    "status": "SOURCE_UNAVAILABLE",
                    "total_market_cap_inr_crore": None,
                    "free_float_market_cap_inr_crore": None,
                    "free_float_fraction": None,
                    "raw_sha256": None,
                    "raw_path": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

        if index == 1 or index % 50 == 0 or index == len(assigned):
            print(
                f"[size-shard {args.shard_index}] {index:04d}/{len(assigned)} "
                f"{symbol} status={acquired[-1]['status']}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    payload = {
        "schema_version": 1,
        "diagnostic_id": "SS001-D003-v1",
        "source_d001_census_sha256": census["census_sha256"],
        "shard_count": args.shard_count,
        "shard_index": args.shard_index,
        "assigned_symbol_count": len(assigned),
        "captured_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "rows": acquired,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    out = args.output / f"ss001-d003-shard-{args.shard_index}.json"
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "shard_index": args.shard_index,
                "assigned_symbol_count": len(assigned),
                "ready_count": sum(row["status"] == "READY" for row in acquired),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
