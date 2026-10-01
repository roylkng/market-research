from __future__ import annotations

import argparse
import json
from datetime import date
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
)
from marketlab.alpha_d010_p3b import build_p3b_panel, map_lagged_short_rows
from marketlab.alpha_d010_p4 import (
    SHORT_P3B_REPORT_SHA256,
    SLB_P3_REPORT_SHA256,
    augment_feature_panel_with_d010,
    summarize_p4,
)
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_market import DailyEquityObservation
from marketlab.events import sha256_bytes

SOURCE_START = date(2025, 9, 1)
SOURCE_END = date(2026, 9, 25)


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
        raise RuntimeError(f"D010 P4 raw path collision: {path}")
    path.write_bytes(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize frozen AE001 D010 P4 short/borrow features"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    base_features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    sessions = market.get("sessions")
    if not isinstance(sessions, list) or len(sessions) < 2:
        raise RuntimeError("D010 P4 requires a historical market panel")

    session_rows: list[
        tuple[str, list[DailyEquityObservation]]
    ] = []
    for raw_session in sessions:
        day = str(raw_session["session_date"])
        equities = [
            row
            if isinstance(row, DailyEquityObservation)
            else DailyEquityObservation(**row)
            for row in raw_session.get("equities", [])
        ]
        session_rows.append((day, equities))

    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    raw_root = args.output / "raw"
    short_sessions = []
    slb_sessions = []

    for index in range(1, len(session_rows)):
        publication_day_text, publication_equities = session_rows[index]
        publication_day = date.fromisoformat(publication_day_text)
        if not SOURCE_START <= publication_day <= SOURCE_END:
            continue
        trade_day_text, trade_equities = session_rows[index - 1]
        trade_day = date.fromisoformat(trade_day_text)

        short_raw = fetch(short_archive_url(publication_day))
        short_rows = None
        short_sha = None
        short_status = "UNAVAILABLE"
        short_error = None
        if short_raw is not None:
            short_sha = sha256_bytes(short_raw)
            _retain(
                raw_root
                / "short-selling"
                / publication_day_text
                / f"{short_sha}.csv",
                short_raw,
            )
            try:
                short_rows, _ = parse_short_selling(
                    short_raw,
                    session_date=trade_day,
                )
                short_status = "READY"
            except AlphaContractError as exc:
                short_status = "PARSER_REJECTED"
                short_error = str(exc)

        short_sessions.append(
            map_lagged_short_rows(
                publication_session=publication_day_text,
                trade_session=trade_day_text,
                rows=short_rows,
                trade_date_equities=trade_equities,
                publication_equities=publication_equities,
                raw_sha256=short_sha,
                source_status=short_status,
                parser_error=short_error,
            )
        )

        slb_raw = fetch(slb_archive_url(publication_day))
        slb_rows = None
        slb_sha = None
        slb_error = None
        if slb_raw is not None:
            slb_sha = sha256_bytes(slb_raw)
            _retain(
                raw_root
                / "slb-open-positions"
                / publication_day_text
                / f"{slb_sha}.csv",
                slb_raw,
            )
            try:
                slb_rows, _ = parse_slb_open_positions(slb_raw)
            except AlphaContractError as exc:
                slb_error = str(exc)

        slb_session = map_source_rows(
            short_rows=None,
            slb_rows=slb_rows,
            equities=publication_equities,
            session_date=publication_day_text,
            short_raw_sha256=None,
            slb_raw_sha256=slb_sha,
        )
        if slb_error is not None:
            slb_session["slb_open_positions"]["source_status"] = (
                "PARSER_REJECTED"
            )
            slb_session["slb_open_positions"]["parser_error"] = slb_error
        slb_sessions.append(slb_session)

    short_panel = build_p3b_panel(
        sessions=short_sessions,
        report_sha256=SHORT_P3B_REPORT_SHA256,
    )
    slb_panel = build_p3_source_panel(
        sessions=slb_sessions,
        report_sha256=SLB_P3_REPORT_SHA256,
    )
    augmented = augment_feature_panel_with_d010(
        feature_panel=base_features,
        market_panel=market,
        short_panel=short_panel,
        slb_panel=slb_panel,
    )
    report = summarize_p4(augmented)

    args.output.mkdir(parents=True, exist_ok=True)
    short_bytes = canonical_gzip_json(short_panel)
    slb_bytes = canonical_gzip_json(slb_panel)
    augmented_bytes = canonical_gzip_json(augmented)
    (args.output / "short-panel.json.gz").write_bytes(short_bytes)
    (args.output / "slb-panel.json.gz").write_bytes(slb_bytes)
    (args.output / "d010-feature-panel.json.gz").write_bytes(
        augmented_bytes
    )
    _write_json(args.output / "report.json", report)

    manifest = {
        "schema_version": 1,
        "diagnostic_id": "AE001-D010-P4-v1",
        "market_panel_sha256": market["panel_sha256"],
        "base_feature_panel_sha256": base_features["panel_sha256"],
        "short_source_panel_sha256": short_panel["panel_sha256"],
        "short_source_artifact_sha256": sha256_bytes(short_bytes),
        "slb_source_panel_sha256": slb_panel["panel_sha256"],
        "slb_source_artifact_sha256": sha256_bytes(slb_bytes),
        "d010_feature_panel_sha256": augmented["panel_sha256"],
        "d010_feature_artifact_sha256": sha256_bytes(augmented_bytes),
        "report_sha256": report["report_sha256"],
        "feature_session_count": report["feature_session_count"],
        "feature_row_count": report["feature_row_count"],
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
