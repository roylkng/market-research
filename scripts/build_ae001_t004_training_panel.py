from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_delivery import (
    acquire_historical_delivery_panel,
    augment_feature_panel_with_delivery,
)
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)
from marketlab.events import sha256_bytes

TRIAL_ID = "AE001-T004"
TRIAL_STATUS = "FROZEN_BEFORE_FIRST_ELIGIBLE_DECISION_SESSION"
MODEL_PROTOCOL_ID = "AE001-T004-P1"
SOURCE_END_DATE = "2026-09-25"


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build frozen historical training inputs for AE001 T004"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--trial-ledger", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trials = _load_json(args.trial_ledger)
    registration = require_unopened_registered_trial(
        trials,
        trial_id=TRIAL_ID,
        required_status=TRIAL_STATUS,
    )
    protocol = require_protocol_amendment(
        trials,
        trial_id=TRIAL_ID,
        protocol_id=MODEL_PROTOCOL_ID,
    )
    if str(protocol["payload"].get("source_end_date")) != SOURCE_END_DATE:
        raise ValueError("T004 P1 source end date differs from frozen builder")

    market_bytes = args.market_panel.read_bytes()
    feature_bytes = args.feature_panel.read_bytes()
    market = load_canonical_gzip_json(market_bytes)
    features = load_canonical_gzip_json(feature_bytes)
    if str(market.get("end_date")) != SOURCE_END_DATE:
        raise ValueError("T004 market panel exceeds frozen source end date")

    sessions = market.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("T004 market sessions are required")
    if str(sessions[-1]["session_date"]) != SOURCE_END_DATE:
        raise ValueError("T004 final market session differs from frozen cutoff")
    session_dates = [str(row["session_date"]) for row in sessions]

    captured = datetime.now(UTC)
    delivery = acquire_historical_delivery_panel(
        session_dates=session_dates,
        fetcher=http_fetcher(
            attempts=args.attempts,
            timeout=args.timeout_seconds,
        ),
        store_root=args.store,
        captured_at_utc=captured,
    )
    augmented = augment_feature_panel_with_delivery(
        feature_panel=features,
        market_panel=market,
        delivery_panel=delivery,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    delivery_bytes = canonical_gzip_json(delivery)
    augmented_bytes = canonical_gzip_json(augmented)
    (args.output / "delivery-panel.json.gz").write_bytes(delivery_bytes)
    (args.output / "training-feature-panel.json.gz").write_bytes(augmented_bytes)

    manifest = {
        "schema_version": 1,
        "trial_id": TRIAL_ID,
        "model_protocol_id": MODEL_PROTOCOL_ID,
        "trial_registration_event_sha256": registration["event_sha256"],
        "model_protocol_event_sha256": protocol["event_sha256"],
        "trial_ledger_sha256": trials["ledger_sha256"],
        "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
        "source_end_date": SOURCE_END_DATE,
        "market_panel_sha256": market["panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "base_feature_panel_sha256": features["panel_sha256"],
        "base_feature_artifact_sha256": sha256_bytes(feature_bytes),
        "delivery_panel_sha256": delivery["panel_sha256"],
        "delivery_artifact_sha256": sha256_bytes(delivery_bytes),
        "training_feature_panel_sha256": augmented["panel_sha256"],
        "training_feature_artifact_sha256": sha256_bytes(augmented_bytes),
        "delivery_excluded_source_quality_sessions": delivery[
            "excluded_source_quality_sessions"
        ],
        "delivery_feature_row_count": augmented["feature_row_count"],
        "historical_archives_captured_prospectively": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
