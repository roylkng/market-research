"""Replay T012 outcomes from original content-addressed NSE source bytes."""

from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.alpha_t012_decisions import validate_t012_decision_ledger
from marketlab.alpha_t012_outcomes import (
    build_t012_horizon_outcome,
    validate_t012_outcome_ledger,
)
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.events import sha256_bytes
from marketlab.marketdata import (
    index_snapshot_url,
    parse_index_snapshot,
    udiff_url,
)


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AlphaContractError(f"T012 expected JSON at {path}")
    return data


def _artifact(path: Path, expected_sha: str) -> dict:
    if not path.is_file():
        raise AlphaContractError(f"T012 evidence file missing: {path}")
    try:
        decoded = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise AlphaContractError(f"T012 invalid compressed evidence: {path}") from exc
    actual = decoded.get("artifact_sha256")
    unsigned = dict(decoded)
    unsigned.pop("artifact_sha256", None)
    if actual != expected_sha or actual != digest(unsigned):
        raise AlphaContractError(f"T012 evidence bytes/hash mismatch: {path}")
    return decoded


def _source_bytes(path: str, sha: str) -> bytes:
    source = Path(path)
    if not source.is_file():
        raise AlphaContractError(f"T012 original source missing: {source}")
    raw = source.read_bytes()
    if sha256_bytes(raw) != sha:
        raise AlphaContractError(f"T012 original source SHA mismatch: {source}")
    return raw


def _replayed_market_sessions(artifact: dict) -> list[dict]:
    rows = []
    for receipt in artifact["holding_session_evidence"]:
        day = str(receipt["session_date"])
        session_date = date.fromisoformat(day)
        stock_raw = _source_bytes(
            receipt["original_market_raw_path"], receipt["udiff_sha256"]
        )
        index_raw = _source_bytes(
            receipt["original_index_raw_path"],
            receipt["benchmark_sha256"],
        )
        stocks = parse_udiff_eq_panel(stock_raw, session_date=session_date)
        index = parse_index_snapshot(
            index_raw, benchmark_id="nifty_500", session_date=session_date
        )
        rows.append({
            "session_date": day,
            "udiff_url": udiff_url(session_date),
            "benchmark_url": index_snapshot_url(session_date),
            "udiff_sha256": receipt["udiff_sha256"],
            "benchmark_sha256": receipt["benchmark_sha256"],
            "original_market_raw_path": receipt["original_market_raw_path"],
            "original_index_raw_path": receipt["original_index_raw_path"],
            "captured_at_utc": receipt["actual_source_captured_at_utc"],
            "equities": [asdict(row) for row in stocks],
            "benchmark": asdict(index),
        })
    return rows


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--outcome-ledger", type=Path,
        default=Path("research/prospective/ae001-t012/outcome-ledger.json")
    )
    p.add_argument(
        "--decision-ledger", type=Path,
        default=Path("research/prospective/ae001-t012/decision-ledger.json")
    )
    p.add_argument(
        "--calendar", type=Path,
        default=Path(
            "research/prospective/calendars/FY27-Q2-2026-09-06/"
            "NSE-CM-FY27Q2-v1.json"
        ),
    )
    return p.parse_args()


def verify(args: argparse.Namespace) -> dict:
    outcomes = _load(args.outcome_ledger)
    decisions = _load(args.decision_ledger)
    validate_t012_outcome_ledger(outcomes)
    validate_t012_decision_ledger(decisions)
    calendar = load_calendar_snapshot(args.calendar)
    if not outcomes["outcomes"]:
        return {
            "state": "NO_MATURE_OUTCOMES",
            "outcome_count": 0,
            "ledger_sha256": outcomes["ledger_sha256"],
            "live_capital_allowed": False,
        }

    by_d = {
        row["session_date"]: row for row in decisions["decisions"]
    }
    verified = []
    for row in outcomes["outcomes"]:
        feature = row["decision_session"]
        if feature not in by_d:
            raise AlphaContractError(f"T012 outcome lacks decision: {feature}")
        decision_row = by_d[feature]
        if row["decision_artifact_sha256"] != decision_row["artifact_sha256"]:
            raise AlphaContractError("T012 outcome decision hash differs")
        decision = _artifact(
            Path(decision_row["artifact_path"]),
            decision_row["artifact_sha256"],
        )
        outcome = _artifact(Path(row["artifact_path"]), row["artifact_sha256"])
        if (
            outcome["trial_id"] != "AE001-T012"
            or outcome["decision_session"] != feature
            or outcome["horizon_sessions"] != row["horizon_sessions"]
            or outcome["entry_session"] != row["entry_session"]
            or outcome["exit_session"] != row["exit_session"]
            or outcome["captured_at_utc"] != row["captured_at_utc"]
            or outcome["valid_paired_ic"] != row["valid_paired_ic"]
        ):
            raise AlphaContractError("T012 outcome ledger/artifact mismatch")
        original_action = _source_bytes(
            outcome["original_corporate_action_raw_path"],
            outcome["corporate_action_raw_sha256"],
        )
        original_payload = json.loads(original_action)
        computed = build_t012_horizon_outcome(
            decision_artifact=decision,
            market_sessions=_replayed_market_sessions(outcome),
            corporate_action_payload=original_payload,
            corporate_action_raw=original_action,
            horizon_sessions=row["horizon_sessions"],
            calendar=calendar,
            captured_at_utc=outcome["captured_at_utc"],
        )
        computed.pop("artifact_sha256")
        computed["original_corporate_action_raw_path"] = outcome[
            "original_corporate_action_raw_path"
        ]
        computed["artifact_sha256"] = digest(computed)
        if computed != outcome:
            raise AlphaContractError(
                f"T012 original-source replay differs: {feature}"
            )
        verified.append({
            "decision_session": feature,
            "horizon_sessions": row["horizon_sessions"],
            "artifact_sha256": outcome["artifact_sha256"],
        })
    return {
        "state": "REPRODUCIBLE_FROM_ORIGINAL_EXCHANGE_BYTES",
        "outcome_count": len(verified),
        "ledger_sha256": outcomes["ledger_sha256"],
        "verified": verified,
        "live_capital_allowed": False,
    }


def main() -> int:
    print(json.dumps(verify(_args()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
