from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from marketlab.h022 import validate_feature_panel
from marketlab.h022_marketdata import parse_h022_nifty500_benchmark
from marketlab.h022_outcomes import (
    HOLIDAYS,
    MARKET_DATA_CUTOFF,
    SPECIAL_SESSION_TIMES,
    build_frozen_sessions,
    build_outcome_report,
    first_entry_session,
    horizon_session,
    parse_share_action_audit,
    parse_udiff_identity_bar,
    summarize_outcomes,
)
from marketlab.marketdata import MarketArtifactStore, index_snapshot_url, udiff_url
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.pf001_marketdata import PF001MarketDataError

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/152.0 Safari/537.36"
)


class HistoricalRunError(ValueError):
    """Raised when the H022 historical challenge cannot be reconstructed safely."""


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
    required: bool,
    attempts: int = 4,
) -> bytes | None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 404:
                if required:
                    raise HistoricalRunError(f"required NSE archive returned 404: {url}")
                return None
            if (
                response.status_code == 429 or response.status_code >= 500
            ) and attempt < attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            if not response.content:
                raise HistoricalRunError(f"NSE archive returned empty bytes: {url}")
            return response.content
        except (requests.RequestException, HistoricalRunError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
                continue
            break
    raise HistoricalRunError(f"NSE archive fetch failed for {url}: {last_error}") from last_error


def _challenge_rows(panel: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in panel["records"]
        if row.get("historical_split") == "CHALLENGE" and row.get("feature_status") == "SIGNAL"
    ]


def _universe_map(payload: object) -> dict[str, dict[str, str]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("members"), list):
        raise HistoricalRunError("U001 universe payload is invalid")
    result: dict[str, dict[str, str]] = {}
    for row in payload["members"]:
        if not isinstance(row, dict):
            raise HistoricalRunError("U001 member must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        series = str(row.get("series") or "").strip().upper()
        if not symbol or not isin or not series or symbol in result:
            raise HistoricalRunError(f"invalid/duplicate U001 identity: {symbol}")
        result[symbol] = {"isin": isin, "series": series}
    return result


def _verify_and_capture_calendar(
    *,
    http: requests.Session,
    store: MarketArtifactStore,
    sessions: tuple[Any, ...],
    captured_at: datetime,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    benchmark_bars: dict[str, dict[str, Any]] = {}
    artifacts: list[dict[str, Any]] = []
    session_dates = {date.fromisoformat(row.session_date) for row in sessions}

    for row in sessions:
        day = date.fromisoformat(row.session_date)
        url = index_snapshot_url(day)
        raw = _fetch_archive(http, url, required=True)
        assert raw is not None
        artifact = store.retain(raw, source_url=url, captured_at=captured_at, suffix=".csv")
        bar = parse_h022_nifty500_benchmark(raw, session_date=day)
        benchmark_bars[row.session_date] = {
            **bar,
            "raw_sha256": artifact.raw_sha256,
            "artifact_id": artifact.artifact_id,
        }
        artifacts.append(artifact.to_dict())

    cursor = date(2025, 10, 1)
    while cursor <= MARKET_DATA_CUTOFF:
        should_probe = cursor not in session_dates and (
            cursor.weekday() >= 5 or cursor in HOLIDAYS
        )
        if should_probe:
            url = index_snapshot_url(cursor)
            raw = _fetch_archive(http, url, required=False)
            if raw is not None:
                try:
                    bar = parse_h022_nifty500_benchmark(raw, session_date=cursor)
                except PF001MarketDataError:
                    bar = None
                if bar is not None and cursor not in SPECIAL_SESSION_TIMES:
                    raise HistoricalRunError(
                        f"official Nifty 500 snapshot exposes unregistered special session {cursor}"
                    )
        cursor += timedelta(days=1)

    return benchmark_bars, artifacts


def _required_stock_dates(
    panel: dict[str, Any], sessions: tuple[Any, ...]
) -> dict[str, set[str]]:
    required: dict[str, set[str]] = defaultdict(set)
    for row in _challenge_rows(panel):
        entry_result = first_entry_session(str(row["exchange_published_at_utc"]), sessions)
        if entry_result is None:
            continue
        entry_index, entry = entry_result
        symbol = str(row["symbol"])
        required[entry.session_date].add(symbol)
        for horizon in (20, 60, 120):
            exit_session = horizon_session(sessions, entry_index=entry_index, horizon=horizon)
            if exit_session is not None:
                required[exit_session.session_date].add(symbol)
    return required


def _capture_stock_bars(
    *,
    http: requests.Session,
    store: MarketArtifactStore,
    captured_at: datetime,
    required: dict[str, set[str]],
    identities: dict[str, dict[str, str]],
) -> tuple[dict[tuple[str, str], dict[str, Any] | None], list[dict[str, Any]]]:
    bars: dict[tuple[str, str], dict[str, Any] | None] = {}
    artifacts: list[dict[str, Any]] = []
    for raw_day in sorted(required):
        day = date.fromisoformat(raw_day)
        url = udiff_url(day)
        raw = _fetch_archive(http, url, required=True)
        assert raw is not None
        artifact = store.retain(raw, source_url=url, captured_at=captured_at, suffix=".zip")
        artifacts.append(artifact.to_dict())
        for symbol in sorted(required[raw_day]):
            identity = identities.get(symbol)
            if identity is None:
                raise HistoricalRunError(f"challenge symbol is not present in frozen U001: {symbol}")
            bar = parse_udiff_identity_bar(
                raw,
                session_date=day,
                symbol=symbol,
                expected_isin=identity["isin"],
                series=identity["series"],
            )
            if bar is not None:
                bar = {
                    **bar,
                    "raw_sha256": artifact.raw_sha256,
                    "artifact_id": artifact.artifact_id,
                }
            bars[(raw_day, symbol)] = bar
    return bars, artifacts


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
                from_date="01-10-2025",
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
                "from_date": "01-10-2025",
                "to_date": "11-09-2026",
            }
        )
        source_url = f"{client.CORPORATE_ACTION_ENDPOINT.url}?{query}"
        artifact = store.retain(raw, source_url=source_url, captured_at=captured_at, suffix=".json")
        audit = parse_share_action_audit(payload, symbol=symbol)
        audits[symbol] = {
            **audit,
            "source_url": source_url,
            "raw_sha256": artifact.raw_sha256,
            "artifact_id": artifact.artifact_id,
        }
        artifacts.append(artifact.to_dict())
    return audits, artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen H022 historical survivor-panel return challenge."
    )
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--evidence-manifest-out", type=Path, required=True)
    args = parser.parse_args()

    feature_panel = _load_json(args.feature_panel)
    if not isinstance(feature_panel, dict):
        raise HistoricalRunError("feature panel root must be an object")
    validate_feature_panel(feature_panel)
    if feature_panel.get("panel_sha256") != (
        "dd992523238aebce5e9f6ee8535951fd869bf9d8615705d4fb5f420e8f85bee3"
    ):
        raise HistoricalRunError("feature panel digest does not match H022-X001")

    identities = _universe_map(_load_json(args.universe))
    challenge_symbols = sorted({str(row["symbol"]) for row in _challenge_rows(feature_panel)})
    missing_identities = [symbol for symbol in challenge_symbols if symbol not in identities]
    if missing_identities:
        raise HistoricalRunError(f"challenge symbols missing from U001: {missing_identities}")

    captured_at = datetime.now(UTC)
    sessions = build_frozen_sessions()
    store = MarketArtifactStore(args.store)
    http = requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})

    benchmark_bars, index_artifacts = _verify_and_capture_calendar(
        http=http,
        store=store,
        sessions=sessions,
        captured_at=captured_at,
    )
    required = _required_stock_dates(feature_panel, sessions)
    stock_bars, udiff_artifacts = _capture_stock_bars(
        http=http,
        store=store,
        captured_at=captured_at,
        required=required,
        identities=identities,
    )
    client = NSEClient(timeout=20.0, attempts=4)
    corporate_actions, action_artifacts = _capture_corporate_actions(
        client=client,
        store=store,
        captured_at=captured_at,
        symbols=challenge_symbols,
    )

    report = build_outcome_report(
        feature_panel,
        sessions=sessions,
        stock_bars=stock_bars,
        benchmark_bars=benchmark_bars,
        corporate_actions=corporate_actions,
    )
    summary = summarize_outcomes(report)
    _write_json(args.report_out, report)
    _write_json(args.summary_out, summary)

    manifest = {
        "schema_version": 1,
        "hypothesis_id": "H022",
        "execution_rule_id": "H022-X001",
        "captured_at_utc": captured_at.isoformat().replace("+00:00", "Z"),
        "feature_panel_sha256": feature_panel["panel_sha256"],
        "market_data_cutoff_session": MARKET_DATA_CUTOFF.isoformat(),
        "calendar_session_count": len(sessions),
        "challenge_symbol_count": len(challenge_symbols),
        "required_udiff_session_count": len(required),
        "stock_bar_request_count": sum(len(symbols) for symbols in required.values()),
        "stock_bar_observed_count": sum(1 for value in stock_bars.values() if value is not None),
        "corporate_action_ready_count": sum(
            1 for value in corporate_actions.values() if value.get("status") == "READY"
        ),
        "corporate_action_unresolved_count": sum(
            1 for value in corporate_actions.values() if value.get("status") != "READY"
        ),
        "index_artifact_count": len(index_artifacts),
        "udiff_artifact_count": len(udiff_artifacts),
        "corporate_action_artifact_count": len(action_artifacts),
        "outcome_report_sha256": report["report_sha256"],
        "outcome_summary_sha256": summary["summary_sha256"],
        "raw_store": str(args.store),
        "live_capital_allowed": False,
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    _write_json(args.evidence_manifest_out, manifest)

    print(
        json.dumps(
            {
                "primary_classification": summary["primary_classification"],
                "primary": summary["horizons"]["60"],
                "report_sha256": report["report_sha256"],
                "summary_sha256": summary["summary_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
