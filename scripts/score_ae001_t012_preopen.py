"""Seal a causal D -> next-trading-session N T012 prediction before N 08:30 IST.

Runs only for the latest completed frozen NSE session. Never backfills.
"""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.alpha_acquisition import acquire_historical_market_panel, http_fetcher
from marketlab.alpha_delivery import acquire_historical_delivery_panel
from marketlab.alpha_delivery_readiness import delivery_source_warmup_readiness
from marketlab.alpha_history import canonical_gzip_json
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.alpha_sc003_preopen import validate_sc003_ledger
from marketlab.alpha_t012_decisions import (
    append_t012_decision,
    build_t012_decision_artifact,
    reseal_t012_decision_artifact,
    validate_t012_decision_ledger,
)
from marketlab.alpha_t012_preopen import (
    FIRST_FEATURE_SESSION,
    admit_t012_preopen,
    require_t012_registration,
)
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.events import sha256_bytes
from marketlab.nse import NSEClient


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _raw(source: dict, label: str) -> bytes:
    path = Path(str(source.get("raw_repo_path") or ""))
    if not path.is_file():
        raise AlphaContractError(f"T012 {label} raw source absent: {path}")
    stored = path.read_bytes()
    raw = gzip.decompress(stored) if path.suffix == ".gz" else stored
    if sha256_bytes(raw) != source.get("raw_sha256"):
        raise AlphaContractError(f"T012 {label} raw source hash mismatch: {path}")
    return raw


def _latest_closed_session(calendar: object, now: datetime) -> str | None:
    closed = [
        session.session_date
        for session in calendar.sessions
        if datetime.fromisoformat(session.close_timestamp_utc).astimezone(UTC)
        <= now
    ]
    return max(closed) if closed else None


def _status(state: str, *, date_text: str | None, reason: str = "") -> int:
    print(
        json.dumps(
            {
                "trial_id": "AE001-T012",
                "state": state,
                "feature_session": date_text,
                "reason": reason,
                "changed": False,
                "live_capital_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--calendar",
        type=Path,
        default=Path(
            "research/prospective/calendars/FY27-Q2-2026-09-06/"
            "NSE-CM-FY27Q2-v1.json"
        ),
    )
    p.add_argument(
        "--sc001-ledger", type=Path,
        default=Path("research/prospective/ae001-sc001/source-ledger.json"),
    )
    p.add_argument(
        "--sc003-ledger", type=Path,
        default=Path("research/prospective/ae001-sc003/source-ledger.json"),
    )
    p.add_argument(
        "--trial-ledger", type=Path,
        default=Path("research/ae001/trial-ledger.json"),
    )
    p.add_argument(
        "--rta-manifest", type=Path,
        default=Path("research/rta001-trials-v1.json"),
    )
    p.add_argument(
        "--models", type=Path,
        default=Path("research/prospective/ae001-t006/frozen-models-v1.json"),
    )
    p.add_argument(
        "--decision-ledger", type=Path,
        default=Path("research/prospective/ae001-t012/decision-ledger.json"),
    )
    p.add_argument(
        "--decision-dir", type=Path,
        default=Path("research/prospective/ae001-t012/decisions"),
    )
    p.add_argument(
        "--work-dir", type=Path, default=Path("reports/ae001-t012-preopen")
    )
    p.add_argument("--attempts", type=int, default=4)
    p.add_argument("--timeout-seconds", type=float, default=30)
    return p.parse_args()


def main() -> int:
    args = _args()
    calendar = load_calendar_snapshot(args.calendar)
    feature = _latest_closed_session(calendar, datetime.now(UTC))
    if feature is None or feature < FIRST_FEATURE_SESSION:
        return _status("BEFORE_PROSPECTIVE_START", date_text=feature)

    sc001 = _load(args.sc001_ledger)
    sc003 = _load(args.sc003_ledger)
    trials = _load(args.trial_ledger)
    accounting = _load(args.rta_manifest)
    models = _load(args.models)
    ledger = _load(args.decision_ledger)
    validate_source_ledger(sc001)
    validate_sc003_ledger(sc003)
    validate_t012_decision_ledger(ledger)
    require_t012_registration(
        trial_ledger=trials,
        rta_manifest=accounting,
        sc003_ledger=sc003,
        calendar=calendar,
        frozen_models=models,
    )

    if any(row["session_date"] == feature for row in ledger["decisions"]):
        return _status("ALREADY_SEALED", date_text=feature)
    common = {
        "feature_session": feature,
        "sc001_ledger": sc001,
        "sc003_ledger": sc003,
        "trial_ledger": trials,
        "rta_manifest": accounting,
        "calendar": calendar,
        "frozen_models": models,
    }
    try:
        before = admit_t012_preopen(
            sealed_at_utc=datetime.now(UTC).isoformat(),
            **common,
        )
    except AlphaContractError as exc:
        reason = str(exc)
        if "requires one linked timely D futures source" in reason:
            return _status("SOURCE_NOT_READY", date_text=feature, reason=reason)
        if "missed N cutoff" in reason:
            return _status("CUTOFF_MISSED", date_text=feature, reason=reason)
        raise

    cash = next(
        row for row in sc001["attempts"]
        if row["attempt_sha256"] == before["sc001_attempt_sha256"]
    )
    futures = next(
        row for row in sc003["attempts"]
        if row["attempt_sha256"] == before["sc003_attempt_sha256"]
    )
    market_raw = _raw(cash["market"], "D cash")
    delivery_raw = _raw(cash["delivery"], "D delivery")
    futures_raw = _raw(futures, "D futures")

    fetch = http_fetcher(
        attempts=args.attempts, timeout=args.timeout_seconds
    )
    support = acquire_historical_market_panel(
        start_date=date.fromisoformat(feature) - timedelta(days=120),
        end_date=date.fromisoformat(feature) - timedelta(days=1),
        fetcher=fetch,
        store_root=args.work_dir,
        captured_at_utc=datetime.now(UTC),
        pause_seconds=0.0,
    )
    if support["session_count"] < 60:
        return _status(
            "INSUFFICIENT_MARKET_WARMUP", date_text=feature,
            reason="fewer than 60 verified market sessions",
        )
    prior_market = support["sessions"][-60:]
    prior_delivery = acquire_historical_delivery_panel(
        session_dates=[
            str(row["session_date"]) for row in prior_market[-20:]
        ],
        fetcher=fetch,
        store_root=args.work_dir,
        captured_at_utc=datetime.now(UTC),
    )
    warmup = delivery_source_warmup_readiness(prior_delivery["sessions"])
    if warmup["state"] != "READY":
        report = {
            "trial_id": "AE001-T012",
            "state": "DELIVERY_WARMUP_BLOCKED",
            "feature_session": feature,
            "warmup": warmup,
            "support_market_sha256": support["panel_sha256"],
            "support_delivery_sha256": prior_delivery["panel_sha256"],
            "live_capital_allowed": False,
        }
        _save(args.work_dir / f"warmup-{feature}.json", report)
        return _status("DELIVERY_WARMUP_BLOCKED", date_text=feature)

    client = NSEClient(
        timeout=args.timeout_seconds, attempts=args.attempts
    )
    action_payload, action_raw = client.corporate_actions_with_raw(
        None,
        from_date=date.fromisoformat(
            str(prior_market[0]["session_date"])
        ).strftime("%d-%m-%Y"),
        to_date=date.fromisoformat(feature).strftime("%d-%m-%Y"),
    )
    action_sha = sha256_bytes(action_raw)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.work_dir / f"corporate-actions-{action_sha}.json"
    if raw_path.exists() and raw_path.read_bytes() != action_raw:
        raise AlphaContractError("T012 source bytes changed under same SHA")
    raw_path.write_bytes(action_raw)

    try:
        artifact = build_t012_decision_artifact(
            admission=before,
            prior_market_sessions=prior_market,
            current_market_raw=market_raw,
            prior_delivery_sessions=prior_delivery["sessions"],
            current_delivery_raw=delivery_raw,
            current_futures_raw=futures_raw,
            corporate_action_payload=action_payload,
            corporate_action_raw=action_raw,
            frozen_models=models,
        )
    except AlphaContractError as exc:
        if "common row count below frozen minimum" in str(exc):
            return _status(
                "INSUFFICIENT_COMMON_STOCKS",
                date_text=feature, reason=str(exc),
            )
        raise
    try:
        # Clock seal happens AFTER all source acquisition and scoring.
        after = admit_t012_preopen(
            sealed_at_utc=datetime.now(UTC).isoformat(),
            **common,
        )
        artifact = reseal_t012_decision_artifact(
            artifact, final_admission=after
        )
    except AlphaContractError as exc:
        if "missed N cutoff" in str(exc):
            return _status(
                "CUTOFF_MISSED_AFTER_COMPUTATION",
                date_text=feature, reason=str(exc),
            )
        raise

    artifact_bytes = canonical_gzip_json(artifact)
    path = args.decision_dir / f"{feature}-v1.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != artifact_bytes:
        raise AlphaContractError(f"T012 immutable artifact path collision: {path}")
    path.write_bytes(artifact_bytes)
    updated = append_t012_decision(
        ledger, artifact=artifact, artifact_path=str(path)
    )
    _save(args.decision_ledger, updated)
    validate_t012_decision_ledger(updated)
    _save(
        args.work_dir / f"prediction-{feature}-manifest.json",
        {
            "trial_id": "AE001-T012",
            "state": "SEALED_LOCALLY_PENDING_REMOTE_ANCHOR",
            "feature_session": feature,
            "entry_session": artifact["entry_session"],
            "sealed_at_utc": artifact["sealed_at_utc"],
            "decision_cutoff_utc": artifact["decision_cutoff_utc"],
            "common_stock_count": artifact["common_row_count"],
            "artifact_sha256": artifact["artifact_sha256"],
            "artifact_file_sha256": sha256_bytes(artifact_bytes),
            "ledger_sha256": updated["ledger_sha256"],
            "live_capital_allowed": False,
        },
    )
    print(
        json.dumps(
            {
                "state": "SEALED_LOCALLY_PENDING_REMOTE_ANCHOR",
                "feature_session": feature,
                "artifact_sha256": artifact["artifact_sha256"],
                "common_stock_count": artifact["common_row_count"],
                "changed": True,
                "live_capital_allowed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
