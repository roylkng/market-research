"""Acquire mature T012 holding-period NSE evidence, never future features.

Only exact frozen trading sessions are evaluated. Missing original UDiFF,
index or corporate-action evidence means outcome pending, not return zero.
"""

from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_history import canonical_gzip_json
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.alpha_t012_decisions import validate_t012_decision_ledger
from marketlab.alpha_t012_outcomes import (
    append_t012_outcome,
    build_t012_horizon_outcome,
    expected_t012_holding_dates,
    finalize_t012_results,
    validate_t012_outcome_ledger,
)
from marketlab.alpha_trials import validate_trial_ledger
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.events import sha256_bytes
from marketlab.marketdata import (
    index_snapshot_url,
    parse_index_snapshot,
    udiff_url,
)
from marketlab.nse import NSEClient
from marketlab.rta001 import build_rta001_summary

IST = ZoneInfo("Asia/Kolkata")


def _json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"T012 expected JSON object: {path}")
    return data


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _save_source(path: Path, raw: bytes) -> None:
    if not raw:
        raise AlphaContractError("T012 empty original NSE source")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise AlphaContractError(f"T012 original byte collision: {path}")
    else:
        path.write_bytes(raw)


def _read_artifact(path: Path, expected: str) -> dict:
    if not path.is_file():
        raise AlphaContractError(f"T012 missing original sealed artifact: {path}")
    data = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    stored = data.get("artifact_sha256")
    unsigned = dict(data)
    unsigned.pop("artifact_sha256", None)
    if stored != digest(unsigned) or stored != expected:
        raise AlphaContractError(f"T012 sealed artifact hash mismatch: {path}")
    return data


def _market_observation(
    session_date: str,
    *,
    fetch,
    storage: Path,
    calendar,
) -> dict | None:
    session = next(
        (
            s for s in calendar.sessions
            if s.session_date == session_date
        ),
        None,
    )
    if session is None:
        raise AlphaContractError(f"T012 unregistered NSE session {session_date}")
    now = datetime.now(UTC)
    close = datetime.fromisoformat(session.close_timestamp_utc).astimezone(UTC)
    if now <= close:
        return None

    day = date.fromisoformat(session_date)
    market_url = udiff_url(day)
    index_url = index_snapshot_url(day)
    market_raw = fetch(market_url)
    if market_raw is None:
        return None
    index_raw = fetch(index_url)
    if index_raw is None:
        return None

    equities = parse_udiff_eq_panel(market_raw, session_date=day)
    benchmark = parse_index_snapshot(
        index_raw, benchmark_id="nifty_500", session_date=day
    )
    captured = datetime.now(UTC)
    if captured <= close:
        raise AlphaContractError("T012 source capture before official close")
    market_sha = sha256_bytes(market_raw)
    index_sha = sha256_bytes(index_raw)
    market_path = storage / session_date / f"market-{market_sha}.zip"
    index_path = storage / session_date / f"nifty500-{index_sha}.csv"
    _save_source(market_path, market_raw)
    _save_source(index_path, index_raw)
    return {
        "session_date": session_date,
        "udiff_url": market_url,
        "benchmark_url": index_url,
        "udiff_sha256": market_sha,
        "benchmark_sha256": index_sha,
        "original_market_raw_path": str(market_path),
        "original_index_raw_path": str(index_path),
        "captured_at_utc": captured.isoformat(),
        "equities": [asdict(row) for row in equities],
        "benchmark": asdict(benchmark),
    }


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--calendar", type=Path,
        default=Path(
            "research/prospective/calendars/FY27-Q2-2026-09-06/"
            "NSE-CM-FY27Q2-v1.json"
        )
    )
    p.add_argument(
        "--decision-ledger", type=Path,
        default=Path("research/prospective/ae001-t012/decision-ledger.json"),
    )
    p.add_argument(
        "--outcome-ledger", type=Path,
        default=Path("research/prospective/ae001-t012/outcome-ledger.json"),
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
        "--rta-summary", type=Path,
        default=Path("research/rta001-summary-v1.json"),
    )
    p.add_argument(
        "--outcome-dir", type=Path,
        default=Path("research/prospective/ae001-t012/outcomes"),
    )
    p.add_argument(
        "--source-dir", type=Path,
        default=Path("research/prospective/ae001-t012/original-market"),
    )
    p.add_argument(
        "--work-dir", type=Path,
        default=Path("reports/ae001-t012-outcomes"),
    )
    p.add_argument("--as-of-date", type=date.fromisoformat)
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--timeout-seconds", type=float, default=30)
    return p.parse_args()


def main() -> int:
    args = _args()
    now = datetime.now(UTC)
    as_of = args.as_of_date or now.astimezone(IST).date()
    if as_of > now.astimezone(IST).date():
        raise AlphaContractError("T012 cannot evaluate a future observation date")

    calendar = load_calendar_snapshot(args.calendar)
    decisions = _json(args.decision_ledger)
    outcomes = _json(args.outcome_ledger)
    trials = _json(args.trial_ledger)
    rta = _json(args.rta_manifest)
    validate_t012_decision_ledger(decisions)
    validate_t012_outcome_ledger(outcomes)
    validate_trial_ledger(trials)
    if not decisions["decisions"]:
        print(json.dumps(
            {"state": "NO_SEALED_DECISIONS", "changed": False,
             "live_capital_allowed": False},
            sort_keys=True,
        ))
        return 0

    existing = {
        (row["decision_session"], row["horizon_sessions"])
        for row in outcomes["outcomes"]
    }
    required: set[str] = set()
    matured: list[tuple[dict, int, list[str]]] = []
    unknown_calendar_dates = []
    for decision in decisions["decisions"]:
        d = decision["session_date"]
        for horizon in (1, 5):
            if (d, horizon) in existing:
                continue
            try:
                holding = expected_t012_holding_dates(
                    calendar, decision_session=d, horizon=horizon
                )
            except AlphaContractError as exc:
                if "lacks full holding horizon" in str(exc):
                    unknown_calendar_dates.append(d)
                    continue
                raise
            exit_session = next(
                s for s in calendar.sessions
                if s.session_date == holding[-1]
            )
            if (
                holding[-1] > as_of.isoformat()
                or datetime.now(UTC) <= datetime.fromisoformat(
                    exit_session.close_timestamp_utc
                ).astimezone(UTC)
            ):
                continue
            matured.append((decision, horizon, holding))
            required.update(holding)

    args.work_dir.mkdir(parents=True, exist_ok=True)
    fetch = http_fetcher(
        attempts=args.attempts, timeout=args.timeout_seconds
    )
    market_data: dict[str, dict] = {}
    incomplete_source_dates = []
    for day in sorted(required):
        # Parser corruption is a scientific integrity failure. Allow it to
        # propagate instead of disguising it as missing market observations.
        observation = _market_observation(
            day,
            fetch=fetch,
            storage=args.source_dir,
            calendar=calendar,
        )
        if observation is None:
            incomplete_source_dates.append(day)
        else:
            market_data[day] = observation

    eligible = [
        (decision, horizon, holding)
        for decision, horizon, holding in matured
        if all(day in market_data for day in holding)
    ]
    action_payload = None
    action_raw = None
    action_sha = None
    action_path = None
    if eligible:
        first_day = min(
            holding[0] for _, _, holding in eligible
        )
        last_day = max(
            holding[-1] for _, _, holding in eligible
        )
        client = NSEClient(
            timeout=args.timeout_seconds, attempts=args.attempts
        )
        action_payload, action_raw = client.corporate_actions_with_raw(
            None,
            from_date=date.fromisoformat(first_day).strftime("%d-%m-%Y"),
            to_date=date.fromisoformat(last_day).strftime("%d-%m-%Y"),
        )
        action_sha = sha256_bytes(action_raw)
        action_path = args.source_dir / "actions" / (
            f"nse-corporate-actions-{action_sha}.json"
        )
        _save_source(action_path, action_raw)

    newly_matured = []
    for decision_row, horizon, holding in eligible:
        d = decision_row["session_date"]
        decision = _read_artifact(
            Path(decision_row["artifact_path"]),
            decision_row["artifact_sha256"],
        )
        if (
            decision.get("entry_session") != holding[0]
            or decision.get("session_date") != d
        ):
            raise AlphaContractError("T012 outcome decision/entry mismatch")
        artifact = build_t012_horizon_outcome(
            decision_artifact=decision,
            market_sessions=[market_data[day] for day in holding],
            corporate_action_payload=action_payload,
            corporate_action_raw=action_raw,
            horizon_sessions=horizon,
            calendar=calendar,
            captured_at_utc=datetime.now(UTC).isoformat(),
        )
        artifact.pop("artifact_sha256")
        artifact["original_corporate_action_raw_path"] = str(action_path)
        artifact["artifact_sha256"] = digest(artifact)
        path = args.outcome_dir / f"{d}-h{horizon}-v1.json.gz"
        bytes_data = canonical_gzip_json(artifact)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != bytes_data:
            raise AlphaContractError(
                f"T012 immutable outcome path collision: {path}"
            )
        path.write_bytes(bytes_data)
        outcomes = append_t012_outcome(
            outcomes,
            outcome_artifact=artifact,
            artifact_path=str(path),
        )
        newly_matured.append({
            "decision_session": d,
            "horizon": horizon,
            "entry": artifact["entry_session"],
            "exit": artifact["exit_session"],
            "valid_paired_ic": artifact["valid_paired_ic"],
            "sha256": artifact["artifact_sha256"],
        })

    if newly_matured:
        _write(args.outcome_ledger, outcomes)

    all_artifacts = [
        _read_artifact(
            Path(row["artifact_path"]),
            row["artifact_sha256"],
        )
        for row in outcomes["outcomes"]
    ]
    trials_updated, events = finalize_t012_results(
        trial_ledger=trials,
        decision_ledger=decisions,
        outcome_ledger=outcomes,
        outcome_artifacts=all_artifacts,
        recorded_at_utc=datetime.now(UTC).isoformat(),
    )

    changed = bool(newly_matured)
    if trials_updated != trials:
        _write(args.trial_ledger, trials_updated)
        changed = True

    # Rebuild RTA from the primary outcome event only. The secondary H1 cannot
    # overwrite the frozen primary test or its global multiplicity family.
    new_primary = next(
        (
            event for event in events
            if event["payload"].get("result_kind") == "PRIMARY_5D"
        ),
        None,
    )
    if new_primary:
        rows = [
            row for row in rta["trials"] if row["trial_id"] == "AE001-T012"
        ]
        if len(rows) != 1 or rows[0]["result_state"] != "PENDING_PROSPECTIVE":
            raise AlphaContractError("T012 global RTA transition invalid")
        alpha = rows[0]
        results = new_primary["payload"]["paired_augmented_minus_base"]["metrics"]
        rank_p = float(results["rank_ic"]["p_value_two_sided"])
        spread_p = float(
            results["top_minus_bottom_spread"]["p_value_two_sided"]
        )
        # Intersection-union p-value for both mandatory endpoints.
        primary_p = max(rank_p, spread_p)
        alpha.update({
            "result_state": "COMPLETE",
            "reported_primary_supported": (
                new_primary["payload"]["status"]
                == "NOMINAL_SUPPORT_PENDING_MULTIPLICITY_AND_COST"
            ),
            "primary_result_event_sha256": new_primary["event_sha256"],
            "required_component_p_values": {
                "rank_ic": rank_p,
                "spread": spread_p,
            },
            "p_value_status": "INTERSECTION_UNION_MAX_REQUIRED_COMPONENTS",
            "nominal_primary_p_value": primary_p,
            "fdr_accounting_p_value": primary_p,
        })
        rta["as_of_date"] = now.astimezone(IST).date().isoformat()
        _write(args.rta_manifest, rta)
        _write(args.rta_summary, build_rta001_summary(rta))
        changed = True

    report = {
        "schema_version": 1,
        "state": "UPDATED" if changed else "NO_MATURE_COMPLETE_OUTCOME",
        "as_of_date": as_of.isoformat(),
        "decision_count": decisions["decision_count"],
        "outcome_count": outcomes["outcome_count"],
        "newly_matured": newly_matured,
        "missing_original_source_dates": sorted(set(incomplete_source_dates)),
        "trials_awaiting_future_calendar_extension": sorted(
            set(unknown_calendar_dates)
        ),
        "new_result_events": [
            {
                "event_sha256": e["event_sha256"],
                "kind": e["payload"].get("result_kind"),
            }
            for e in events
        ],
        "outcome_ledger_sha256": outcomes["ledger_sha256"],
        "changed": changed,
        "live_capital_allowed": False,
    }
    _write(args.work_dir / "latest-advance.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
