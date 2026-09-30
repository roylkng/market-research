from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha_announcements import (
    SYMBOL_SAMPLE,
    WINDOW_END,
    WINDOW_START,
    build_d003_audit,
)
from marketlab.events import sha256_bytes
from marketlab.nse import NSEClient


def _retain(root: Path, label: str, raw: bytes) -> str:
    sha = sha256_bytes(raw)
    destination = root / "raw" / f"{label}-{sha}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != raw:
            raise RuntimeError(
                f"D003 content-addressed collision: {destination}"
            )
    else:
        destination.write_bytes(raw)
    return sha


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


def _nse_date(value: date) -> str:
    return value.strftime("%d-%m-%Y")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AE001 D003 NSE announcement source audit"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--pause-seconds", type=float, default=0.10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    args.output.mkdir(parents=True, exist_ok=True)

    full_payload, full_raw = client.corporate_announcements_with_raw(
        None,
        from_date=_nse_date(WINDOW_START),
        to_date=_nse_date(WINDOW_END),
    )
    full_sha = _retain(args.output, "whole-window-market", full_raw)

    daily_payloads = {}
    daily_hashes = {}
    day = WINDOW_START
    while day <= WINDOW_END:
        payload, raw = client.corporate_announcements_with_raw(
            None,
            from_date=_nse_date(day),
            to_date=_nse_date(day),
        )
        key = day.isoformat()
        daily_payloads[key] = payload
        daily_hashes[key] = _retain(
            args.output,
            f"daily-{key}",
            raw,
        )
        day = date.fromordinal(day.toordinal() + 1)
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    symbol_payloads = {}
    symbol_hashes = {}
    for symbol in SYMBOL_SAMPLE:
        payload, raw = client.corporate_announcements_with_raw(
            symbol,
            from_date=_nse_date(WINDOW_START),
            to_date=_nse_date(WINDOW_END),
        )
        symbol_payloads[symbol] = payload
        symbol_hashes[symbol] = _retain(
            args.output,
            f"symbol-{symbol}",
            raw,
        )
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    report = build_d003_audit(
        full_payload=full_payload,
        full_raw_sha256=full_sha,
        daily_payloads=daily_payloads,
        daily_raw_sha256=daily_hashes,
        symbol_payloads=symbol_payloads,
        symbol_raw_sha256=symbol_hashes,
        generated_at_utc=datetime.now(UTC).isoformat(),
    )
    _write_json(args.output / "report.json", report)

    summary = {
        "audit_id": report["audit_id"],
        "status": report["status"],
        "report_sha256": report["report_sha256"],
        "full_count": report["full_vs_daily"]["full_count"],
        "daily_union_count": report["full_vs_daily"][
            "daily_union_count"
        ],
        "full_vs_daily_exact": report["primary_gates"][
            "full_vs_daily_exact"
        ],
        "all_symbol_scoped_exact": report["primary_gates"][
            "all_symbol_scoped_exact"
        ],
        "distinct_symbol_count": report["distinct_symbol_count"],
        "max_daily_count": report["max_daily_count"],
        "max_rows_for_one_symbol": report["max_rows_for_one_symbol"],
        "thresholds": report["full_count_exceeds_threshold"],
        "market_return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
