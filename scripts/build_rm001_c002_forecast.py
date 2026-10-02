from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from marketlab.alpha import AlphaContractError
from marketlab.alpha_acquisition import acquire_historical_market_panel, http_fetcher
from marketlab.alpha_corporate_actions import (
    acquire_corporate_action_ledger,
    filter_feature_panel_for_corporate_actions,
)
from marketlab.alpha_history import build_historical_feature_panel, canonical_gzip_json
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.events import sha256_bytes
from marketlab.nse import NSEClient
from marketlab.rm001 import (
    build_rm001_exposure_panel,
    build_rm001_factor_history,
    build_rm001_risk_state,
)
from marketlab.rm001_calibration import calibrate_v1_risk_state
from marketlab.rm001_c002 import (
    append_forecast_entry,
    build_forecast_artifact,
    forecast_seal_cutoff_utc,
    next_unhandled_target,
    validate_forecast_ledger,
)

SUPPORT_LOOKBACK_CALENDAR_DAYS = 420
MIN_COMPLETED_MARKET_SESSIONS = 200


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


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


def _load_exact_raw(path_text: str, expected_sha: str, name: str) -> bytes:
    path = Path(path_text)
    if not path.exists():
        raise AlphaContractError(f"{name} exact raw file is missing: {path}")
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_sha:
        raise AlphaContractError(f"{name} exact raw hash mismatch")
    return raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seal one prospective RM001 C002 raw-v1/CAL1 risk forecast"
    )
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--forecast-ledger", type=Path, required=True)
    parser.add_argument("--forecast-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_ledger = _load_json(args.sc001_ledger)
    validate_source_ledger(source_ledger)
    forecast_ledger = _load_json(args.forecast_ledger)
    validate_forecast_ledger(forecast_ledger)

    attempt = next_unhandled_target(
        source_ledger=source_ledger,
        forecast_ledger=forecast_ledger,
    )
    if attempt is None:
        print(
            json.dumps(
                {
                    "state": "NO_UNHANDLED_ELIGIBLE_TARGET",
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    target_session = str(attempt["session_date"])
    cutoff = forecast_seal_cutoff_utc(target_session)
    now = datetime.now(UTC)
    if now > cutoff:
        updated = append_forecast_entry(
            forecast_ledger,
            target_session_date=target_session,
            status="MISSED_0905_CUTOFF",
            sc001_attempt_sha256=str(attempt["attempt_sha256"]),
            observed_at_utc=now.isoformat(),
            reason="FORECAST_WORKFLOW_OBSERVED_TARGET_AFTER_FROZEN_CUTOFF",
        )
        _write_json(args.forecast_ledger, updated)
        print(
            json.dumps(
                {
                    "state": "MISSED_0905_CUTOFF",
                    "target_session_date": target_session,
                    "cutoff_utc": cutoff.isoformat(),
                    "changed": True,
                    "forecast_ledger_sha256": updated["ledger_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0

    market_meta = attempt["market"]
    current_market_raw = _load_exact_raw(
        str(market_meta["raw_repo_path"]),
        str(market_meta["raw_sha256"]),
        "C002 target market",
    )

    target_day = date.fromisoformat(target_session)
    support_start = target_day - timedelta(days=SUPPORT_LOOKBACK_CALENDAR_DAYS)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    base_fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    target_market_url = str(market_meta["source_url"])

    def market_fetch(url: str):
        if url == target_market_url:
            return current_market_raw
        return base_fetch(url)

    market = acquire_historical_market_panel(
        start_date=support_start,
        end_date=target_day,
        fetcher=market_fetch,
        store_root=args.work_dir / "market-store",
        captured_at_utc=datetime.now(UTC),
        pause_seconds=0.0,
    )
    if int(market["session_count"]) < MIN_COMPLETED_MARKET_SESSIONS:
        raise AlphaContractError(
            "C002 support has too few completed market sessions"
        )
    if str(market["sessions"][-1]["session_date"]) != target_session:
        raise AlphaContractError("C002 market support does not end on target")
    if str(market["sessions"][-1]["udiff_sha256"]) != str(
        market_meta["raw_sha256"]
    ):
        raise AlphaContractError(
            "C002 market panel did not bind exact target bytes"
        )

    features = build_historical_feature_panel(sessions=market["sessions"])

    action_client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )

    def action_fetch(from_date: str, to_date: str):
        payload, raw = action_client.corporate_actions_with_raw(
            None,
            from_date=from_date,
            to_date=to_date,
        )
        query = urlencode(
            {
                "index": "equities",
                "from_date": from_date,
                "to_date": to_date,
            }
        )
        return (
            payload,
            raw,
            f"{action_client.CORPORATE_ACTION_ENDPOINT.url}?{query}",
        )

    actions = acquire_corporate_action_ledger(
        start_date=date.fromisoformat(str(market["sessions"][0]["session_date"])),
        end_date=target_day,
        fetcher=action_fetch,
        raw_dir=args.work_dir / "corporate-actions",
        chunk_days=31,
    )
    action_safe = filter_feature_panel_for_corporate_actions(
        feature_panel=features,
        market_panel=market,
        action_ledger=actions,
        lookback_sessions=60,
    )

    exposures = build_rm001_exposure_panel(
        feature_panel=action_safe,
        market_panel=market,
        action_ledger=actions,
    )
    history = build_rm001_factor_history(
        exposure_panel=exposures,
        market_panel=market,
        action_ledger=actions,
    )
    raw_state = build_rm001_risk_state(
        exposure_panel=exposures,
        factor_history=history,
        as_of_session=target_session,
    )
    calibrated_state = calibrate_v1_risk_state(raw_state)

    # Persist workflow support before final timing decision.
    support_payloads = (
        ("market-panel.json.gz", market),
        ("feature-panel.json.gz", features),
        ("corporate-action-ledger.json.gz", actions),
        ("action-safe-feature-panel.json.gz", action_safe),
        ("exposure-panel.json.gz", exposures),
        ("factor-history.json.gz", history),
        ("raw-v1-risk-state.json.gz", raw_state),
        ("cal1-risk-state.json.gz", calibrated_state),
    )
    for filename, payload in support_payloads:
        (args.work_dir / filename).write_bytes(canonical_gzip_json(payload))

    sealed = datetime.now(UTC)
    if sealed > cutoff:
        updated = append_forecast_entry(
            forecast_ledger,
            target_session_date=target_session,
            status="MISSED_0905_CUTOFF",
            sc001_attempt_sha256=str(attempt["attempt_sha256"]),
            observed_at_utc=sealed.isoformat(),
            reason="RISK_STATE_BUILD_COMPLETED_AFTER_FROZEN_CUTOFF",
        )
        _write_json(args.forecast_ledger, updated)
        result = {
            "state": "MISSED_0905_CUTOFF",
            "target_session_date": target_session,
            "sealed_at_utc": sealed.isoformat(),
            "cutoff_utc": cutoff.isoformat(),
            "raw_risk_state_sha256": raw_state["state_sha256"],
            "calibrated_risk_state_sha256": calibrated_state["state_sha256"],
            "changed": True,
            "forecast_ledger_sha256": updated["ledger_sha256"],
        }
        _write_json(args.work_dir / "late-result.json", result)
        print(json.dumps(result, sort_keys=True))
        return 0

    forecast = build_forecast_artifact(
        target_session_date=target_session,
        sc001_attempt=attempt,
        raw_risk_state=raw_state,
        calibrated_risk_state=calibrated_state,
        sealed_at_utc=sealed.isoformat(),
    )

    args.forecast_dir.mkdir(parents=True, exist_ok=True)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    forecast_path = args.forecast_dir / f"{target_session}-v1.json.gz"
    raw_state_path = args.state_dir / f"{target_session}-raw-v1.json.gz"
    cal_state_path = args.state_dir / f"{target_session}-cal1.json.gz"

    forecast_bytes = canonical_gzip_json(forecast)
    raw_state_bytes = canonical_gzip_json(raw_state)
    cal_state_bytes = canonical_gzip_json(calibrated_state)

    for path, raw in (
        (forecast_path, forecast_bytes),
        (raw_state_path, raw_state_bytes),
        (cal_state_path, cal_state_bytes),
    ):
        if path.exists() and path.read_bytes() != raw:
            raise AlphaContractError(f"C002 artifact path collision: {path}")
        path.write_bytes(raw)

    updated = append_forecast_entry(
        forecast_ledger,
        target_session_date=target_session,
        status="SEALED",
        sc001_attempt_sha256=str(attempt["attempt_sha256"]),
        observed_at_utc=sealed.isoformat(),
        forecast_artifact_path=str(forecast_path),
        forecast_artifact_sha256=forecast["artifact_sha256"],
        raw_risk_state_sha256=raw_state["state_sha256"],
        calibrated_risk_state_sha256=calibrated_state["state_sha256"],
    )
    _write_json(args.forecast_ledger, updated)
    validate_forecast_ledger(updated)

    result = {
        "state": "SEALED",
        "target_session_date": target_session,
        "sealed_at_utc": sealed.isoformat(),
        "forecast_artifact_sha256": forecast["artifact_sha256"],
        "forecast_file_sha256": sha256_bytes(forecast_bytes),
        "raw_risk_state_sha256": raw_state["state_sha256"],
        "raw_risk_state_file_sha256": sha256_bytes(raw_state_bytes),
        "calibrated_risk_state_sha256": calibrated_state["state_sha256"],
        "calibrated_risk_state_file_sha256": sha256_bytes(cal_state_bytes),
        "forecast_ledger_sha256": updated["ledger_sha256"],
        "probe_count": forecast["probe_count"],
        "common_identity_count": forecast["common_identity_count"],
        "support_hashes": {
            "market_panel_sha256": market["panel_sha256"],
            "feature_panel_sha256": features["panel_sha256"],
            "action_ledger_sha256": actions["ledger_sha256"],
            "action_safe_feature_panel_sha256": action_safe["panel_sha256"],
            "exposure_panel_sha256": exposures["panel_sha256"],
            "factor_history_sha256": history["history_sha256"],
        },
        "changed": True,
        "live_capital_allowed": False,
    }
    _write_json(args.work_dir / "sealed-result.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
