from __future__ import annotations

from pathlib import Path

from marketlab.frozen_bundle import EXPECTED_BUNDLE_SHA256, load_frozen_bundle
from marketlab.universe import load_universe_snapshot

UNIVERSE = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
ROOT = Path("research/prospective/preparation/FY27-Q2-2026-09-06")


def test_canonical_fy27q2_bundle_and_external_anchor_validate():
    universe = load_universe_snapshot(UNIVERSE)
    view = load_frozen_bundle(
        ROOT / "expectation-bundle.json",
        ROOT / "run-metadata.json",
        universe=universe,
    )
    assert view.bundle_sha256 == EXPECTED_BUNDLE_SHA256
    assert len(view.records_by_symbol) == 100
    assert view.records_by_symbol["ADANIENT"].expectation.status == "NO_SIGNAL"
    assert view.records_by_symbol["LTM"].expectation.status == "NO_SIGNAL"
    assert (
        sum(
            record.expectation.status == "READY"
            for record in view.records_by_symbol.values()
        )
        == 98
    )
