from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
import run_h022_historical_challenge as base_runner

from marketlab.h022_expanded_features import validate_expanded_feature_panel
from marketlab.h022_expanded_outcomes import (
    FEATURE_PANEL_SHA256,
    build_expanded_outcome_report,
    challenge_rows,
    summarize_expanded_outcomes,
)
from marketlab.h022_outcomes import (
    MARKET_DATA_CUTOFF,
    build_frozen_sessions,
    first_entry_session,
    horizon_session,
)
from marketlab.marketdata import MarketArtifactStore
from marketlab.nse import NSEClient

USER_AGENT = base_runner.USER_AGENT


class ExpandedHistoricalRunError(ValueError):
    """Raised when expanded H022 returns cannot be reconstructed safely."""


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _identity_map(reconstruction: object) -> dict[str, dict[str, str]]:
    if not isinstance(reconstruction, dict):
        raise ExpandedHistoricalRunError("historical membership reconstruction must be an object")
    if reconstruction.get("reconstruction_sha256") != (
        "dee26ffc683781202da21e789cc45f480d625772e8510f3beb1f65aa4a6ba144"
    ):
        raise ExpandedHistoricalRunError("historical membership reconstruction digest changed")
    rows = reconstruction.get("expanded_union_members")
    if not isinstance(rows, list) or len(rows) != 211:
        raise ExpandedHistoricalRunError("expanded union identity coverage changed")
    identities: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ExpandedHistoricalRunError("expanded union member must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        series = str(row.get("series") or "EQ").strip().upper()
        isin = str(row.get("isin") or "").strip()
        if not symbol or not series or symbol in identities:
            raise ExpandedHistoricalRunError(f"invalid/duplicate historical identity: {symbol}")
        identities[symbol] = {"isin": isin, "series": series}
    return identities


def _required_stock_dates(
    panel: dict[str, Any], sessions: tuple[Any, ...]
) -> dict[str, set[str]]:
    required: dict[str, set[str]] = defaultdict(set)
    for row in challenge_rows(panel):
        entry_result = first_entry_session(
            str(row["exchange_published_at_utc"]), sessions
        )
        if entry_result is None:
            continue
        entry_index, entry = entry_result
        symbol = str(row["symbol"])
        required[entry.session_date].add(symbol)
        for horizon in (20, 60, 120):
            exit_session = horizon_session(
                sessions, entry_index=entry_index, horizon=horizon
            )
            if exit_session is not None:
                required[exit_session.session_date].add(symbol)
    return required


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run H022 point-in-time Nifty 200 historical universe challenge"
    )
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--reconstruction", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--evidence-manifest-out", type=Path, required=True)
    args = parser.parse_args()

    feature_panel = _load_json(args.feature_panel)
    if not isinstance(feature_panel, dict):
        raise ExpandedHistoricalRunError("expanded feature panel must be an object")
    validate_expanded_feature_panel(feature_panel)
    if feature_panel.get("panel_sha256") != FEATURE_PANEL_SHA256:
        raise ExpandedHistoricalRunError("expanded feature panel digest changed")

    identities = _identity_map(_load_json(args.reconstruction))
    challenge = challenge_rows(feature_panel)
    challenge_symbols = sorted({str(row["symbol"]) for row in challenge})
    missing = [symbol for symbol in challenge_symbols if symbol not in identities]
    if missing:
        raise ExpandedHistoricalRunError(
            f"expanded challenge symbols missing from historical union: {missing}"
        )

    captured_at = datetime.now(UTC)
    sessions = build_frozen_sessions()
    store = MarketArtifactStore(args.store)
    http = requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})

    benchmark_bars, index_artifacts = base_runner._verify_and_capture_calendar(
        http=http,
        store=store,
        sessions=sessions,
        captured_at=captured_at,
    )
    required = _required_stock_dates(feature_panel, sessions)
    stock_bars, udiff_artifacts = base_runner._capture_stock_bars(
        http=http,
        store=store,
        captured_at=captured_at,
        required=required,
        identities=identities,
    )
    client = NSEClient(timeout=20.0, attempts=4)
    corporate_actions, action_artifacts = base_runner._capture_corporate_actions(
        client=client,
        store=store,
        captured_at=captured_at,
        symbols=challenge_symbols,
    )

    report = build_expanded_outcome_report(
        feature_panel,
        sessions=sessions,
        stock_bars=stock_bars,
        benchmark_bars=benchmark_bars,
        corporate_actions=corporate_actions,
    )
    summary = summarize_expanded_outcomes(report)
    _write_json(args.report_out, report)
    _write_json(args.summary_out, summary)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "hypothesis_id": "H022",
        "challenge_rule_id": "H022-UX001",
        "execution_rule_id": "H022-X001",
        "evidence_class": "HISTORICAL_POINT_IN_TIME_NIFTY200_CHALLENGER",
        "captured_at_utc": captured_at.isoformat().replace("+00:00", "Z"),
        "feature_panel_sha256": feature_panel["panel_sha256"],
        "membership_reconstruction_sha256": (
            "dee26ffc683781202da21e789cc45f480d625772e8510f3beb1f65aa4a6ba144"
        ),
        "market_data_cutoff_session": MARKET_DATA_CUTOFF.isoformat(),
        "calendar_session_count": len(sessions),
        "challenge_signal_count": len(challenge),
        "challenge_symbol_count": len(challenge_symbols),
        "required_udiff_session_count": len(required),
        "stock_bar_request_count": sum(len(symbols) for symbols in required.values()),
        "stock_bar_observed_count": sum(
            1 for value in stock_bars.values() if value is not None
        ),
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
        "exact_historical_u001": False,
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
