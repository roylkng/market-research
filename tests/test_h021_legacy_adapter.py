from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from marketlab.h021 import select_prior_snapshot
from marketlab.h021_legacy_adapter import (
    LEGACY_BASENAME,
    LEGACY_CAPTURE_ID,
    LEGACY_GZIP_SHA256,
    LEGACY_JSON_SHA256,
    load_h021_capture_compatible,
)

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "research/prospective/h021/captures"
UNIVERSE = ROOT / "research/prospective/universes/FY27-Q2-2026-09-06.json"
BATCHES = ROOT / "research/prospective/h021/capture-batches-v1.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load(path: Path) -> tuple[dict, dict]:
    return load_h021_capture_compatible(
        path, universe=_json(UNIVERSE), batch_spec=_json(BATCHES)
    )


def test_real_sep11_v1_bundle_is_exact_and_full_u001() -> None:
    snapshot, manifest = _load(CAPTURES / LEGACY_BASENAME)
    assert snapshot["capture_date_ist"] == "2026-09-11"
    assert manifest["schema_version"] == 1
    assert manifest["logical_capture_id"] == LEGACY_CAPTURE_ID
    assert manifest["payload_gzip_sha256"] == LEGACY_GZIP_SHA256
    assert manifest["payload_uncompressed_sha256"] == LEGACY_JSON_SHA256
    assert len(snapshot["observations"]) == 100
    assert len({row["symbol"] for row in snapshot["observations"]}) == 100
    assert snapshot["outcomes_opened"] is False
    assert snapshot["live_capital_allowed"] is False


def test_v2_capture_verification_remains_unchanged() -> None:
    for day in ("2026-09-18", "2026-09-25"):
        snapshot, manifest = _load(CAPTURES / f"{day}-full-u001-v1.json.gz")
        assert manifest["schema_version"] == 2
        assert snapshot["capture_date_ist"] == day
        assert len(snapshot["observations"]) == 100


def test_oct09_primary_window_selects_pinned_sep11_anchor() -> None:
    sep11, _ = _load(CAPTURES / LEGACY_BASENAME)
    sep18, _ = _load(CAPTURES / "2026-09-18-full-u001-v1.json.gz")
    sep25, _ = _load(CAPTURES / "2026-09-25-full-u001-v1.json.gz")

    current = copy.deepcopy(sep11)
    current["capture_date_ist"] = "2026-10-09"
    current["captured_at_utc"] = "2026-10-09T13:10:00Z"
    current["logical_capture_id"] = "2026-10-09-full-u001-v1"
    selected = select_prior_snapshot(current, [sep11, sep18, sep25])
    assert selected is sep11


def test_tampered_legacy_manifest_fails_closed(tmp_path: Path) -> None:
    raw = CAPTURES / LEGACY_BASENAME
    destination = tmp_path / LEGACY_BASENAME
    shutil.copy2(raw, destination)
    manifest_path = tmp_path / "2026-09-11-full-u001-v1.manifest.json"
    manifest = _json(CAPTURES / manifest_path.name)
    manifest["payload_gzip_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="payload_gzip_sha256"):
        _load(destination)


def test_tampered_legacy_gzip_fails_closed(tmp_path: Path) -> None:
    destination = tmp_path / LEGACY_BASENAME
    raw = bytearray((CAPTURES / LEGACY_BASENAME).read_bytes())
    raw[-1] ^= 1
    destination.write_bytes(bytes(raw))
    shutil.copy2(
        CAPTURES / "2026-09-11-full-u001-v1.manifest.json",
        tmp_path / "2026-09-11-full-u001-v1.manifest.json",
    )
    with pytest.raises(ValueError, match="gzip SHA mismatch"):
        _load(destination)


def test_unrecognized_v1_bundle_cannot_be_substituted(tmp_path: Path) -> None:
    name = "2026-09-12-full-u001-v1.json.gz"
    destination = tmp_path / name
    shutil.copy2(CAPTURES / LEGACY_BASENAME, destination)
    shutil.copy2(
        CAPTURES / "2026-09-11-full-u001-v1.manifest.json",
        tmp_path / "2026-09-12-full-u001-v1.manifest.json",
    )
    with pytest.raises(ValueError, match="unrecognized legacy"):
        _load(destination)
