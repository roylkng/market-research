from __future__ import annotations

import json
from pathlib import Path

from marketlab.h021 import validate_snapshot


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "research/prospective/h021/captures/2026-09-11-browser-baseline-v1.json"
BATCHES = ROOT / "research/prospective/h021/capture-batches-v1.json"
UNIVERSE = ROOT / "research/prospective/universes/FY27-Q2-2026-09-06.json"


def test_seed_baseline_is_valid_and_primary_eps_is_unavailable() -> None:
    snapshot = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert validate_snapshot(snapshot) == []
    assert snapshot["primary_eps_revision_usable"] is False
    assert len(snapshot["observations"]) == 8
    assert all(row["consensus_eps"] is None for row in snapshot["observations"])


def test_capture_batches_cover_frozen_nifty_200_exactly_once() -> None:
    batch_config = json.loads(BATCHES.read_text(encoding="utf-8"))
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))

    assert batch_config["expected_member_count"] == 200
    assert len(universe["members"]) == 200

    covered_ranks: list[int] = []
    for batch in batch_config["batches"]:
        covered_ranks.extend(range(batch["rank_min"], batch["rank_max"] + 1))

    assert covered_ranks == list(range(1, 201))
    assert sorted(member["rank"] for member in universe["members"]) == list(range(1, 201))
