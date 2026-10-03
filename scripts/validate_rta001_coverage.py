from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from marketlab.rta001 import build_rta001_summary, validate_rta001_manifest


class RTA001CoverageError(ValueError):
    """Raised when repository research escapes explicit RTA001 accounting."""


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _research_result_files(root: Path) -> set[str]:
    research = root / "research"
    if not research.exists():
        raise FileNotFoundError(f"research directory missing: {research}")
    return {
        path.relative_to(root).as_posix()
        for path in research.rglob("*result*.json")
        if path.is_file()
    }


def _accounted_result_paths(manifest: dict) -> set[str]:
    paths = [
        str(trial["result_path"])
        for trial in manifest["trials"]
        if trial.get("result_path") is not None
    ]
    paths.extend(
        str(path)
        for path in manifest.get("source_feasibility_results", [])
    )
    if len(paths) != len(set(paths)):
        duplicates = sorted(
            path for path in set(paths) if paths.count(path) > 1
        )
        raise RTA001CoverageError(
            f"RTA001 result paths must be unique: {duplicates}"
        )
    return set(paths)


def _registered_ae001_trial_ids(root: Path) -> set[str]:
    ledger_path = root / "research/ae001/trial-ledger.json"
    ledger = _load_json(ledger_path)
    events = ledger.get("events")
    if not isinstance(events, list):
        raise TypeError(f"AE001 trial ledger events must be a list: {ledger_path}")
    return {
        str(event["trial_id"])
        for event in events
        if isinstance(event, dict)
        and event.get("event_type") == "TRIAL_REGISTERED"
        and str(event.get("trial_id") or "").strip()
    }


def _registered_hypothesis_ids(root: Path) -> set[str]:
    path = root / "registry/hypotheses.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"hypothesis registry must be an object: {path}")
    rows = payload.get("hypotheses")
    if not isinstance(rows, list):
        raise TypeError(f"hypothesis registry rows must be a list: {path}")
    ids = [
        str(row.get("id") or "").strip()
        for row in rows
        if isinstance(row, dict)
    ]
    if any(not value for value in ids):
        raise RTA001CoverageError(
            "canonical hypothesis registry contains an empty ID"
        )
    if len(ids) != len(set(ids)):
        raise RTA001CoverageError(
            "canonical hypothesis registry contains duplicate IDs"
        )
    return set(ids)


def validate_repository_accounting(
    *,
    repo_root: Path,
    manifest_path: Path,
    summary_path: Path,
) -> dict:
    manifest = _load_json(repo_root / manifest_path)
    validate_rta001_manifest(manifest)
    manifest_ids = {
        str(trial["trial_id"])
        for trial in manifest["trials"]
    }

    repository_results = _research_result_files(repo_root)
    accounted_results = _accounted_result_paths(manifest)
    unaccounted_results = sorted(repository_results - accounted_results)
    missing_result_files = sorted(accounted_results - repository_results)
    if unaccounted_results:
        raise RTA001CoverageError(
            "research result artifacts are missing explicit RTA001 accounting: "
            + ", ".join(unaccounted_results)
        )
    if missing_result_files:
        raise RTA001CoverageError(
            "RTA001 references result artifacts that do not exist: "
            + ", ".join(missing_result_files)
        )

    ae001_ids = _registered_ae001_trial_ids(repo_root)
    missing_ae001 = sorted(ae001_ids - manifest_ids)
    if missing_ae001:
        raise RTA001CoverageError(
            "AE001 registered trials are missing from RTA001: "
            + ", ".join(missing_ae001)
        )

    hypothesis_ids = _registered_hypothesis_ids(repo_root)
    missing_hypotheses = sorted(hypothesis_ids - manifest_ids)
    if missing_hypotheses:
        raise RTA001CoverageError(
            "canonical H-series hypotheses are missing from RTA001: "
            + ", ".join(missing_hypotheses)
        )

    expected_summary = build_rta001_summary(manifest)
    observed_summary = _load_json(repo_root / summary_path)
    if observed_summary != expected_summary:
        raise RTA001CoverageError(
            "checked-in RTA001 summary is stale; rebuild it from the current "
            "research/rta001-trials-v1.json manifest"
        )

    report = {
        "accounting_id": manifest["accounting_id"],
        "manifest_trial_count": len(manifest_ids),
        "research_result_artifact_count": len(repository_results),
        "accounted_result_artifact_count": len(accounted_results),
        "ae001_registered_trial_count": len(ae001_ids),
        "canonical_hypothesis_count": len(hypothesis_ids),
        "summary_sha256": observed_summary["summary_sha256"],
        "coverage_complete": True,
        "live_capital_allowed": False,
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail closed when repository research escapes RTA001 accounting"
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("research/rta001-trials-v1.json"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("research/rta001-summary-v1.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_repository_accounting(
        repo_root=args.repo_root,
        manifest_path=args.manifest,
        summary_path=args.summary,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
