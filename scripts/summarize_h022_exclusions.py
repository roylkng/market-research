from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_HYPOTHESIS_ID = "H022"
EXPECTED_EXECUTION_RULE_ID = "H022-X001"
HORIZONS = (20, 60, 120)


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("H022 outcome report must be a JSON object")
    if payload.get("hypothesis_id") != EXPECTED_HYPOTHESIS_ID:
        raise ValueError("unexpected H022 outcome-report hypothesis id")
    if payload.get("execution_rule_id") != EXPECTED_EXECUTION_RULE_ID:
        raise ValueError("unexpected H022 outcome-report execution rule")
    stored = payload.get("report_sha256")
    unsigned = dict(payload)
    unsigned.pop("report_sha256", None)
    actual = _canonical_hash(unsigned)
    if stored != actual:
        raise ValueError(
            f"H022 outcome-report hash mismatch: stored={stored}, recomputed={actual}"
        )
    records = payload.get("records")
    if not isinstance(records, list):
        raise TypeError("H022 outcome-report records must be a list")
    return payload


def build_summary(report: dict[str, Any]) -> dict[str, Any]:
    status_counts: dict[str, dict[str, int]] = {}
    missing_stock_bars: list[dict[str, Any]] = []
    corporate_action_blocked: list[dict[str, Any]] = []

    for horizon in HORIZONS:
        key = str(horizon)
        counts: Counter[str] = Counter()
        for record in report["records"]:
            if not isinstance(record, dict):
                raise TypeError("H022 outcome record must be an object")
            horizon_payload = record.get("horizons", {}).get(key)
            if not isinstance(horizon_payload, dict):
                raise ValueError(f"H022 record is missing horizon {key}")
            status = str(horizon_payload.get("status") or "")
            if not status:
                raise ValueError(f"H022 horizon {key} status is missing")
            counts[status] += 1

            if status in {"MISSING_ENTRY_STOCK_BAR", "MISSING_EXIT_STOCK_BAR"}:
                missing_stock_bars.append(
                    {
                        "source_id": record.get("source_id"),
                        "symbol": record.get("symbol"),
                        "horizon_sessions": horizon,
                        "status": status,
                        "entry_session_date": (
                            record.get("entry_session", {}).get("session_date")
                            if isinstance(record.get("entry_session"), dict)
                            else None
                        ),
                        "exit_session_date": (
                            horizon_payload.get("exit_session", {}).get("session_date")
                            if isinstance(horizon_payload.get("exit_session"), dict)
                            else None
                        ),
                    }
                )
            if status == "CORPORATE_ACTION_BLOCKED":
                corporate_action_blocked.append(
                    {
                        "source_id": record.get("source_id"),
                        "symbol": record.get("symbol"),
                        "horizon_sessions": horizon,
                        "entry_session_date": (
                            record.get("entry_session", {}).get("session_date")
                            if isinstance(record.get("entry_session"), dict)
                            else None
                        ),
                        "exit_session_date": (
                            horizon_payload.get("exit_session", {}).get("session_date")
                            if isinstance(horizon_payload.get("exit_session"), dict)
                            else None
                        ),
                        "blocked_actions": horizon_payload.get("blocked_actions", []),
                    }
                )
        status_counts[key] = dict(sorted(counts.items()))

    summary: dict[str, Any] = {
        "schema_version": 1,
        "hypothesis_id": EXPECTED_HYPOTHESIS_ID,
        "execution_rule_id": EXPECTED_EXECUTION_RULE_ID,
        "outcome_report_sha256": report["report_sha256"],
        "challenge_signal_count": report.get("challenge_signal_count"),
        "status_counts_by_horizon": status_counts,
        "missing_stock_bar_count": len(missing_stock_bars),
        "missing_stock_bars": missing_stock_bars,
        "corporate_action_blocked_count": len(corporate_action_blocked),
        "corporate_action_blocked": corporate_action_blocked,
    }
    summary["summary_sha256"] = _canonical_hash(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize H022 exclusions")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = _load_report(args.report)
    summary = build_summary(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
