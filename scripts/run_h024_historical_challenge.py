from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from marketlab.h024_acquisition import (
    PIT_GG_ENDPOINT,
    discover_sources,
    discovery_session,
    fetch_discovery,
)
from marketlab.h024_historical import (
    HOLIDAYS,
    MARKET_DATA_CUTOFF,
    SPECIAL_SESSION_TIMES,
    SOURCE_PANEL_RAW_SHA256,
    build_event_panel,
    build_frozen_sessions,
    build_outcome_report,
    parse_share_action_audit,
    parse_udiff_candidate_bars,
    summarize_outcomes,
    validate_source_panel,
)
from marketlab.marketdata import MarketArtifactStore, index_snapshot_url, udiff_url
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.pf001_marketdata import PF001MarketDataError, parse_pf001_nifty500_index

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/152.0 Safari/537.36"
)
SOURCE_START = date(2026, 5, 1)
SOURCE_END = date(2026, 9, 15)
CALENDAR_START = date(2026, 1, 1)


class HistoricalRunError(ValueError):
    """Raised when H024's historical challenge cannot be reconstructed safely."""


def _load_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise HistoricalRunError(f"expected JSON object: {path}")
    return payload, raw


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _fetch_archive(
    http: requests.Session,
    url: str,
    *,
    required: bool,
    attempts: int = 4,
) -> bytes | None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = http.get(url, timeout=30)
            if response.status_code == 404:
                if required:
                    raise HistoricalRunError(
                        f"required NSE archive returned 404: {url}"
                    )
                return None
            if (
                response.status_code in {403, 429} or response.status_code >= 500
            ) and attempt < attempts:
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            if not response.content:
                raise HistoricalRunError(f"NSE archive returned empty bytes: {url}")
            return response.content
        except (requests.RequestException, HistoricalRunError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            break
    raise HistoricalRunError(
        f"NSE archive fetch failed for {url}: {last_error}"
    ) from last_error


def _windows(start: date, end: date, days: int = 28) -> list[tuple[date, date]]:
    result: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=days - 1), end)
        result.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return result


def _capture_revision_sources(
    *,
    store: MarketArtifactStore,
    captured_at: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    api = discovery_session(30.0)
    by_id: dict[str, dict[str, Any]] = {}
    artifacts: list[dict[str, Any]] = []
    for start, end in _windows(SOURCE_START, SOURCE_END):
        response = fetch_discovery(
            api,
            start=start,
            end=end,
            timeout=30.0,
            attempts=4,
        )
        raw = response.content
        params = urlencode(
            {
                "index": "equities",
                "from_date": start.strftime("%d-%m-%Y"),
                "to_date": end.strftime("%d-%m-%Y"),
            }
        )
        source_url = f"{PIT_GG_ENDPOINT}?{params}"
        artifact = store.retain(
            raw,
            source_url=source_url,
            captured_at=captured_at,
            suffix=".json",
        )
        artifacts.append(artifact.to_dict())
        try:
            payload = response.json()
        except ValueError as exc:
            raise HistoricalRunError(
                f"PIT-GG response is not JSON for {start}..{end}"
            ) from exc
        for source in discover_sources(payload):
            source_id = str(source["source_id"])
            previous = by_id.get(source_id)
            if previous is not None and previous != source:
                raise HistoricalRunError(
                    f"PIT-GG source identity drift: {source_id}"
                )
            by_id[source_id] = source

    # The API windows are expressed in NSE-local calendar dates. Do not re-filter
    # their normalized UTC timestamps by UTC calendar date, which would drop
    # legitimate early-IST boundary records.
    revisions = [
        source
        for source in by_id.values()
        if source.get("submission_type") == "Revision"
    ]
    revisions.sort(
        key=lambda row: (
            str(row["exchange_disseminated_at_utc"]),
            str(row["symbol"]),
            str(row["app_id"]),
        )
    )
    return revisions, artifacts


def _capture_market_history(
    *,
    http: requests.Session,
    store: MarketArtifactStore,
    captured_at: datetime,
    symbols: set[str],
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    sessions = build_frozen_sessions()
    session_dates = {date.fromisoformat(row.session_date) for row in sessions}
    bars: dict[tuple[str, str], dict[str, Any]] = {}
    benchmark_bars: dict[str, dict[str, Any]] = {}
    index_artifacts: list[dict[str, Any]] = []
    udiff_artifacts: list[dict[str, Any]] = []

    for index, session in enumerate(sessions, start=1):
        day = date.fromisoformat(session.session_date)
        index_url = index_snapshot_url(day)
        index_raw = _fetch_archive(http, index_url, required=True)
        assert index_raw is not None
        index_artifact = store.retain(
            index_raw,
            source_url=index_url,
            captured_at=captured_at,
            suffix=".csv",
        )
        index_parsed = parse_pf001_nifty500_index(index_raw, session_date=day)
        benchmark_bars[session.session_date] = {
            **index_parsed.to_dict(),
            "raw_sha256": index_artifact.raw_sha256,
            "artifact_id": index_artifact.artifact_id,
        }
        index_artifacts.append(index_artifact.to_dict())

        udiff_url_value = udiff_url(day)
        udiff_raw = _fetch_archive(http, udiff_url_value, required=True)
        assert udiff_raw is not None
        udiff_artifact = store.retain(
            udiff_raw,
            source_url=udiff_url_value,
            captured_at=captured_at,
            suffix=".zip",
        )
        observed = parse_udiff_candidate_bars(
            udiff_raw,
            session_date=day,
            symbols=symbols,
        )
        for symbol, bar in observed.items():
            bars[(session.session_date, symbol)] = {
                **bar,
                "raw_sha256": udiff_artifact.raw_sha256,
                "artifact_id": udiff_artifact.artifact_id,
                "source_url": udiff_url_value,
            }
        udiff_artifacts.append(udiff_artifact.to_dict())
        if index % 20 == 0 or index == len(sessions):
            print(
                json.dumps(
                    {
                        "market_sessions_captured": index,
                        "market_sessions_total": len(sessions),
                        "candidate_bar_count": len(bars),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    cursor = CALENDAR_START
    while cursor <= MARKET_DATA_CUTOFF:
        should_probe = cursor not in session_dates and (
            cursor.weekday() >= 5 or cursor in HOLIDAYS
        )
        if should_probe:
            url = index_snapshot_url(cursor)
            raw = _fetch_archive(http, url, required=False)
            if raw is not None:
                try:
                    parsed = parse_pf001_nifty500_index(raw, session_date=cursor)
                except PF001MarketDataError:
                    parsed = None
                if parsed is not None and cursor not in SPECIAL_SESSION_TIMES:
                    raise HistoricalRunError(
                        "official Nifty 500 snapshot exposes unregistered special "
                        f"session {cursor}"
                    )
        cursor += timedelta(days=1)

    return bars, benchmark_bars, index_artifacts, udiff_artifacts


def _capture_corporate_actions(
    *,
    store: MarketArtifactStore,
    captured_at: datetime,
    symbols: list[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    client = NSEClient(timeout=20.0, attempts=4)
    audits: dict[str, dict[str, Any]] = {}
    artifacts: list[dict[str, Any]] = []
    for index, symbol in enumerate(symbols, start=1):
        try:
            payload, raw = client.corporate_actions_with_raw(
                symbol,
                from_date="01-01-2026",
                to_date="15-09-2026",
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
                "from_date": "01-01-2026",
                "to_date": "15-09-2026",
            }
        )
        source_url = f"{client.CORPORATE_ACTION_ENDPOINT.url}?{query}"
        artifact = store.retain(
            raw,
            source_url=source_url,
            captured_at=captured_at,
            suffix=".json",
        )
        audits[symbol] = {
            **parse_share_action_audit(payload, symbol=symbol),
            "source_url": source_url,
            "raw_sha256": artifact.raw_sha256,
            "artifact_id": artifact.artifact_id,
        }
        artifacts.append(artifact.to_dict())
        if index % 25 == 0 or index == len(symbols):
            print(
                json.dumps(
                    {
                        "corporate_action_symbols_captured": index,
                        "corporate_action_symbols_total": len(symbols),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    return audits, artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen H024 historical direct-insider-purchase challenge."
    )
    parser.add_argument("--source-panel", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--event-panel-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--evidence-manifest-out", type=Path, required=True)
    args = parser.parse_args()

    source_panel, source_raw = _load_json_bytes(args.source_panel)
    if hashlib.sha256(source_raw).hexdigest() != SOURCE_PANEL_RAW_SHA256:
        raise HistoricalRunError("frozen H024 source-panel bytes changed")
    validate_source_panel(source_panel, raw_bytes=source_raw)
    symbols = {
        str(row["symbol"]).strip().upper() for row in source_panel["records"]
    }
    if len(symbols) != 158:
        raise HistoricalRunError(
            f"expected 158 source symbols, found {len(symbols)}"
        )

    captured_at = datetime.now(UTC)
    store = MarketArtifactStore(args.store)
    http = requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})

    revisions, discovery_artifacts = _capture_revision_sources(
        store=store,
        captured_at=captured_at,
    )
    bars, benchmark_bars, index_artifacts, udiff_artifacts = (
        _capture_market_history(
            http=http,
            store=store,
            captured_at=captured_at,
            symbols=symbols,
        )
    )
    sessions = build_frozen_sessions()
    event_panel = build_event_panel(
        source_panel,
        revisions=revisions,
        sessions=sessions,
        bars=bars,
    )
    event_symbols = sorted(
        {str(row["symbol"]) for row in event_panel["events"]}
    )
    corporate_actions, action_artifacts = _capture_corporate_actions(
        store=store,
        captured_at=captured_at,
        symbols=event_symbols,
    )
    report = build_outcome_report(
        event_panel,
        sessions=sessions,
        bars=bars,
        benchmark_bars=benchmark_bars,
        corporate_actions=corporate_actions,
    )
    summary = summarize_outcomes(report)

    _write_json(args.event_panel_out, event_panel)
    _write_json(args.report_out, report)
    _write_json(args.summary_out, summary)

    manifest = {
        "schema_version": 1,
        "hypothesis_id": "H024",
        "execution_rule_id": "H024-R001",
        "captured_at_utc": captured_at.isoformat().replace("+00:00", "Z"),
        "source_panel_raw_sha256": SOURCE_PANEL_RAW_SHA256,
        "source_window": [SOURCE_START.isoformat(), SOURCE_END.isoformat()],
        "market_data_cutoff_session": MARKET_DATA_CUTOFF.isoformat(),
        "calendar_session_count": len(sessions),
        "source_symbol_count": len(symbols),
        "revision_source_count": len(revisions),
        "eligible_event_count": event_panel["event_count"],
        "eligible_event_symbol_count": event_panel["event_symbol_count"],
        "event_panel_sha256": event_panel["event_panel_sha256"],
        "candidate_bar_count": len(bars),
        "corporate_action_ready_count": sum(
            1
            for value in corporate_actions.values()
            if value.get("status") == "READY"
        ),
        "corporate_action_unresolved_count": sum(
            1
            for value in corporate_actions.values()
            if value.get("status") != "READY"
        ),
        "discovery_artifact_count": len(discovery_artifacts),
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
                "event_panel": {
                    "event_count": event_panel["event_count"],
                    "event_symbol_count": event_panel["event_symbol_count"],
                    "exclusion_reason_counts": event_panel[
                        "exclusion_reason_counts"
                    ],
                },
                "primary_classification": summary["primary_classification"],
                "primary": summary["horizons"]["60"],
                "report_sha256": report["report_sha256"],
                "summary_sha256": summary["summary_sha256"],
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
