import json
from datetime import UTC, datetime

import pytest

from marketlab.universe import UniverseError, build_universe_snapshot, load_universe_snapshot
from tests.universe_fixtures import make_nifty200_sources


def test_selects_top_non_financial_companies_by_ffmc():
    index, constituent_csv = make_nifty200_sources(
        [
            {"symbol": "AAA", "ffmc": 600, "industry": "Information Technology"},
            {"symbol": "BANK", "ffmc": 550, "industry": "Financial Services"},
            {"symbol": "CCC", "ffmc": 500, "industry": "Healthcare"},
            {"symbol": "BBB", "ffmc": 500, "industry": "Capital Goods"},
            {"symbol": "DDD", "ffmc": 400, "industry": "Consumer Services"},
        ]
    )

    snapshot = build_universe_snapshot(
        index,
        constituent_csv,
        cohort_id="FY27-Q2",
        selection_size=3,
        captured_at=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
    )

    assert [member.symbol for member in snapshot.members] == ["AAA", "BBB", "CCC"]
    assert [member.source_rank for member in snapshot.members] == [1, 3, 4]
    assert snapshot.members[1].ffmc == 500
    assert snapshot.members[1].constituent_industry == "Capital Goods"
    assert snapshot.contains("bbb") is True
    assert snapshot.contains("BANK") is False
    assert len(snapshot.sha256) == 64
    assert len(snapshot.source_hashes["constituents_raw_sha256"]) == 64


def test_snapshot_hash_is_deterministic():
    index, constituent_csv = make_nifty200_sources(
        [{"symbol": "AAA", "ffmc": 1000, "industry": "Information Technology"}]
    )
    captured = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)

    one = build_universe_snapshot(
        index,
        constituent_csv,
        cohort_id="C",
        selection_size=1,
        captured_at=captured,
    )
    two = build_universe_snapshot(
        index,
        constituent_csv,
        cohort_id="C",
        selection_size=1,
        captured_at=captured,
    )
    assert one.sha256 == two.sha256
    assert one.to_dict() == two.to_dict()


def test_frozen_snapshot_round_trip_verifies_hash(tmp_path):
    index, constituent_csv = make_nifty200_sources(
        [{"symbol": "AAA", "ffmc": 1000, "industry": "Capital Goods"}]
    )
    snapshot = build_universe_snapshot(
        index,
        constituent_csv,
        cohort_id="C",
        selection_size=1,
        captured_at=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
    )
    path = tmp_path / "universe.json"
    path.write_text(json.dumps(snapshot.to_dict()), encoding="utf-8")
    loaded = load_universe_snapshot(path)
    assert loaded == snapshot


def test_frozen_snapshot_rejects_tampering(tmp_path):
    index, constituent_csv = make_nifty200_sources(
        [{"symbol": "AAA", "ffmc": 1000, "industry": "Capital Goods"}]
    )
    snapshot = build_universe_snapshot(
        index,
        constituent_csv,
        cohort_id="C",
        selection_size=1,
        captured_at=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
    )
    document = snapshot.to_dict()
    document["members"][0]["symbol"] = "CHANGED"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(UniverseError, match="hash mismatch"):
        load_universe_snapshot(path)


def test_missing_industry_is_fatal_not_silently_skipped():
    index, constituent_csv = make_nifty200_sources(
        [
            {"symbol": "AAA", "ffmc": 1000, "industry": ""},
            {"symbol": "BBB", "ffmc": 900, "industry": "Capital Goods"},
        ]
    )

    with pytest.raises(UniverseError, match="missing official Industry classification for AAA"):
        build_universe_snapshot(index, constituent_csv, cohort_id="C", selection_size=1)


def test_too_few_non_financial_names_fails():
    index, constituent_csv = make_nifty200_sources(
        [{"symbol": "BANK", "ffmc": 1000, "industry": "Financial Services"}]
    )

    with pytest.raises(UniverseError, match="could select only 0"):
        build_universe_snapshot(index, constituent_csv, cohort_id="C", selection_size=1)


def test_index_and_constituent_csv_symbol_mismatch_is_fatal():
    index, constituent_csv = make_nifty200_sources(
        [{"symbol": "AAA", "ffmc": 1000, "industry": "Capital Goods"}]
    )
    index["data"][0]["symbol"] = "INDEXONLY"

    with pytest.raises(UniverseError, match="Nifty 200 source mismatch"):
        build_universe_snapshot(index, constituent_csv, cohort_id="C", selection_size=1)
