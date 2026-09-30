from __future__ import annotations

import argparse
import gzip
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_acquisition import acquire_historical_market_panel, http_fetcher
from marketlab.alpha_history import canonical_gzip_json
from marketlab.alpha_t006_outcomes import (
    append_t006_outcome,
    build_t006_horizon_outcome,
    finalize_t006_results,
    validate_t006_outcome_ledger,
)
from marketlab.alpha_t006_prospective import validate_t006_decision_ledger
from marketlab.alpha_trials import validate_trial_ledger
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


def _load_gzip_artifact(path: Path, expected_sha: str, *, label: str) -> dict:
    payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    stored = str(payload.get("artifact_sha256") or "")
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    if stored != digest(unsigned) or stored != expected_sha:
        raise AlphaContractError(f"{label} artifact hash mismatch: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Advance AE001 T006 outcomes and frozen result gates"
    )
    parser.add_argument("--as-of-date", type=date.fromisoformat, required=True)
    parser.add_argument("--decision-ledger", type=Path, required=True)
    parser.add_argument("--outcome-ledger", type=Path, required=True)
    parser.add_argument("--trial-ledger", type=Path, required=True)
    parser.add_argument("--outcome-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    decisions = _load_json(args.decision_ledger)
    validate_t006_decision_ledger(decisions)
    outcomes = _load_json(args.outcome_ledger)
    validate_t006_outcome_ledger(outcomes)
    trials = _load_json(args.trial_ledger)
    validate_trial_ledger(trials)

    if not decisions["decisions"]:
        print(json.dumps({"state":"NO_DECISIONS","changed":False},sort_keys=True))
        return 0

    earliest = min(
        date.fromisoformat(str(row["session_date"]))
        for row in decisions["decisions"]
    )
    start = earliest + timedelta(days=1)
    if args.as_of_date < start:
        print(json.dumps({"state":"NO_MATURITY_WINDOW","changed":False},sort_keys=True))
        return 0

    args.work_dir.mkdir(parents=True, exist_ok=True)
    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    market = acquire_historical_market_panel(
        start_date=start,
        end_date=args.as_of_date,
        fetcher=fetch,
        store_root=args.work_dir,
        captured_at_utc=datetime.now(UTC),
        pause_seconds=0.0,
    )

    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    from_text = start.strftime("%d-%m-%Y")
    to_text = args.as_of_date.strftime("%d-%m-%Y")
    action_payload, action_raw = client.corporate_actions_with_raw(
        None,
        from_date=from_text,
        to_date=to_text,
    )
    action_raw_sha256 = sha256_bytes(action_raw)
    action_raw_path = (
        args.work_dir
        / f"corporate-actions-{action_raw_sha256}.json"
    )
    if action_raw_path.exists() and action_raw_path.read_bytes() != action_raw:
        raise AlphaContractError(
            f"T006 outcome corporate-action raw path collision: {action_raw_path}"
        )
    action_raw_path.write_bytes(action_raw)
    query = urlencode(
        {
            "index": "equities",
            "from_date": from_text,
            "to_date": to_text,
        }
    )
    action_source_url = f"{client.CORPORATE_ACTION_ENDPOINT.url}?{query}"

    existing = {
        (str(row["decision_session"]), int(row["horizon_sessions"]))
        for row in outcomes["outcomes"]
    }
    changed = False
    newly_matured = []

    for decision_row in decisions["decisions"]:
        decision_session = str(decision_row["session_date"])
        decision = _load_gzip_artifact(
            Path(str(decision_row["artifact_path"])),
            str(decision_row["artifact_sha256"]),
            label="T006 decision",
        )
        available = [
            row
            for row in market["sessions"]
            if str(row["session_date"]) > decision_session
        ]
        for horizon in (1, 5):
            key = (decision_session, horizon)
            if key in existing or len(available) < horizon:
                continue
            artifact = build_t006_horizon_outcome(
                decision_artifact=decision,
                market_sessions=market["sessions"],
                corporate_action_payload=action_payload,
                corporate_action_raw=action_raw,
                horizon_sessions=horizon,
            )
            path = args.outcome_dir / f"{decision_session}-h{horizon}-v1.json.gz"
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = canonical_gzip_json(artifact)
            if path.exists() and path.read_bytes() != payload:
                raise AlphaContractError(
                    f"T006 outcome artifact path collision: {path}"
                )
            path.write_bytes(payload)
            outcomes = append_t006_outcome(
                outcomes,
                outcome_artifact=artifact,
                artifact_path=str(path),
            )
            existing.add(key)
            changed = True
            newly_matured.append(
                {
                    "decision_session": decision_session,
                    "horizon_sessions": horizon,
                    "artifact_sha256": artifact["artifact_sha256"],
                    "valid_paired_ic": artifact["valid_paired_ic"],
                }
            )

    if changed:
        _write_json(args.outcome_ledger, outcomes)

    artifacts = [
        _load_gzip_artifact(
            Path(str(row["artifact_path"])),
            str(row["artifact_sha256"]),
            label="T006 outcome",
        )
        for row in outcomes["outcomes"]
    ]
    updated_trials, emitted = finalize_t006_results(
        trial_ledger=trials,
        decision_ledger=decisions,
        outcome_ledger=outcomes,
        outcome_artifacts=artifacts,
        recorded_at_utc=datetime.now(UTC).isoformat(),
    )
    if updated_trials != trials:
        _write_json(args.trial_ledger, updated_trials)
        changed = True

    report = {
        "schema_version": 1,
        "state": "UPDATED" if changed else "NO_NEW_MATURE_OUTCOME",
        "as_of_date": args.as_of_date.isoformat(),
        "decision_count": decisions["decision_count"],
        "outcome_count": outcomes["outcome_count"],
        "newly_matured": newly_matured,
        "result_events_emitted": [
            {
                "event_sha256": event["event_sha256"],
                "result_kind": event["payload"].get("result_kind"),
                "status": event["payload"].get("status"),
            }
            for event in emitted
        ],
        "market_panel_sha256": market["panel_sha256"],
        "corporate_action_raw_sha256": action_raw_sha256,
        "corporate_action_raw_path": str(action_raw_path),
        "corporate_action_source_url": action_source_url,
        "outcome_ledger_sha256": outcomes["ledger_sha256"],
        "trial_ledger_sha256": updated_trials["ledger_sha256"],
        "changed": changed,
        "live_capital_allowed": False,
    }
    _write_json(args.work_dir / "advance-report.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
