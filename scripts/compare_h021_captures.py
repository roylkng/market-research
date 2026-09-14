from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from marketlab.h021 import (
    compare_snapshots,
    select_primary_top_decile,
    select_prior_snapshot,
    validate_snapshot,
)

IDENTITY_FIELDS = ("source_version", "universe_path", "universe_git_blob_sha")


def _manifest_path(snapshot_path: Path) -> Path:
    name = snapshot_path.name
    if name.endswith(".json.gz"):
        base = name[: -len(".json.gz")]
    elif name.endswith(".json"):
        base = name[: -len(".json")]
    else:
        base = snapshot_path.stem
    return snapshot_path.with_name(f"{base}.manifest.json")


def _read_json(path: Path) -> dict:
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"snapshot must be a JSON object: {path}")
    return payload


def _load_snapshot(path: Path) -> dict:
    snapshot = _read_json(path)
    manifest_path = _manifest_path(path)
    if not manifest_path.exists():
        return snapshot

    manifest = _read_json(manifest_path)
    enriched = dict(snapshot)
    for field in IDENTITY_FIELDS:
        manifest_value = manifest.get(field)
        snapshot_value = snapshot.get(field)
        if (
            snapshot_value is not None
            and manifest_value is not None
            and snapshot_value != manifest_value
        ):
            raise ValueError(
                f"snapshot/manifest {field} mismatch for {path}: "
                f"{snapshot_value!r} != {manifest_value!r}"
            )
        if snapshot_value is None and manifest_value is not None:
            enriched[field] = manifest_value
    return enriched


def _candidate_paths(capture_dir: Path, current_path: Path) -> list[Path]:
    current_resolved = current_path.resolve()
    paths: list[Path] = []
    for path in sorted(capture_dir.iterdir()):
        if not path.is_file() or path.resolve() == current_resolved:
            continue
        if path.name.endswith(".manifest.json"):
            continue
        if path.name.endswith(".json") or path.name.endswith(".json.gz"):
            paths.append(path)
    return paths


def _select_prior_from_dir(
    capture_dir: Path, current_path: Path, current: dict
) -> tuple[Path, dict]:
    candidates: list[tuple[Path, dict]] = []
    for path in _candidate_paths(capture_dir, current_path):
        snapshot = _load_snapshot(path)
        if snapshot.get("hypothesis_id") != "H021":
            continue
        if not isinstance(snapshot.get("observations"), list):
            continue
        candidates.append((path, snapshot))

    selected = select_prior_snapshot(current, [snapshot for _, snapshot in candidates])
    for path, snapshot in candidates:
        if snapshot is selected:
            return path, snapshot
    raise RuntimeError("selected H021 prior capture path could not be resolved")


def main() -> None:
    parser = argparse.ArgumentParser()
    prior_group = parser.add_mutually_exclusive_group(required=True)
    prior_group.add_argument("--prior", type=Path)
    prior_group.add_argument("--capture-dir", type=Path)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    current = _load_snapshot(args.current)
    if args.prior is not None:
        prior_path = args.prior
        prior = _load_snapshot(prior_path)
    else:
        prior_path, prior = _select_prior_from_dir(
            args.capture_dir, args.current, current
        )

    errors = {
        "prior": validate_snapshot(prior),
        "current": validate_snapshot(current),
    }
    if errors["prior"] or errors["current"]:
        raise SystemExit(json.dumps(errors, indent=2, sort_keys=True))

    revision_models = compare_snapshots(prior, current)
    selected_models = select_primary_top_decile(revision_models)
    revisions = [asdict(row) for row in revision_models]
    reason_counts = Counter(row.primary_signal_reason for row in revision_models)
    cutoff = (
        min(float(row.eps_revision_pct) for row in selected_models)
        if selected_models
        else None
    )

    output = {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "prior_capture_path": str(prior_path),
        "current_capture_path": str(args.current),
        "prior_capture_date_ist": prior["capture_date_ist"],
        "current_capture_date_ist": current["capture_date_ist"],
        "capture_interval_days": revision_models[0].capture_interval_days,
        "source_version": current["source_version"],
        "universe_path": current["universe_path"],
        "universe_git_blob_sha": current["universe_git_blob_sha"],
        "primary_signal": "28-35 day same-period consensus EPS revision",
        "primary_coverage_rule": "analyst_count >= 5 at both captures",
        "primary_signal_available_count": sum(
            int(row.primary_signal_available) for row in revision_models
        ),
        "primary_signal_reason_counts": dict(sorted(reason_counts.items())),
        "primary_top_decile_tie_rule": (
            "include all eligible names tied at the cutoff EPS revision"
        ),
        "primary_top_decile_cutoff_eps_revision_pct": cutoff,
        "primary_top_decile_count": len(selected_models),
        "primary_top_decile_symbols": [row.symbol for row in selected_models],
        "revision_observations": revisions,
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"compared={len(revisions)} "
        f"primary_available={output['primary_signal_available_count']} "
        f"primary_top_decile={output['primary_top_decile_count']} "
        f"prior={prior['capture_date_ist']} current={current['capture_date_ist']}"
    )


if __name__ == "__main__":
    main()
