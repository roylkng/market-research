from __future__ import annotations

import argparse
import copy
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_acquisition import acquire_historical_market_panel, http_fetcher
from marketlab.alpha_corporate_actions import (
    acquire_corporate_action_ledger,
    action_index,
    blocked_actions,
)
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.events import sha256_bytes
from marketlab.nse import NSEClient
from marketlab.rm001 import _market_maps
from marketlab.rm001_c002 import (
    append_outcome_entry,
    build_outcome_artifact,
    prospective_summary,
    validate_forecast_ledger,
    validate_outcome_ledger,
)


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


def _exact_market_raw(attempt: dict) -> bytes:
    meta = attempt["market"]
    path = Path(str(meta["raw_repo_path"]))
    if not path.exists():
        raise AlphaContractError(
            f"C002 exact market source is missing: {path}"
        )
    raw = path.read_bytes()
    if sha256_bytes(raw) != str(meta["raw_sha256"]):
        raise AlphaContractError("C002 exact market source hash mismatch")
    return raw


def _find_attempt_by_sha(
    source_ledger: dict,
    attempt_sha256: str,
) -> dict:
    matches = [
        row
        for row in source_ledger.get("attempts", [])
        if row.get("attempt_sha256") == attempt_sha256
    ]
    if len(matches) != 1:
        raise AlphaContractError(
            "C002 cannot resolve exact forecast SC001 attempt"
        )
    return matches[0]


def _next_later_eligible_attempt(
    source_ledger: dict,
    target_session: str,
) -> dict | None:
    rows = [
        row
        for row in source_ledger.get("attempts", [])
        if row.get("eligible_before_cutoff") is True
        and str(row.get("session_date") or "") > target_session
    ]
    rows.sort(
        key=lambda row: (
            str(row["session_date"]),
            str(row["captured_at_utc"]),
            int(row["seq"]),
        )
    )
    unique = {}
    for row in rows:
        unique.setdefault(str(row["session_date"]), row)
    return unique[min(unique)] if unique else None


def _next_pending_forecast(
    forecast_ledger: dict,
    outcome_ledger: dict,
) -> dict | None:
    handled = {
        str(row["target_session_date"])
        for row in outcome_ledger.get("entries", [])
    }
    rows = [
        row
        for row in forecast_ledger.get("entries", [])
        if row.get("status") == "SEALED"
        and str(row["target_session_date"]) not in handled
    ]
    rows.sort(key=lambda row: str(row["target_session_date"]))
    return rows[0] if rows else None


def _unavailable_artifact(
    *,
    target_session: str,
    realized_session: str,
    forecast_artifact_sha256: str,
    reason: str,
) -> dict:
    artifact = {
        "schema_version": 1,
        "study_id": "RM001-C002-v1",
        "status": "UNAVAILABLE",
        "target_session_date": target_session,
        "realized_session_date": realized_session,
        "forecast_artifact_sha256": forecast_artifact_sha256,
        "valid_probe_count": 0,
        "minimum_valid_probe_count": 12,
        "reason": reason,
        "probe_outcomes": [],
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Advance one prospective RM001 C002 next-session outcome"
    )
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--forecast-ledger", type=Path, required=True)
    parser.add_argument("--outcome-ledger", type=Path, required=True)
    parser.add_argument("--outcome-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
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
    outcome_ledger = _load_json(args.outcome_ledger)
    validate_outcome_ledger(outcome_ledger)

    forecast_entry = _next_pending_forecast(
        forecast_ledger,
        outcome_ledger,
    )
    if forecast_entry is None:
        print(
            json.dumps(
                {"state": "NO_PENDING_FORECAST", "changed": False},
                sort_keys=True,
            )
        )
        return 0

    target = str(forecast_entry["target_session_date"])
    next_attempt = _next_later_eligible_attempt(source_ledger, target)
    if next_attempt is None:
        print(
            json.dumps(
                {
                    "state": "WAITING_FOR_NEXT_ELIGIBLE_MARKET_SOURCE",
                    "target_session_date": target,
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0

    target_attempt = _find_attempt_by_sha(
        source_ledger,
        str(forecast_entry["sc001_attempt_sha256"]),
    )
    target_raw = _exact_market_raw(target_attempt)
    later_raw = _exact_market_raw(next_attempt)
    later_session = str(next_attempt["session_date"])

    args.work_dir.mkdir(parents=True, exist_ok=True)
    base_fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    exact = {
        str(target_attempt["market"]["source_url"]): target_raw,
        str(next_attempt["market"]["source_url"]): later_raw,
    }

    def market_fetch(url: str):
        if url in exact:
            return exact[url]
        return base_fetch(url)

    market = acquire_historical_market_panel(
        start_date=date.fromisoformat(target),
        end_date=date.fromisoformat(later_session),
        fetcher=market_fetch,
        store_root=args.work_dir / "market-store",
        pause_seconds=0.0,
    )
    sessions = market.get("sessions")
    if not isinstance(sessions, list) or len(sessions) < 2:
        print(
            json.dumps(
                {
                    "state": "WAITING_FOR_NEXT_COMPLETED_NSE_SESSION",
                    "target_session_date": target,
                    "changed": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if str(sessions[0]["session_date"]) != target:
        raise AlphaContractError(
            "C002 outcome market panel does not start at target"
        )
    actual_next = str(sessions[1]["session_date"])

    forecast_path = Path(str(forecast_entry["forecast_artifact_path"]))
    if not forecast_path.exists():
        raise AlphaContractError(
            f"C002 forecast artifact is missing: {forecast_path}"
        )
    forecast = load_canonical_gzip_json(forecast_path.read_bytes())
    if forecast["artifact_sha256"] != forecast_entry[
        "forecast_artifact_sha256"
    ]:
        raise AlphaContractError(
            "C002 forecast ledger/artifact SHA mismatch"
        )

    if actual_next != later_session:
        outcome = _unavailable_artifact(
            target_session=target,
            realized_session=actual_next,
            forecast_artifact_sha256=forecast["artifact_sha256"],
            reason="SC001_MISSING_IMMEDIATE_NEXT_COMPLETED_SESSION_SOURCE",
        )
    else:
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
            start_date=date.fromisoformat(target),
            end_date=date.fromisoformat(actual_next),
            fetcher=action_fetch,
            raw_dir=args.work_dir / "corporate-actions",
            chunk_days=31,
        )
        action_states = action_index(actions)
        _, stock_by_session, _ = _market_maps(market)

        identities = {
            (str(member["symbol"]), str(member["isin"]))
            for probe in forecast["probes"]
            for member in probe["members"]
        }
        realized_returns = {}
        unavailable = {}
        for identity in sorted(identities):
            current = stock_by_session[target].get(identity)
            nxt = stock_by_session[actual_next].get(identity)
            if current is None or nxt is None:
                unavailable[identity] = "MISSING_NEXT_IDENTITY"
                continue
            state = action_states.get(identity[0].upper())
            if state is not None and state.get("status") != "READY":
                unavailable[identity] = "ACTION_AUDIT_UNRESOLVED"
                continue
            if blocked_actions(
                action_states,
                symbol=identity[0],
                start_exclusive=target,
                end_inclusive=actual_next,
            ):
                unavailable[identity] = "CORPORATE_ACTION_BLOCKED"
                continue
            value = nxt.close_price / current.close_price - 1.0
            if not (-1.0 < value < 100.0):
                unavailable[identity] = "NONFINITE_OR_IMPLAUSIBLE_RETURN"
                continue
            realized_returns[identity] = value

        outcome = build_outcome_artifact(
            forecast_artifact=forecast,
            realized_session_date=actual_next,
            realized_returns=realized_returns,
            unavailable_identities=unavailable,
        )
        (args.work_dir / "market-panel.json.gz").write_bytes(
            canonical_gzip_json(market)
        )
        (args.work_dir / "corporate-action-ledger.json.gz").write_bytes(
            canonical_gzip_json(actions)
        )

    args.outcome_dir.mkdir(parents=True, exist_ok=True)
    outcome_path = args.outcome_dir / f"{target}-v1.json.gz"
    outcome_bytes = canonical_gzip_json(outcome)
    if outcome_path.exists() and outcome_path.read_bytes() != outcome_bytes:
        raise AlphaContractError(
            f"C002 outcome path collision: {outcome_path}"
        )
    outcome_path.write_bytes(outcome_bytes)

    updated = append_outcome_entry(
        outcome_ledger,
        forecast_entry_sha256=str(forecast_entry["entry_sha256"]),
        outcome_artifact=outcome,
        outcome_artifact_path=str(outcome_path),
    )
    _write_json(args.outcome_ledger, updated)
    validate_outcome_ledger(updated)

    outcome_artifacts = []
    for entry in updated["entries"]:
        path = Path(str(entry["outcome_artifact_path"]))
        if not path.exists():
            raise AlphaContractError(
                f"C002 historical outcome artifact missing: {path}"
            )
        artifact = load_canonical_gzip_json(path.read_bytes())
        if artifact["artifact_sha256"] != entry["outcome_artifact_sha256"]:
            raise AlphaContractError(
                "C002 outcome ledger/artifact SHA mismatch"
            )
        outcome_artifacts.append(artifact)
    summary = prospective_summary(outcome_artifacts)
    _write_json(args.summary, summary)

    result = {
        "state": outcome["status"],
        "target_session_date": target,
        "realized_session_date": actual_next,
        "valid_probe_count": outcome["valid_probe_count"],
        "outcome_artifact_sha256": outcome["artifact_sha256"],
        "outcome_file_sha256": sha256_bytes(outcome_bytes),
        "outcome_ledger_sha256": updated["ledger_sha256"],
        "summary_status": summary["status"],
        "evaluated_date_count": summary["evaluated_date_count"],
        "summary_sha256": summary["summary_sha256"],
        "changed": True,
        "live_capital_allowed": False,
    }
    _write_json(args.work_dir / "outcome-result.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
