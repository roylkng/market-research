from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_expectations import build_h021_expectations_panel
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021 import select_prior_snapshot
from marketlab.h021_capture import verify_capture_bundle


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _manifest_path(capture_path: Path) -> Path:
    name = capture_path.name
    if not name.endswith(".json.gz"):
        raise ValueError(f"H021 capture must end in .json.gz: {capture_path}")
    return capture_path.with_name(
        f"{name[:-len('.json.gz')]}.manifest.json"
    )


def _load_capture(
    path: Path,
    *,
    universe: dict,
    batch_spec: dict,
) -> tuple[dict, dict]:
    manifest_path = _manifest_path(path)
    manifest = _read_json(manifest_path)
    payload_gzip = path.read_bytes()
    snapshot = verify_capture_bundle(
        payload_gzip,
        manifest,
        universe,
        batch_spec,
    )
    return snapshot, manifest


def _candidate_paths(capture_dir: Path, current_path: Path) -> list[Path]:
    current = current_path.resolve()
    return [
        path
        for path in sorted(capture_dir.glob("*.json.gz"))
        if path.resolve() != current
    ]


def _select_prior(
    capture_dir: Path,
    current_path: Path,
    current: dict,
    *,
    universe: dict,
    batch_spec: dict,
) -> tuple[Path, dict, dict]:
    candidates: list[tuple[Path, dict, dict]] = []
    snapshots: list[dict] = []
    for path in _candidate_paths(capture_dir, current_path):
        snapshot, manifest = _load_capture(
            path,
            universe=universe,
            batch_spec=batch_spec,
        )
        candidates.append((path, snapshot, manifest))
        snapshots.append(snapshot)

    selected = select_prior_snapshot(current, snapshots)
    for path, snapshot, manifest in candidates:
        if snapshot is selected:
            return path, snapshot, manifest
    raise RuntimeError("selected H021 prior capture path could not be resolved")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize AE001 expectations features from sealed H021 captures"
    )
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--batches", type=Path, required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe = _read_json(args.universe)
    batch_spec = _read_json(args.batches)
    current, current_manifest = _load_capture(
        args.current,
        universe=universe,
        batch_spec=batch_spec,
    )
    prior_path, prior, prior_manifest = _select_prior(
        args.capture_dir,
        args.current,
        current,
        universe=universe,
        batch_spec=batch_spec,
    )
    comparison = _read_json(args.comparison)
    calendar = load_calendar_snapshot(args.calendar)

    panel = build_h021_expectations_panel(
        prior=prior,
        current=current,
        prior_manifest=prior_manifest,
        current_manifest=current_manifest,
        comparison=comparison,
        universe=universe,
        calendar=calendar,
    )
    panel["prior_capture_path"] = str(prior_path)
    panel["current_capture_path"] = str(args.current)
    panel["comparison_path"] = str(args.comparison)
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    panel["panel_sha256"] = digest(unsigned)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            panel,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "panel_id": panel["panel_id"],
                "panel_sha256": panel["panel_sha256"],
                "prior_capture_date": panel["prior_capture"][
                    "capture_date_ist"
                ],
                "current_capture_date": panel["current_capture"][
                    "capture_date_ist"
                ],
                "row_count": panel["row_count"],
                "primary_signal_available_count": panel[
                    "primary_signal_available_count"
                ],
                "same_day_1830_compatible": panel[
                    "ae001_same_day_eod_1830_compatible"
                ],
                "earliest_execution_session": panel[
                    "earliest_execution_session"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
