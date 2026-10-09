from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.materialize_ae001_h021_expectations import _load_capture

CAPTURE_DIR = Path("research/prospective/h021/captures")
UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
BATCH_PATH = Path("research/prospective/h021/capture-batches-v1.json")


def _inputs() -> tuple[dict, dict]:
    universe = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    batches = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    return universe, batches


def test_h021_ae001_accepts_only_pinned_legacy_anchor_and_current_v2_bundles() -> None:
    universe, batches = _inputs()
    for day, expected_schema in (
        ("2026-09-11", 1),
        ("2026-09-18", 2),
        ("2026-09-25", 2),
    ):
        path = CAPTURE_DIR / f"{day}-full-u001-v1.json.gz"
        snapshot, manifest = _load_capture(
            path, universe=universe, batch_spec=batches
        )
        assert manifest["schema_version"] == expected_schema
        assert snapshot["capture_date_ist"] == day
        assert snapshot["source_version"] == manifest["source_version"]
        assert snapshot["universe_git_blob_sha"] == manifest["universe_git_blob_sha"]
        assert len(snapshot["observations"]) == 100
        assert len({row["symbol"] for row in snapshot["observations"]}) == 100
        assert snapshot["outcomes_opened"] is False
        assert snapshot["live_capital_allowed"] is False


def test_h021_ae001_rejects_tampered_legacy_anchor_manifest(tmp_path: Path) -> None:
    universe, batches = _inputs()
    name = "2026-09-11-full-u001-v1"
    source = CAPTURE_DIR / f"{name}.json.gz"
    target = tmp_path / source.name
    target.write_bytes(source.read_bytes())
    manifest = json.loads((CAPTURE_DIR / f"{name}.manifest.json").read_text())
    manifest["universe_git_blob_sha"] = "0" * 40
    (tmp_path / f"{name}.manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="frozen"):
        _load_capture(target, universe=universe, batch_spec=batches)


def test_h021_ae001_rejects_tampered_legacy_anchor_bytes(tmp_path: Path) -> None:
    universe, batches = _inputs()
    name = "2026-09-11-full-u001-v1"
    target = tmp_path / f"{name}.json.gz"
    source = CAPTURE_DIR / target.name
    target.write_bytes(source.read_bytes() + b"\\x00")
    (tmp_path / f"{name}.manifest.json").write_bytes(
        (CAPTURE_DIR / f"{name}.manifest.json").read_bytes()
    )
    with pytest.raises(ValueError, match="frozen bytes"):
        _load_capture(target, universe=universe, batch_spec=batches)
