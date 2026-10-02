from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlencode

from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.rm001_d009 import (
    SAMPLE_SYMBOLS,
    build_d009_report,
    raw_observation,
)


def _write_json(path: Path, payload: object) -> None:
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
        description="Run frozen RM001 D009 NSE quote industry source scan"
    )
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--pause-seconds", type=float, default=0.15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.pause_seconds < 0:
        raise ValueError("pause-seconds cannot be negative")

    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    observations = []
    args.raw_dir.mkdir(parents=True, exist_ok=True)

    for index, symbol in enumerate(SAMPLE_SYMBOLS):
        source_url = (
            f"{client.QUOTE_ENDPOINT.url}?"
            + urlencode({"symbol": symbol})
        )
        try:
            payload, raw = client.quote_equity_with_raw(symbol)
            observation = raw_observation(
                requested_symbol=symbol,
                payload=payload,
                raw=raw,
                source_url=source_url,
            )
            raw_path = (
                args.raw_dir
                / f"{index + 1:02d}-{symbol}-{observation['raw_sha256']}.json"
            )
            if raw_path.exists() and raw_path.read_bytes() != raw:
                raise RuntimeError(
                    f"D009 raw evidence path collision: {raw_path}"
                )
            raw_path.write_bytes(raw)
            observation["raw_path"] = str(raw_path)
        except NSEAcquisitionError as exc:
            observation = {
                "requested_symbol": symbol,
                "status": "ACQUISITION_ERROR",
                "returned_symbol": None,
                "symbol_identity_match": False,
                "isin": None,
                "classification": None,
                "industry_info_normalized_keys": [],
                "source_url": source_url,
                "raw_sha256": None,
                "raw_byte_count": None,
                "raw_path": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        observations.append(observation)
        if index + 1 < len(SAMPLE_SYMBOLS) and args.pause_seconds:
            time.sleep(args.pause_seconds)

    report = build_d009_report(observations=observations)
    _write_json(args.output, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
