from __future__ import annotations

import argparse
import gzip
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.alpha_acquisition import (
    acquire_historical_market_panel,
    http_fetcher,
)
from marketlab.alpha_delivery import acquire_historical_delivery_panel
from marketlab.alpha_delivery_readiness import delivery_source_warmup_readiness
from marketlab.alpha_history import canonical_gzip_json
from marketlab.alpha_prospective_futures_sources import (
    validate_futures_source_ledger,
)
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.alpha_t004_prospective import eligible_sc001_attempt
from marketlab.alpha_t006 import validate_frozen_t006_models
from marketlab.alpha_t012 import (
    append_t012_decision,
    build_t012_decision_artifact,
    eligible_sc002_t012_attempt,
    session_is_post_timing_basis,
    t012_cutoff_utc,
    validate_t012_cutoff_freeze,
    validate_t012_decision_ledger,
)
from marketlab.events import sha256_bytes
from marketlab.nse import NSEClient


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


def _raw_from_source(source: dict[str, object], *, label: str) -> bytes:
    path = Path(str(source.get("raw_repo_path") or ""))
    if not path.exists():
        raise AlphaContractError(f"T012 {label} bytes missing: {path}")
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    expected = str(source.get("raw_sha256") or "")
    if sha256_bytes(raw) != expected:
        raise AlphaContractError(f"T012 {label} source hash mismatch: {path}")
    return raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seal one prospective AE001 T012 late-futures decision"
    )
    parser.add_argument("--session-date", type=date.fromisoformat, required=True)
    parser.add_argument("--cutoff-freeze", type=Path, required=True)
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--sc002-ledger", type=Path, required=True)
    parser.add_argument("--decision-ledger", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--decision-dir", type=Path, required=True)
    parser.add_argument("--support-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_text = args.session_date.isoformat()

    cutoff = _load_json(args.cutoff_freeze)
    validate_t012_cutoff_freeze(cutoff)
    if cutoff["state"] != "FROZEN":
        print(
            json.dumps(
                {
                    "state": "CUTOFF_NOT_FROZEN",
                    "session_date": session_text,
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if not session_is_post_timing_basis(session_text, cutoff):
        print(
            json.dumps(
                {
                    "state": "TIMING_BASIS_OR_PREACTIVATION_SESSION",
                    "session_date": session_text,
                    "latest_timing_basis_session": cutoff[
                        "latest_timing_basis_session"
                    ],
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    decisions = _load_json(args.decision_ledger)
    validate_t012_decision_ledger(decisions)
    if any(
        row["session_date"] == session_text
        for row in decisions["decisions"]
    ):
        print(
            json.dumps(
                {
                    "state": "ALREADY_SEALED",
                    "session_date": session_text,
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    now = datetime.now(UTC)
    session_cutoff = t012_cutoff_utc(session_text, cutoff)
    if now > session_cutoff:
        print(
            json.dumps(
                {
                    "state": "MISSED_FROZEN_CUTOFF_NO_BACKFILL",
                    "session_date": session_text,
                    "observed_at_utc": now.isoformat(),
                    "decision_cutoff_utc": session_cutoff.isoformat(),
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    sc001 = _load_json(args.sc001_ledger)
    sc002 = _load_json(args.sc002_ledger)
    validate_source_ledger(sc001)
    validate_futures_source_ledger(sc002)

    try:
        sc001_attempt = eligible_sc001_attempt(
            sc001,
            session_date=session_text,
        )
    except AlphaContractError as exc:
        if "no SC001 eligible" in str(exc):
            print(
                json.dumps(
                    {
                        "state": "SC001_NOT_ELIGIBLE",
                        "session_date": session_text,
                        "reason": str(exc),
                        "changed": False,
                    },
                    sort_keys=True,
                )
            )
            return 0
        raise

    try:
        sc002_attempt = eligible_sc002_t012_attempt(
            sc002,
            session_date=session_text,
            cutoff_freeze=cutoff,
        )
    except AlphaContractError as exc:
        if "no SC002 READY source" in str(exc):
            print(
                json.dumps(
                    {
                        "state": "FUTURES_NOT_READY_BY_T012_CUTOFF_YET",
                        "session_date": session_text,
                        "reason": str(exc),
                        "decision_cutoff_utc": session_cutoff.isoformat(),
                        "changed": False,
                    },
                    sort_keys=True,
                )
            )
            return 0
        raise

    models = _load_json(args.models)
    validate_frozen_t006_models(models)

    current_market_raw = _raw_from_source(
        sc001_attempt["market"],
        label="current market",
    )
    current_delivery_raw = _raw_from_source(
        sc001_attempt["delivery"],
        label="current delivery",
    )
    current_futures_raw = _raw_from_source(
        sc002_attempt["futures"],
        label="current futures",
    )

    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    support_start = args.session_date - timedelta(days=120)
    support_end = args.session_date - timedelta(days=1)
    prior_market = acquire_historical_market_panel(
        start_date=support_start,
        end_date=support_end,
        fetcher=fetch,
        store_root=args.support_dir,
        captured_at_utc=datetime.now(UTC),
        pause_seconds=0.0,
    )
    if prior_market["session_count"] < 60:
        raise AlphaContractError(
            "T012 support acquisition found fewer than 60 market sessions"
        )
    prior_market_sessions = prior_market["sessions"][-60:]

    prior_delivery_dates = [
        str(row["session_date"])
        for row in prior_market_sessions[-20:]
    ]
    prior_delivery = acquire_historical_delivery_panel(
        session_dates=prior_delivery_dates,
        fetcher=fetch,
        store_root=args.support_dir,
        captured_at_utc=datetime.now(UTC),
    )
    warmup = delivery_source_warmup_readiness(prior_delivery["sessions"])
    if warmup["state"] != "READY":
        report = {
            "state": "DELIVERY_SOURCE_WARMUP_BLOCKED",
            "session_date": session_text,
            "cutoff_freeze_sha256": cutoff["freeze_sha256"],
            "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
            "sc002_attempt_sha256": sc002_attempt["attempt_sha256"],
            "support_market_panel_sha256": prior_market["panel_sha256"],
            "support_delivery_panel_sha256": prior_delivery["panel_sha256"],
            "delivery_warmup": warmup,
            "changed": False,
            "live_capital_allowed": False,
        }
        args.support_dir.mkdir(parents=True, exist_ok=True)
        _write_json(
            args.support_dir / f"t012-warmup-{session_text}.json",
            report,
        )
        print(json.dumps(report, sort_keys=True))
        return 0

    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    action_from = date.fromisoformat(
        str(prior_market_sessions[0]["session_date"])
    ).strftime("%d-%m-%Y")
    action_to = args.session_date.strftime("%d-%m-%Y")
    action_payload, action_raw = client.corporate_actions_with_raw(
        None,
        from_date=action_from,
        to_date=action_to,
    )
    action_raw_sha256 = sha256_bytes(action_raw)
    args.support_dir.mkdir(parents=True, exist_ok=True)
    action_raw_path = (
        args.support_dir / f"corporate-actions-{action_raw_sha256}.json"
    )
    if action_raw_path.exists() and action_raw_path.read_bytes() != action_raw:
        raise AlphaContractError(
            f"T012 corporate-action raw path collision: {action_raw_path}"
        )
    action_raw_path.write_bytes(action_raw)

    try:
        artifact = build_t012_decision_artifact(
            session_date=session_text,
            cutoff_freeze=cutoff,
            sc001_attempt=sc001_attempt,
            sc002_attempt=sc002_attempt,
            prior_market_sessions=prior_market_sessions,
            current_market_raw=current_market_raw,
            prior_delivery_sessions=prior_delivery["sessions"],
            current_delivery_raw=current_delivery_raw,
            current_futures_raw=current_futures_raw,
            corporate_action_payload=action_payload,
            corporate_action_raw=action_raw,
            frozen_models=models,
            sealed_at_utc=None,
        )
    except AlphaContractError as exc:
        message = str(exc)
        if (
            "common row count below frozen minimum" in message
            or "prediction sealing missed frozen late-evening cutoff" in message
        ):
            report = {
                "state": "SESSION_EXCLUDED",
                "session_date": session_text,
                "reason": message,
                "cutoff_freeze_sha256": cutoff["freeze_sha256"],
                "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
                "sc002_attempt_sha256": sc002_attempt["attempt_sha256"],
                "support_market_panel_sha256": prior_market["panel_sha256"],
                "support_delivery_panel_sha256": prior_delivery["panel_sha256"],
                "changed": False,
                "live_capital_allowed": False,
            }
            _write_json(
                args.support_dir / f"t012-excluded-{session_text}.json",
                report,
            )
            print(json.dumps(report, sort_keys=True))
            return 0
        raise

    artifact_bytes = canonical_gzip_json(artifact)
    artifact_path = args.decision_dir / f"{session_text}-v1.json.gz"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    if artifact_path.exists() and artifact_path.read_bytes() != artifact_bytes:
        raise AlphaContractError(
            f"T012 decision artifact path collision: {artifact_path}"
        )
    artifact_path.write_bytes(artifact_bytes)

    updated = append_t012_decision(
        decisions,
        decision_artifact=artifact,
        artifact_path=str(artifact_path),
    )
    _write_json(args.decision_ledger, updated)
    validate_t012_decision_ledger(updated)

    report = {
        "schema_version": 1,
        "state": "SEALED",
        "session_date": session_text,
        "decision_cutoff_utc": artifact["decision_cutoff_utc"],
        "cutoff_freeze_sha256": cutoff["freeze_sha256"],
        "source_timing_summary_sha256": cutoff[
            "source_timing_summary_sha256"
        ],
        "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
        "sc002_attempt_sha256": sc002_attempt["attempt_sha256"],
        "support_market_panel_sha256": prior_market["panel_sha256"],
        "support_delivery_panel_sha256": prior_delivery["panel_sha256"],
        "corporate_action_raw_sha256": action_raw_sha256,
        "corporate_action_raw_path": str(action_raw_path),
        "decision_artifact_sha256": artifact["artifact_sha256"],
        "decision_artifact_file_sha256": sha256_bytes(artifact_bytes),
        "decision_ledger_sha256": updated["ledger_sha256"],
        "common_row_count": artifact["common_row_count"],
        "sealed_at_utc": artifact["sealed_at_utc"],
        "changed": True,
        "live_capital_allowed": False,
    }
    _write_json(
        args.support_dir / f"t012-decision-{session_text}-manifest.json",
        report,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
