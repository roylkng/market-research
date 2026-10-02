from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_history import load_canonical_gzip_json
from marketlab.rm001_c002 import (
    validate_forecast_ledger,
    validate_outcome_ledger,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify canonical RM001 C002 prospective state"
    )
    parser.add_argument("--forecast-ledger", type=Path, required=True)
    parser.add_argument("--outcome-ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    forecast = _load(args.forecast_ledger)
    outcome = _load(args.outcome_ledger)
    validate_forecast_ledger(forecast)
    validate_outcome_ledger(outcome)

    sealed_forecasts = 0
    for entry in forecast["entries"]:
        if entry["status"] != "SEALED":
            continue
        path = Path(str(entry["forecast_artifact_path"]))
        if not path.exists():
            raise SystemExit(f"missing C002 forecast artifact: {path}")
        artifact = load_canonical_gzip_json(path.read_bytes())
        stored = str(artifact.get("artifact_sha256") or "")
        unsigned = dict(artifact)
        unsigned.pop("artifact_sha256", None)
        if stored != digest(unsigned):
            raise SystemExit(f"C002 forecast artifact hash mismatch: {path}")
        if stored != entry["forecast_artifact_sha256"]:
            raise SystemExit(f"C002 forecast ledger/artifact mismatch: {path}")
        if artifact.get("outcomes_attached") is not False:
            raise SystemExit(f"C002 forecast contains outcome: {path}")
        sealed_forecasts += 1

    for entry in outcome["entries"]:
        path = Path(str(entry["outcome_artifact_path"]))
        if not path.exists():
            raise SystemExit(f"missing C002 outcome artifact: {path}")
        artifact = load_canonical_gzip_json(path.read_bytes())
        stored = str(artifact.get("artifact_sha256") or "")
        unsigned = dict(artifact)
        unsigned.pop("artifact_sha256", None)
        if stored != digest(unsigned):
            raise SystemExit(f"C002 outcome artifact hash mismatch: {path}")
        if stored != entry["outcome_artifact_sha256"]:
            raise SystemExit(f"C002 outcome ledger/artifact mismatch: {path}")

    summary_state = None
    if args.summary is not None and args.summary.exists():
        summary = _load(args.summary)
        stored = str(summary.get("summary_sha256") or "")
        unsigned = dict(summary)
        unsigned.pop("summary_sha256", None)
        if stored != digest(unsigned):
            raise SystemExit("C002 prospective summary hash mismatch")
        summary_state = summary.get("status")

    print(
        json.dumps(
            {
                "forecast_entry_count": forecast["entry_count"],
                "sealed_forecast_count": sealed_forecasts,
                "outcome_entry_count": outcome["entry_count"],
                "forecast_ledger_sha256": forecast["ledger_sha256"],
                "outcome_ledger_sha256": outcome["ledger_sha256"],
                "summary_status": summary_state,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
