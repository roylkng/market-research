from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from marketlab.h021 import validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "research/prospective/h021/captures"
BASELINE = CAPTURE_DIR / "2026-09-11-browser-baseline-v1.json"
FULL_CAPTURE = CAPTURE_DIR / "2026-09-11-full-u001-v1.json.gz"
FULL_MANIFEST = CAPTURE_DIR / "2026-09-11-full-u001-v1.manifest.json"
BATCHES = ROOT / "research/prospective/h021/capture-batches-v1.json"
UNIVERSE = ROOT / "research/prospective/universes/FY27-Q2-2026-09-06.json"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def test_seed_baseline_is_valid_and_primary_eps_is_unavailable() -> None:
    snapshot = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert validate_snapshot(snapshot) == []
    assert snapshot["primary_eps_revision_usable"] is False
    assert len(snapshot["observations"]) == 8
    assert all(row["consensus_eps"] is None for row in snapshot["observations"])


def test_capture_batches_cover_frozen_u001_panel_exactly_once() -> None:
    batch_config = json.loads(BATCHES.read_text(encoding="utf-8"))
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))

    assert batch_config["expected_member_count"] == 100
    assert len(universe["members"]) == 100

    covered_ranks: list[int] = []
    for batch in batch_config["batches"]:
        covered_ranks.extend(range(batch["rank_min"], batch["rank_max"] + 1))

    assert covered_ranks == list(range(1, 101))
    assert sorted(member["rank"] for member in universe["members"]) == list(range(1, 101))


def test_full_u001_anchor_bytes_and_cross_section_match_manifest() -> None:
    manifest = json.loads(FULL_MANIFEST.read_text(encoding="utf-8"))
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    payload_gzip = FULL_CAPTURE.read_bytes()
    payload_json = gzip.decompress(payload_gzip)
    snapshot = json.loads(payload_json)

    assert manifest["logical_capture_id"] == "2026-09-11-full-u001-v1"
    assert manifest["payload_path"].endswith(FULL_CAPTURE.name)
    assert manifest["payload_gzip_bytes"] == len(payload_gzip)
    assert manifest["payload_gzip_sha256"] == _sha256(payload_gzip)
    assert manifest["payload_uncompressed_bytes"] == len(payload_json)
    assert manifest["payload_uncompressed_sha256"] == _sha256(payload_json)

    assert validate_snapshot(snapshot) == []
    assert snapshot["capture_date_ist"] == manifest["capture_date_ist"]
    assert snapshot["captured_at_utc"] == manifest["captured_at_utc"]
    assert len(snapshot["observations"]) == 100

    frozen_symbols = {member["symbol"] for member in universe["members"]}
    captured_symbols = {row["symbol"] for row in snapshot["observations"]}
    assert captured_symbols == frozen_symbols

    summary = manifest["coverage_summary"]
    analyst_counts = [row.get("analyst_count") for row in snapshot["observations"]]
    assert summary["total"] == len(snapshot["observations"])
    assert summary["explicit_consensus_eps"] == sum(
        row.get("consensus_eps") is not None for row in snapshot["observations"]
    )
    assert summary["current_analyst_count_ge_5"] == sum(
        isinstance(value, int) and value >= 5 for value in analyst_counts
    )
    assert summary["current_analyst_count_2_to_4"] == sum(
        isinstance(value, int) and 2 <= value <= 4 for value in analyst_counts
    )
    assert summary["current_analyst_count_lt_2_or_null"] == sum(
        value is None or (isinstance(value, int) and value < 2) for value in analyst_counts
    )
