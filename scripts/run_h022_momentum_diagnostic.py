from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from marketlab.h022_marketdata import parse_h022_nifty500_benchmark
from marketlab.h022_momentum_diagnostic import (
    DIAGNOSTIC_ID,
    OUTCOME_REPORT_SHA256,
    build_control_panel,
    build_diagnostic_sessions,
    parse_control_action_audit,
    required_control_windows,
    summarize_independence,
    validate_outcome_report,
)
from marketlab.h022_outcomes import parse_udiff_identity_bar
from marketlab.marketdata import MarketArtifactStore, index_snapshot_url, udiff_url
from marketlab.nse import NSEAcquisitionError, NSEClient

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/152.0 Safari/537.36"
)


class MomentumDiagnosticRunError(ValueError):
    """Raised when the H022 momentum diagnostic cannot be reconstructed safely."""


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _fetch_archive(
    session: requests.Session,
    url: str,
    *,
    attempts: int = 4,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=30)
            if (
                response.status_code == 429 or response.status_code >= 500
            ) and attempt < attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            if not response.content:
                raise MomentumDiagnosticRunError(f"NSE archive returned empty bytes: {url}")
            return response.content
        except (requests.RequestException, MomentumDiagnosticRunError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
                continue
            break
    raise MomentumDiagnosticRunError(f"NSE archive fetch failed for {url}: {last_error}") from last_error


def _universe_map(payload: object) -> dict[str, dict[str, str]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("members"), list):
        raise MomentumDiagnosticRunError("U001 universe payload is invalid")
    result: dict[str, dict[str, str]] = {}
    for row in payload["members"]:
        if not isinstance(row, dict):
            raise MomentumDiagnosticRunError("U001 member must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        series = str(row.get("series") or "").strip().upper()
        if not symbol or not isin or not series or symbol in result:
            raise MomentumDiagnosticRunError(f"invalid/duplicate U001 identity: {symbol}")
        result[symbol] = {"isin": isin, "series": series}
    return result


def _required_dates_and_symbols(
    windows: list[dict[str, str]],
) -> tuple[set[str], dict[str, set[str]]]:
    dates: set[str] = set()
    symbols_by_date: dict[str, set[str]] = defaultdict(set)
    for window in windows:
        if window["status"] != "REQUIRED":
            continue
        symbol = window["symbol"]
        for key in ("start_session_date", "end_session_date"):
            day = window[key]
            dates.add(day)
            symbols_by_date[day].add(symbol)
    return dates, symbols_by_date


def _capture_benchmark_closes(
    *,
    http: requests.Session,
    store: MarketArtifactStore,
    captured_at: datetime,
    dates: set[str],
) -> tuple[dict[str, float | None], list[dict[str, Any]]]:
    closes: dict[str, float | None] = {}
    artifacts: list[dict[str, Any]] = []
    for raw_day in sorted(dates):
        day = date.fromisoformat(raw_day)
        url = index_snapshot_url(day)
        raw = _fetch_archive(http, url)
        artifact = store.retain(raw, source_url=url, captured_at=captured_at, suffix=".csv")
        parsed = parse_h022_nifty500_benchmark(raw, session_date=day)
        closes[raw_day] = float(parsed["close"])
        artifacts.append(artifact.to_dict())
    return closes, artifacts


def _capture_stock_closes(
    *,
    http: requests.Session,
    store: MarketArtifactStore,
    captured_at: datetime,
    symbols_by_date: dict[str, set[str]],
    identities: dict[str, dict[str, str]],
) -> tuple[dict[tuple[str, str], float | None], list[dict[str, Any]], int]:
    closes: dict[tuple[str, str], float | None] = {}
    artifacts: list[dict[str, Any]] = []
    observed = 0
    for raw_day in sorted(symbols_by_date):
        day = date.fromisoformat(raw_day)
        url = udiff_url(day)
        raw = _fetch_archive(http, url)
        artifact = store.retain(raw, source_url=url, captured_at=captured_at, suffix=".zip")
        artifacts.append(artifact.to_dict())
        for symbol in sorted(symbols_by_date[raw_day]):
            identity = identities.get(symbol)
            if identity is None:
                raise MomentumDiagnosticRunError(f"control symbol missing from U001: {symbol}")
            bar = parse_udiff_identity_bar(
                raw,
                session_date=day,
                symbol=symbol,
                expected_isin=identity["isin"],
                series=identity["series"],
            )
            close = None if bar is None else float(bar["close"])
            if close is not None:
                observed += 1
            closes[(raw_day, symbol)] = close
    return closes, artifacts, observed


def _capture_corporate_actions(
    *,
    client: NSEClient,
    store: MarketArtifactStore,
    captured_at: datetime,
    symbols: list[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    audits: dict[str, dict[str, Any]] = {}
    artifacts: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            payload, raw = client.corporate_actions_with_raw(
                symbol,
                from_date="15-06-2025",
                to_date="11-09-2026",
            )
        except NSEAcquisitionError as exc:
            audits[symbol] = {
                "status": "UNRESOLVED_SOURCE",
                "actions": [],
                "unresolved_subjects": [],
                "error": str(exc),
            }
            continue
        query = urlencode(
            {
                "index": "equities",
                "symbol": symbol,
                "from_date": "15-06-2025",
                "to_date": "11-09-2026",
            }
        )
        source_url = f"{client.CORPORATE_ACTION_ENDPOINT.url}?{query}"
        artifact = store.retain(raw, source_url=source_url, captured_at=captured_at, suffix=".json")
        audit = parse_control_action_audit(payload, symbol=symbol)
        audits[symbol] = {
            **audit,
            "source_url": source_url,
            "raw_sha256": artifact.raw_sha256,
            "artifact_id": artifact.artifact_id,
        }
        artifacts.append(artifact.to_dict())
    return audits, artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run H022-D001 momentum independence diagnostic")
    parser.add_argument("--outcome-report", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--control-panel-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--evidence-manifest-out", type=Path, required=True)
    args = parser.parse_args()

    outcome_report = _load_json(args.outcome_report)
    if not isinstance(outcome_report, dict):
        raise MomentumDiagnosticRunError("H022 outcome report root must be an object")
    validate_outcome_report(outcome_report)
    identities = _universe_map(_load_json(args.universe))

    sessions = build_diagnostic_sessions()
    windows = required_control_windows(outcome_report, sessions)
    required_dates, symbols_by_date = _required_dates_and_symbols(windows)
    symbols = sorted({window["symbol"] for window in windows})
    missing_identities = [symbol for symbol in symbols if symbol not in identities]
    if missing_identities:
        raise MomentumDiagnosticRunError(f"diagnostic symbols missing from U001: {missing_identities}")

    captured_at = datetime.now(UTC)
    store = MarketArtifactStore(args.store)
    http = requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})

    benchmark_closes, benchmark_artifacts = _capture_benchmark_closes(
        http=http,
        store=store,
        captured_at=captured_at,
        dates=required_dates,
    )
    stock_closes, udiff_artifacts, observed_stock_bars = _capture_stock_closes(
        http=http,
        store=store,
        captured_at=captured_at,
        symbols_by_date=symbols_by_date,
        identities=identities,
    )
    client = NSEClient(timeout=20.0, attempts=4)
    corporate_actions, action_artifacts = _capture_corporate_actions(
        client=client,
        store=store,
        captured_at=captured_at,
        symbols=symbols,
    )

    control_panel = build_control_panel(
        outcome_report,
        sessions=sessions,
        stock_closes=stock_closes,
        benchmark_closes=benchmark_closes,
        corporate_actions=corporate_actions,
    )
    summary = summarize_independence(control_panel)
    _write_json(args.control_panel_out, control_panel)
    _write_json(args.summary_out, summary)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "outcome_report_sha256": OUTCOME_REPORT_SHA256,
        "captured_at_utc": captured_at.isoformat().replace("+00:00", "Z"),
        "calendar_session_count": len(sessions),
        "control_window_count": len(windows),
        "required_control_date_count": len(required_dates),
        "control_symbol_count": len(symbols),
        "benchmark_artifact_count": len(benchmark_artifacts),
        "udiff_artifact_count": len(udiff_artifacts),
        "corporate_action_artifact_count": len(action_artifacts),
        "corporate_action_ready_count": sum(
            audit.get("status") == "READY" for audit in corporate_actions.values()
        ),
        "corporate_action_unresolved_count": sum(
            audit.get("status") != "READY" for audit in corporate_actions.values()
        ),
        "stock_bar_request_count": sum(len(symbols_for_day) for symbols_for_day in symbols_by_date.values()),
        "stock_bar_observed_count": observed_stock_bars,
        "control_panel_sha256": control_panel["panel_sha256"],
        "diagnostic_summary_sha256": summary["summary_sha256"],
        "raw_store": str(args.store),
        "evidence_class": "POST_OUTCOME_DIAGNOSTIC",
        "can_upgrade_h022_validation": False,
        "live_capital_allowed": False,
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    _write_json(args.evidence_manifest_out, manifest)

    print(
        f"{DIAGNOSTIC_ID}: ready={summary['ready_count']}/{summary['record_count']}; "
        f"classification={summary['classification']}; panel={control_panel['panel_sha256']}; "
        f"summary={summary['summary_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
