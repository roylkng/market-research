from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.rta001 import build_rta001_summary, validate_rta001_manifest


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write(path: Path, payload: object) -> None:
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


def _verify_result_file(root: Path, trial: dict) -> None:
    raw_path = trial.get("result_path")
    if raw_path is None:
        return
    path = root / str(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"RTA001 result file missing: {path}")
    payload = _load(path)
    if payload.get("live_capital_allowed") is not False:
        raise ValueError(f"RTA001 result may not allow live capital: {path}")
    anchor = trial.get("result_anchor")
    if anchor is not None:
        field = str(anchor["field"])
        expected = anchor["value"]
        observed = payload.get(field)
        if observed != expected:
            raise ValueError(
                f"RTA001 result anchor mismatch for {trial['trial_id']}: "
                f"{field}={observed} != {expected}"
            )


def _verify_source_reference(root: Path, trial: dict) -> None:
    source = trial.get("source")
    if not isinstance(source, str) or "#" not in source:
        return
    raw_path, _ = source.split("#", 1)
    path = root / raw_path
    if not path.exists():
        raise FileNotFoundError(f"RTA001 source ledger missing: {path}")
    payload = _load(path)
    events = payload.get("events")
    if not isinstance(events, list):
        raise TypeError(
            f"RTA001 fragmented source is not an event ledger: {path}"
        )
    trial_id = str(trial["trial_id"])
    matches = [
        event
        for event in events
        if str(event.get("trial_id") or "") == trial_id
    ]
    if not matches:
        raise ValueError(
            f"RTA001 source ledger lacks trial {trial_id}: {path}"
        )
    expected_sha = trial.get("source_anchor_sha256")
    if expected_sha is not None and not any(
        event.get("event_sha256") == expected_sha for event in matches
    ):
        raise ValueError(
            f"RTA001 source event anchor missing for {trial_id}: {expected_sha}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and verify RTA001 global research accounting"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("research/rta001-trials-v1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/rta001-summary-v1.json"),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = _load(args.manifest)
    validate_rta001_manifest(manifest)

    for trial in manifest["trials"]:
        _verify_result_file(args.repo_root, trial)
        _verify_source_reference(args.repo_root, trial)

    for raw_path in manifest.get("source_feasibility_results", []):
        path = args.repo_root / raw_path
        if not path.exists():
            raise FileNotFoundError(
                f"RTA001 source-feasibility result missing: {path}"
            )
        payload = _load(path)
        if payload.get("live_capital_allowed") is not False:
            raise ValueError(
                f"RTA001 source result may not allow live capital: {path}"
            )

    summary = build_rta001_summary(manifest)
    _write(args.output, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
