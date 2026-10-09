from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_expectations import build_h021_expectations_panel
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021 import select_prior_snapshot, validate_snapshot
from marketlab.h021_capture import (
    ALLOWED_CAPTURE_STATES,
    CANONICAL_SOURCE_VERSION,
    CANONICAL_UNIVERSE_BLOB_SHA,
    CANONICAL_UNIVERSE_PATH,
    verify_capture_bundle,
)


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



# The 2026-09-11 anchor predates sealer v2. Its immutable, content-addressed
# schema-v1 payload may be read for the frozen 28-35-day comparison. This is
# deliberately a one-identity compatibility path, not general schema-v1 support.
LEGACY_ANCHOR_ID = "2026-09-11-full-u001-v1"
LEGACY_ANCHOR_GZIP_SHA256 = "94bdbbc4fa4e8fa70f1535797f165dfbab52d0f937cade91425824422f9d2c33"
LEGACY_ANCHOR_JSON_SHA256 = "bd87a3bb942a60e7f625293577487b8850b67530b3126bea5bb7d9d9e999d434"


def _verified_legacy_anchor(
    path: Path,
    payload_gzip: bytes,
    manifest: dict,
    *,
    universe: dict,
    batch_spec: dict,
) -> dict:
    if path.name != f"{LEGACY_ANCHOR_ID}.json.gz":
        raise ValueError("unsupported legacy H021 capture identity")
    if manifest.get("schema_version") != 1 or manifest.get("hypothesis_id") != "H021":
        raise ValueError("unexpected historical H021 manifest schema or hypothesis")
    expected = {
        "logical_capture_id": LEGACY_ANCHOR_ID,
        "capture_date_ist": "2026-09-11",
        "source_version": CANONICAL_SOURCE_VERSION,
        "universe_path": CANONICAL_UNIVERSE_PATH,
        "universe_git_blob_sha": CANONICAL_UNIVERSE_BLOB_SHA,
        "payload_path": (
            "research/prospective/h021/captures/"
            f"{LEGACY_ANCHOR_ID}.json.gz"
        ),
        "payload_encoding": "gzip",
        "payload_gzip_sha256": LEGACY_ANCHOR_GZIP_SHA256,
        "payload_uncompressed_sha256": LEGACY_ANCHOR_JSON_SHA256,
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise ValueError(f"legacy H021 manifest {field} does not match freeze")
    if len(universe.get("members", [])) != 100 or batch_spec.get("expected_member_count") != 100:
        raise ValueError("legacy H021 comparison requires frozen 100-name U001")
    if hashlib.sha256(payload_gzip).hexdigest() != LEGACY_ANCHOR_GZIP_SHA256:
        raise ValueError("legacy H021 anchor gzip differs from frozen bytes")
    if manifest.get("payload_gzip_bytes") != len(payload_gzip):
        raise ValueError("legacy H021 gzip byte length mismatch")
    try:
        raw = gzip.decompress(payload_gzip)
    except (OSError, EOFError) as exc:
        raise ValueError("invalid legacy H021 gzip payload") from exc
    if hashlib.sha256(raw).hexdigest() != LEGACY_ANCHOR_JSON_SHA256:
        raise ValueError("legacy H021 anchor JSON differs from frozen bytes")
    if manifest.get("payload_uncompressed_bytes") != len(raw):
        raise ValueError("legacy H021 JSON byte length mismatch")
    snapshot = json.loads(raw)
    if not isinstance(snapshot, dict):
        raise TypeError("legacy H021 snapshot must be an object")
    snapshot = dict(snapshot)
    for field in (
        "logical_capture_id", "capture_date_ist", "captured_at_utc",
        "source_version", "universe_path", "universe_git_blob_sha",
        "protocol_path", "batch_spec_path",
    ):
        from_manifest = manifest.get(field)
        in_snapshot = snapshot.get(field)
        if in_snapshot is not None and from_manifest is not None and in_snapshot != from_manifest:
            raise ValueError(f"legacy H021 payload/manifest {field} mismatch")
        if in_snapshot is None and from_manifest is not None:
            snapshot[field] = from_manifest
    if snapshot.get("outcomes_opened") is not False or snapshot.get("live_capital_allowed") is not False:
        raise ValueError("legacy H021 result boundary changed")
    errors = validate_snapshot(snapshot)
    if errors:
        raise ValueError({"legacy_h021_snapshot_errors": errors})
    observations = snapshot.get("observations")
    if not isinstance(observations, list) or len(observations) != 100:
        raise ValueError("legacy H021 capture must retain exactly 100 rows")
    members = {row["symbol"]: row for row in universe["members"]}
    if len(members) != 100:
        raise ValueError("frozen U001 contains duplicate symbols")
    observed = [row.get("symbol") for row in observations]
    if len(set(observed)) != 100 or set(observed) != set(members):
        raise ValueError("legacy H021 symbol accounting differs from frozen U001")
    batches = Counter()
    states = Counter()
    for row in observations:
        member = members[row["symbol"]]
        if row.get("isin") != member["isin"] or row.get("universe_rank") != member["rank"]:
            raise ValueError("legacy H021 symbol/ISIN/rank mismatch")
        expected_batch = "B01" if member["rank"] <= 50 else "B02"
        if row.get("batch_id") != expected_batch:
            raise ValueError("legacy H021 frozen batch identity mismatch")
        batches[expected_batch] += 1
        state = row.get("data_state")
        if state not in ALLOWED_CAPTURE_STATES:
            raise ValueError("legacy H021 invalid coverage state")
        states[state] += 1
    if batches != {"B01": 50, "B02": 50}:
        raise ValueError("legacy H021 batch counts are not 50 + 50")
    declared = manifest.get("coverage_summary", {})
    if declared.get("total") != 100:
        raise ValueError("legacy H021 manifest total is not 100")
    for state in ALLOWED_CAPTURE_STATES:
        if declared.get(state) != states[state]:
            raise ValueError("legacy H021 declared coverage differs from payload")
    if declared.get("explicit_consensus_eps") != sum(
        row.get("consensus_eps") is not None for row in observations
    ):
        raise ValueError("legacy H021 declared EPS count differs from payload")
    if manifest.get("batch_summary") != [
        {"batch_id": "B01", "ranks": "1-50", "processed": 50},
        {"batch_id": "B02", "ranks": "51-100", "processed": 50},
    ]:
        raise ValueError("legacy H021 manifest batch accounting differs")
    return snapshot

def _load_capture(
    path: Path,
    *,
    universe: dict,
    batch_spec: dict,
) -> tuple[dict, dict]:
    manifest_path = _manifest_path(path)
    manifest = _read_json(manifest_path)
    payload_gzip = path.read_bytes()
    if manifest.get("schema_version") == 1:
        snapshot = _verified_legacy_anchor(
            path, payload_gzip, manifest, universe=universe, batch_spec=batch_spec
        )
        return snapshot, manifest
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
