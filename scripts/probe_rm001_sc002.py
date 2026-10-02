from __future__ import annotations

import argparse
import gzip
import json
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.rm001_d015 import SOURCE_URL as CONSTITUENT_SOURCE_URL
from marketlab.rm001_d015 import parse_constituent_csv
from marketlab.rm001_d015_r1 import parse_security_master_all_series
from marketlab.rm001_industry_capture import (
    append_industry_attempt,
    build_industry_snapshot,
    industry_readiness_summary,
    latest_eligible_sc001_target,
    mapping_change_diagnostics,
    validate_industry_source_ledger,
)
from marketlab.rm001_size_source import security_master_url


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


def _raw_path(
    *,
    observation_date: str,
    kind: str,
    raw_sha256: str,
    target_session: str | None = None,
) -> Path:
    root = Path("research/prospective/rm001-sc002/raw") / observation_date
    if kind == "constituent":
        return root / f"constituent-{raw_sha256}.csv"
    if kind == "security" and target_session is not None:
        return root / f"security-{target_session}-{raw_sha256}.csv.gz"
    raise ValueError("unsupported RM001-SC002 raw path request")


def _previous_ready_snapshot(ledger: dict) -> dict | None:
    for attempt in reversed(ledger["attempts"]):
        if attempt.get("status") != "READY":
            continue
        path = Path(str(attempt.get("snapshot_path") or ""))
        if not path.exists():
            raise RuntimeError(
                f"RM001-SC002 previous READY snapshot missing: {path}"
            )
        payload = load_canonical_gzip_json(path.read_bytes())
        if payload.get("snapshot_sha256") != attempt.get("snapshot_sha256"):
            raise RuntimeError(
                "RM001-SC002 previous READY snapshot hash mismatch"
            )
        return payload
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture prospective RM001-SC002 industry snapshot"
    )
    parser.add_argument(
        "--observation-date",
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--industry-ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    observation_date = args.observation_date.isoformat()
    sc001 = _load_json(args.sc001_ledger)
    ledger = _load_json(args.industry_ledger)
    validate_industry_source_ledger(ledger)

    target = latest_eligible_sc001_target(
        sc001,
        observation_date=observation_date,
    )
    target_session = str(target["session_date"])
    security_url = security_master_url(date.fromisoformat(target_session))

    fetch = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    constituent_raw = fetch(CONSTITUENT_SOURCE_URL)
    security_raw = fetch(security_url)
    captured = datetime.now(UTC).isoformat()

    constituent_status = "UNAVAILABLE" if constituent_raw is None else "READY"
    security_status = "UNAVAILABLE" if security_raw is None else "READY"

    if constituent_raw is not None:
        try:
            parse_constituent_csv(constituent_raw)
        except AlphaContractError:
            constituent_status = "PARSER_REJECTED"
    if security_raw is not None:
        try:
            parse_security_master_all_series(security_raw)
        except AlphaContractError:
            security_status = "PARSER_REJECTED"

    constituent_sha = (
        None if constituent_raw is None else sha256_bytes(constituent_raw)
    )
    security_sha = (
        None if security_raw is None else sha256_bytes(security_raw)
    )
    constituent_path = (
        None
        if constituent_sha is None
        else _raw_path(
            observation_date=observation_date,
            kind="constituent",
            raw_sha256=constituent_sha,
        )
    )
    security_path = (
        None
        if security_sha is None
        else _raw_path(
            observation_date=observation_date,
            kind="security",
            raw_sha256=security_sha,
            target_session=target_session,
        )
    )

    snapshot = None
    snapshot_path = None
    change = None
    if (
        constituent_raw is not None
        and security_raw is not None
        and constituent_status == "READY"
        and security_status == "READY"
    ):
        snapshot = build_industry_snapshot(
            constituent_raw=constituent_raw,
            security_raw=security_raw,
            target_session_date=target_session,
            captured_at_utc=captured,
            constituent_raw_path=str(constituent_path),
            security_raw_path=str(security_path),
        )
        snapshot_path = (
            Path("research/prospective/rm001-sc002/snapshots")
            / (
                f"{observation_date}-{target_session}-"
                f"{snapshot['snapshot_sha256']}.json.gz"
            )
        )
        if snapshot["status"] == "READY":
            previous = _previous_ready_snapshot(ledger)
            change = mapping_change_diagnostics(previous, snapshot)

    updated, attempt = append_industry_attempt(
        ledger,
        observation_date=observation_date,
        target_session_date=target_session,
        captured_at_utc=captured,
        constituent_status=constituent_status,
        constituent_raw_sha256=constituent_sha,
        constituent_raw_path=(
            None if constituent_path is None else str(constituent_path)
        ),
        security_status=security_status,
        security_raw_sha256=security_sha,
        security_raw_path=(
            None if security_path is None else str(security_path)
        ),
        snapshot=snapshot,
        snapshot_path=(
            None if snapshot_path is None else str(snapshot_path)
        ),
        change_diagnostics=change,
    )

    if attempt is None:
        ready_summary = industry_readiness_summary(ledger)
        _write_json(args.summary, ready_summary)
        print(
            json.dumps(
                {
                    "state": "IDENTICAL_CAPTURE_ALREADY_RECORDED",
                    "observation_date": observation_date,
                    "target_session_date": target_session,
                    "changed": False,
                    "ledger_sha256": ledger["ledger_sha256"],
                    "summary_sha256": ready_summary["summary_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0

    if constituent_raw is not None and constituent_path is not None:
        constituent_path.parent.mkdir(parents=True, exist_ok=True)
        if (
            constituent_path.exists()
            and constituent_path.read_bytes() != constituent_raw
        ):
            raise RuntimeError(
                f"RM001-SC002 constituent path collision: {constituent_path}"
            )
        constituent_path.write_bytes(constituent_raw)

    if security_raw is not None and security_path is not None:
        security_path.parent.mkdir(parents=True, exist_ok=True)
        if (
            security_path.exists()
            and security_path.read_bytes() != security_raw
        ):
            raise RuntimeError(
                f"RM001-SC002 security path collision: {security_path}"
            )
        security_path.write_bytes(security_raw)

    if snapshot is not None and snapshot_path is not None:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_bytes = canonical_gzip_json(snapshot)
        if (
            snapshot_path.exists()
            and snapshot_path.read_bytes() != snapshot_bytes
        ):
            raise RuntimeError(
                f"RM001-SC002 snapshot path collision: {snapshot_path}"
            )
        snapshot_path.write_bytes(snapshot_bytes)

    _write_json(args.industry_ledger, updated)
    validate_industry_source_ledger(updated)
    ready_summary = industry_readiness_summary(updated)
    _write_json(args.summary, ready_summary)

    print(
        json.dumps(
            {
                "state": "CAPTURED",
                "changed": True,
                "observation_date": observation_date,
                "target_session_date": target_session,
                "captured_at_utc": captured,
                "status": attempt["status"],
                "attempt_sha256": attempt["attempt_sha256"],
                "snapshot_sha256": attempt["snapshot_sha256"],
                "mapped_eq_count": attempt["mapped_eq_count"],
                "dummy_count": attempt["dummy_count"],
                "ledger_sha256": updated["ledger_sha256"],
                "summary_sha256": ready_summary["summary_sha256"],
                "prospective_industry_source_capture_ready": ready_summary[
                    "prospective_industry_source_capture_ready"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
