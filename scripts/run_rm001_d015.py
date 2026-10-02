from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.rm001_d015 import SOURCE_URL, build_d015_report


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
        description="Run frozen RM001 D015 Nifty Total Market industry source scan"
    )
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    raw = fetch(SOURCE_URL)
    if raw is None:
        raise RuntimeError("D015 official constituent source returned 404")

    report = build_d015_report(
        raw=raw,
        source_url=SOURCE_URL,
    )
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.raw_dir / f"nifty-total-market-{report['raw_sha256']}.csv"
    if raw_path.exists() and raw_path.read_bytes() != raw:
        raise RuntimeError(f"D015 raw evidence path collision: {raw_path}")
    raw_path.write_bytes(raw)

    report["raw_path"] = str(raw_path)
    report.pop("report_sha256", None)
    from marketlab.alpha import digest

    report["report_sha256"] = digest(report)
    _write_json(args.output, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
