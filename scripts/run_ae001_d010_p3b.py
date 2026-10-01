from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_d010_p1 import short_archive_url
from marketlab.alpha_d010_p3 import parse_short_selling
from marketlab.alpha_d010_p3b import (
    build_p3b_panel,
    map_lagged_short_rows,
    summarize_p3b,
)
from marketlab.alpha_history import canonical_gzip_json
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.events import sha256_bytes
from marketlab.marketdata import udiff_url

SUPPORT_START = date(2025, 8, 20)
WINDOW_START = date(2025, 9, 1)
WINDOW_END = date(2026, 9, 25)


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
        raise RuntimeError(f"D010 P3B raw path collision: {path}")
    path.write_bytes(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen D010 P3B lagged short-selling historical audit"
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

    market_sessions = []
    cursor = SUPPORT_START
    while cursor <= WINDOW_END:
        raw = fetch(udiff_url(cursor))
        if raw is not None:
            equities = parse_udiff_eq_panel(
                raw,
                session_date=cursor,
            )
            raw_sha = sha256_bytes(raw)
            _retain(
                raw_root / "udiff" / cursor.isoformat() / f"{raw_sha}.zip",
                raw,
            )
            market_sessions.append(
                {
                    "session_date": cursor.isoformat(),
                    "equities": equities,
                    "raw_sha256": raw_sha,
                }
            )
        cursor += timedelta(days=1)

    if len(market_sessions) < 2:
        raise RuntimeError("D010 P3B found insufficient UDiFF sessions")

    audited = []
    schemas = []
    for index in range(1, len(market_sessions)):
        publication = market_sessions[index]
        publication_date = date.fromisoformat(
            str(publication["session_date"])
        )
        if not WINDOW_START <= publication_date <= WINDOW_END:
            continue
        trade = market_sessions[index - 1]
        trade_date = date.fromisoformat(str(trade["session_date"]))

        raw = fetch(short_archive_url(publication_date))
        rows = None
        raw_sha = None
        status = "UNAVAILABLE"
        parser_error = None
        if raw is not None:
            raw_sha = sha256_bytes(raw)
            _retain(
                raw_root
                / "short-selling"
                / publication_date.isoformat()
                / f"{raw_sha}.csv",
                raw,
            )
            try:
                rows, schema = parse_short_selling(
                    raw,
                    session_date=trade_date,
                )
                schemas.append(schema)
                status = "READY"
            except AlphaContractError as exc:
                status = "PARSER_REJECTED"
                parser_error = str(exc)

        audited.append(
            map_lagged_short_rows(
                publication_session=publication_date.isoformat(),
                trade_session=trade_date.isoformat(),
                rows=rows,
                trade_date_equities=trade["equities"],
                publication_equities=publication["equities"],
                raw_sha256=raw_sha,
                source_status=status,
                parser_error=parser_error,
            )
        )

    report = summarize_p3b(
        audited,
        schemas=schemas,
    )
    panel = build_p3b_panel(
        sessions=audited,
        report_sha256=report["report_sha256"],
    )
    panel_bytes = canonical_gzip_json(panel)

    args.output.mkdir(parents=True, exist_ok=True)
    _write_json(args.output / "report.json", report)
    (args.output / "short-panel.json.gz").write_bytes(panel_bytes)
    manifest = {
        "schema_version": 1,
        "diagnostic_id": "AE001-D010-P3B-v1",
        "report_sha256": report["report_sha256"],
        "short_panel_sha256": panel["panel_sha256"],
        "short_panel_artifact_sha256": sha256_bytes(panel_bytes),
        "publication_session_count": report["publication_session_count"],
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
