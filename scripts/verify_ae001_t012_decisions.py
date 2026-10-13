"""Verify every T012 decision against current append-only source proofs."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_t012_decisions import validate_t012_decision_ledger
from marketlab.alpha_t012_preopen import admit_t012_preopen
from marketlab.calendar_snapshot import load_calendar_snapshot


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--ledger", type=Path,
        default=Path("research/prospective/ae001-t012/decision-ledger.json")
    )
    p.add_argument(
        "--calendar", type=Path,
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
    return p.parse_args()


def verify(args: argparse.Namespace) -> dict:
    ledger = _read(args.ledger)
    validate_t012_decision_ledger(ledger)
    if not ledger["decisions"]:
        return {
            "state": "PREREGISTERED_AWAITING_FIRST_ELIGIBLE_DECISION",
            "decision_count": 0,
            "ledger_sha256": ledger["ledger_sha256"],
            "live_capital_allowed": False,
        }
    common = {
        "sc001_ledger": _read(args.sc001_ledger),
        "sc003_ledger": _read(args.sc003_ledger),
        "trial_ledger": _read(args.trial_ledger),
        "rta_manifest": _read(args.rta_manifest),
        "calendar": load_calendar_snapshot(args.calendar),
        "frozen_models": _read(args.models),
    }
    verified = []
    for row in ledger["decisions"]:
        path = Path(str(row["artifact_path"]))
        if not path.is_file():
            raise AlphaContractError(f"T012 missing sealed prediction file: {path}")
        try:
            artifact = json.loads(
                gzip.decompress(path.read_bytes()).decode("utf-8")
            )
        except (ValueError, OSError) as exc:
            raise AlphaContractError(f"T012 malformed prediction: {path}") from exc
        stored = artifact.get("artifact_sha256")
        unsigned = dict(artifact)
        unsigned.pop("artifact_sha256", None)
        if digest(unsigned) != stored or row["artifact_sha256"] != stored:
            raise AlphaContractError(f"T012 decision hash mismatch: {path}")
        if artifact.get("trial_id") != "AE001-T012":
            raise AlphaContractError(f"T012 wrong trial artifact: {path}")
        if (
            artifact.get("session_date") != row["session_date"]
            or artifact.get("entry_session") != row["entry_session"]
            or artifact.get("sealed_at_utc") != row["sealed_at_utc"]
            or artifact.get("common_row_count") != row["common_row_count"]
        ):
            raise AlphaContractError(f"T012 ledger/artifact mismatch: {path}")
        if artifact.get("outcomes_attached") is not False:
            raise AlphaContractError("T012 decision includes future outcome")
        if artifact.get("live_capital_allowed") is not False:
            raise AlphaContractError("T012 decision permits live capital")
        for kind in ("base", "augmented"):
            preds = artifact.get(f"{kind}_predictions")
            if not isinstance(preds, list) or len(preds) != row[
                "common_row_count"
            ]:
                raise AlphaContractError(
                    f"T012 {kind} prediction count/identity mismatch"
                )
        admitted = admit_t012_preopen(
            feature_session=row["session_date"],
            sealed_at_utc=row["sealed_at_utc"],
            **common,
        )
        if artifact["admission_sha256"] != admitted["admission_sha256"]:
            raise AlphaContractError("T012 decision admission not source-reproducible")
        if (
            admitted["sc001_attempt_sha256"] != row["sc001_attempt_sha256"]
            or admitted["sc003_attempt_sha256"] != row["sc003_attempt_sha256"]
        ):
            raise AlphaContractError("T012 source attempt drift")
        verified.append(
            {
                "feature_session": row["session_date"],
                "entry_session": row["entry_session"],
                "artifact_sha256": stored,
            }
        )
    return {
        "state": "VERIFIED",
        "decision_count": len(verified),
        "ledger_sha256": ledger["ledger_sha256"],
        "verified": verified,
        "live_capital_allowed": False,
    }


def main() -> int:
    print(json.dumps(verify(parse_args()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
