from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_d010_p1 import short_archive_url
from marketlab.alpha_d010_p2 import slb_archive_url
from marketlab.alpha_d010_p3 import (
    build_p3_source_panel,
    map_source_rows,
    parse_short_selling,
    parse_slb_open_positions,
    summarize_p3,
)
from marketlab.alpha_history import canonical_gzip_json
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.events import sha256_bytes
from marketlab.marketdata import udiff_url

START_DATE = date(2025, 9, 1)
END_DATE = date(2026, 9, 25)


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


def _retain(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"D010 P3 raw path collision: {path}")
    path.write_bytes(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AE001 D010 P3 historical source coverage audit"
    )
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
    raw_root = args.output / "raw"
    sessions = []
    short_schemas = []
    slb_schemas = []

    cursor = START_DATE
    while cursor <= END_DATE:
        raw_udiff = fetch(udiff_url(cursor))
        if raw_udiff is None:
            cursor += timedelta(days=1)
            continue
        equities = parse_udiff_eq_panel(
            raw_udiff,
            session_date=cursor,
        )
        udiff_sha = sha256_bytes(raw_udiff)
        _retain(
            raw_root / "udiff" / cursor.isoformat() / f"{udiff_sha}.zip",
            raw_udiff,
        )

        short_raw = fetch(short_archive_url(cursor))
        short_rows = None
        short_sha = None
        short_error = None
        if short_raw is not None:
            short_sha = hashlib.sha256(short_raw).hexdigest()
            _retain(
                raw_root / "short-selling" / cursor.isoformat() / f"{short_sha}.csv",
                short_raw,
            )
            try:
                short_rows, short_schema = parse_short_selling(
                    short_raw,
                    session_date=cursor,
                )
                short_schemas.append(short_schema)
            except AlphaContractError as exc:
                short_error = str(exc)

        slb_raw = fetch(slb_archive_url(cursor))
        slb_rows = None
        slb_sha = None
        slb_error = None
        if slb_raw is not None:
            slb_sha = hashlib.sha256(slb_raw).hexdigest()
            _retain(
                raw_root / "slb-open-positions" / cursor.isoformat() / f"{slb_sha}.csv",
                slb_raw,
            )
            try:
                slb_rows, slb_schema = parse_slb_open_positions(slb_raw)
                slb_schemas.append(slb_schema)
            except AlphaContractError as exc:
                slb_error = str(exc)

        session = map_source_rows(
            short_rows=short_rows,
            slb_rows=slb_rows,
            equities=equities,
            session_date=cursor.isoformat(),
            short_raw_sha256=short_sha,
            slb_raw_sha256=slb_sha,
        )
        session["udiff_sha256"] = udiff_sha
        if short_error is not None:
            session["short_selling"]["source_status"] = "PARSER_REJECTED"
            session["short_selling"]["parser_error"] = short_error
        if slb_error is not None:
            session["slb_open_positions"]["source_status"] = "PARSER_REJECTED"
            session["slb_open_positions"]["parser_error"] = slb_error
        sessions.append(session)
        cursor += timedelta(days=1)

    report = summarize_p3(
        sessions=sessions,
        short_schemas=short_schemas,
        slb_schemas=slb_schemas,
    )
    panel = build_p3_source_panel(
        sessions=sessions,
        report_sha256=report["report_sha256"],
    )
    panel_bytes = canonical_gzip_json(panel)

    args.output.mkdir(parents=True, exist_ok=True)
    _write_json(args.output / "report.json", report)
    (args.output / "source-panel.json.gz").write_bytes(panel_bytes)
    manifest = {
        "schema_version": 1,
        "diagnostic_id": "AE001-D010-P3-v1",
        "report_sha256": report["report_sha256"],
        "source_panel_sha256": panel["panel_sha256"],
        "source_panel_artifact_sha256": sha256_bytes(panel_bytes),
        "completed_market_session_count": report[
            "completed_market_session_count"
        ],
        "status": report["status"],
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
