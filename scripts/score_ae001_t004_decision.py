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
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.alpha_t004 import validate_frozen_t004_models
from marketlab.alpha_t004_prospective import (
    append_t004_decision,
    build_t004_decision_artifact,
    eligible_sc001_attempt,
    validate_t004_decision_ledger,
)
from marketlab.alpha_t004_readiness import build_t004_readiness
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


def _persist_readiness(
    args: argparse.Namespace,
    *,
    session_date: str,
    state: str,
    sc001_attempt_sha256: str,
    support_market_panel_sha256: str | None = None,
    support_delivery_panel_sha256: str | None = None,
    delivery_warmup: dict | None = None,
    reason: str | None = None,
    decision_artifact_sha256: str | None = None,
    common_row_count: int | None = None,
) -> None:
    if args.readiness is None:
        return
    readiness = build_t004_readiness(
        session_date=session_date,
        state=state,
        sc001_attempt_sha256=sc001_attempt_sha256,
        support_market_panel_sha256=support_market_panel_sha256,
        support_delivery_panel_sha256=support_delivery_panel_sha256,
        delivery_warmup=delivery_warmup,
        reason=reason,
        decision_artifact_sha256=decision_artifact_sha256,
        common_row_count=common_row_count,
        source_workflow_run_id=args.workflow_run_id,
    )
    _write_json(args.readiness, readiness)


def _current_raw(attempt: dict, *, field: str) -> bytes:
    source = attempt[field]
    path = Path(str(source.get("raw_repo_path") or ""))
    if not path.exists():
        raise AlphaContractError(
            f"T004 current {field} source bytes are not anchored: {path}"
        )
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    observed = sha256_bytes(raw)
    expected = str(source.get("raw_sha256") or "")
    if observed != expected:
        raise AlphaContractError(
            f"T004 current {field} source hash mismatch"
        )
    return raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seal one prospective AE001 T004 model decision"
    )
    parser.add_argument("--session-date", type=date.fromisoformat, required=True)
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--decision-ledger", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--decision-dir", type=Path, required=True)
    parser.add_argument("--support-dir", type=Path, required=True)
    parser.add_argument("--readiness", type=Path)
    parser.add_argument("--workflow-run-id", type=int)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_text = args.session_date.isoformat()

    source_ledger = _load_json(args.sc001_ledger)
    validate_source_ledger(source_ledger)
    decision_ledger = _load_json(args.decision_ledger)
    validate_t004_decision_ledger(decision_ledger)
    if any(
        row["session_date"] == session_text
        for row in decision_ledger["decisions"]
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

    try:
        attempt = eligible_sc001_attempt(
            source_ledger,
            session_date=session_text,
        )
    except AlphaContractError as exc:
        if "no SC001 eligible" in str(exc):
            print(
                json.dumps(
                    {
                        "state": "SC001_NOT_ELIGIBLE",
                        "session_date": session_text,
                        "changed": False,
                    },
                    sort_keys=True,
                )
            )
            return 0
        raise

    models = _load_json(args.models)
    validate_frozen_t004_models(models)
    current_market_raw = _current_raw(attempt, field="market")
    current_delivery_raw = _current_raw(attempt, field="delivery")

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
            "T004 support acquisition found fewer than 60 market sessions"
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
    warmup = delivery_source_warmup_readiness(
        prior_delivery["sessions"]
    )
    if warmup["state"] != "READY":
        report = {
            "state": "DELIVERY_SOURCE_WARMUP_BLOCKED",
            "session_date": session_text,
            "sc001_attempt_sha256": attempt["attempt_sha256"],
            "support_market_panel_sha256": prior_market["panel_sha256"],
            "support_delivery_panel_sha256": prior_delivery["panel_sha256"],
            "delivery_warmup": warmup,
            "changed": False,
            "live_capital_allowed": False,
        }
        _write_json(
            args.support_dir / f"t004-warmup-{session_text}.json",
            report,
        )
        _persist_readiness(
            args,
            session_date=session_text,
            state="DELIVERY_SOURCE_WARMUP_BLOCKED",
            sc001_attempt_sha256=str(attempt["attempt_sha256"]),
            support_market_panel_sha256=str(prior_market["panel_sha256"]),
            support_delivery_panel_sha256=str(prior_delivery["panel_sha256"]),
            delivery_warmup=warmup,
        )
        print(json.dumps(report, sort_keys=True))
        return 0

    action_client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    action_from = date.fromisoformat(
        str(prior_market_sessions[0]["session_date"])
    ).strftime("%d-%m-%Y")
    action_to = args.session_date.strftime("%d-%m-%Y")
    action_payload, action_raw = action_client.corporate_actions_with_raw(
        None,
        from_date=action_from,
        to_date=action_to,
    )

    try:
        artifact = build_t004_decision_artifact(
            session_date=session_text,
            sc001_attempt=attempt,
            prior_market_sessions=prior_market_sessions,
            current_market_raw=current_market_raw,
            prior_delivery_sessions=prior_delivery["sessions"],
            current_delivery_raw=current_delivery_raw,
            corporate_action_payload=action_payload,
            corporate_action_raw=action_raw,
            frozen_models=models,
            sealed_at_utc=None,
        )
    except AlphaContractError as exc:
        message = str(exc)
        if (
            "common row count below frozen minimum" in message
            or "prediction sealing missed decision cutoff" in message
        ):
            report = {
                "state": "SESSION_EXCLUDED",
                "session_date": session_text,
                "reason": message,
                "sc001_attempt_sha256": attempt["attempt_sha256"],
                "support_market_panel_sha256": prior_market["panel_sha256"],
                "support_delivery_panel_sha256": prior_delivery["panel_sha256"],
                "changed": False,
            }
            _write_json(
                args.support_dir / f"t004-excluded-{session_text}.json",
                report,
            )
            _persist_readiness(
                args,
                session_date=session_text,
                state="SESSION_EXCLUDED",
                sc001_attempt_sha256=str(attempt["attempt_sha256"]),
                support_market_panel_sha256=str(prior_market["panel_sha256"]),
                support_delivery_panel_sha256=str(prior_delivery["panel_sha256"]),
                reason=message,
            )
            print(json.dumps(report, sort_keys=True))
            return 0
        raise

    artifact_bytes = canonical_gzip_json(artifact)
    artifact_path = (
        args.decision_dir / f"{session_text}-v1.json.gz"
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    if artifact_path.exists() and artifact_path.read_bytes() != artifact_bytes:
        raise AlphaContractError(
            f"T004 decision artifact path collision: {artifact_path}"
        )
    artifact_path.write_bytes(artifact_bytes)

    updated = append_t004_decision(
        decision_ledger,
        decision_artifact=artifact,
        artifact_path=str(artifact_path),
    )
    _write_json(args.decision_ledger, updated)
    validate_t004_decision_ledger(updated)

    _persist_readiness(
        args,
        session_date=session_text,
        state="SEALED",
        sc001_attempt_sha256=str(attempt["attempt_sha256"]),
        support_market_panel_sha256=str(prior_market["panel_sha256"]),
        support_delivery_panel_sha256=str(prior_delivery["panel_sha256"]),
        decision_artifact_sha256=str(artifact["artifact_sha256"]),
        common_row_count=int(artifact["common_row_count"]),
    )

    support_manifest = {
        "schema_version": 1,
        "session_date": session_text,
        "sc001_attempt_sha256": attempt["attempt_sha256"],
        "support_market_panel_sha256": prior_market["panel_sha256"],
        "support_delivery_panel_sha256": prior_delivery["panel_sha256"],
        "corporate_action_raw_sha256": sha256_bytes(action_raw),
        "decision_artifact_sha256": artifact["artifact_sha256"],
        "decision_artifact_file_sha256": sha256_bytes(artifact_bytes),
        "decision_ledger_sha256": updated["ledger_sha256"],
        "common_row_count": artifact["common_row_count"],
        "sealed_at_utc": artifact["sealed_at_utc"],
        "live_capital_allowed": False,
    }
    _write_json(
        args.support_dir / f"t004-decision-{session_text}-manifest.json",
        support_manifest,
    )
    print(
        json.dumps(
            {
                "state": "SEALED",
                "session_date": session_text,
                "changed": True,
                **support_manifest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
