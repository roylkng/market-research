import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_d011 import (
    D011_REPORT_DATES,
    D011_SAMPLE_RANKS,
    build_d011_result,
    first_current_source,
    prior_source_at_current_broadcast,
    sample_symbols,
)


def _universe():
    return {
        "members": [
            {"rank": rank, "symbol": f"S{rank:03d}"}
            for rank in range(1, 101)
        ]
    }


def _source(symbol, report_date, broadcast, record_id):
    return {
        "source_id": f"{symbol}-{record_id}",
        "symbol": symbol,
        "record_id": record_id,
        "report_date": report_date,
        "broadcast_at_utc": broadcast,
        "xbrl_url": "https://nsearchives.nseindia.com/test.xml",
        "master_row_sha256": "a" * 64,
    }


def test_sample_symbols_are_exact_frozen_stratified_ranks():
    symbols = sample_symbols(_universe())
    assert len(symbols) == 25
    assert symbols[0] == "S001"
    assert symbols[-1] == "S097"
    assert [int(symbol[1:]) for symbol in symbols] == list(
        D011_SAMPLE_RANKS
    )


def test_current_uses_first_broadcast_and_prior_uses_latest_public_revision():
    sources = [
        _source("S001", "2025-03-31", "2025-04-20T10:00:00Z", "P1"),
        _source("S001", "2025-03-31", "2025-05-01T10:00:00Z", "P2"),
        _source("S001", "2025-06-30", "2025-07-20T10:00:00Z", "C1"),
        _source("S001", "2025-06-30", "2025-07-21T10:00:00Z", "C2"),
        _source("S001", "2025-03-31", "2025-08-01T10:00:00Z", "P3"),
    ]
    current, ambiguous = first_current_source(
        sources,
        report_date="2025-06-30",
    )
    assert ambiguous is False
    assert current["record_id"] == "C1"
    prior, prior_ambiguous = prior_source_at_current_broadcast(
        sources,
        current_report_date="2025-06-30",
        current_broadcast_at_utc=current["broadcast_at_utc"],
    )
    assert prior_ambiguous is False
    assert prior["record_id"] == "P2"


def test_same_timestamp_current_sources_fail_as_ambiguous():
    sources = [
        _source("S001", "2025-06-30", "2025-07-20T10:00:00Z", "C1"),
        _source("S001", "2025-06-30", "2025-07-20T10:00:00Z", "C2"),
    ]
    current, ambiguous = first_current_source(
        sources,
        report_date="2025-06-30",
    )
    assert current is None
    assert ambiguous is True


def test_source_result_passes_when_full_sample_is_ready():
    universe = _universe()
    symbols = sample_symbols(universe)
    master = {
        symbol: {"status": "READY", "raw_sha256": "m" * 64}
        for symbol in symbols
    }
    sources_by_symbol = {}
    evidence = {}
    for symbol in symbols:
        sources = []
        broadcast_dates = (
            "2024-04-15T10:00:00Z",
            "2024-07-15T10:00:00Z",
            "2024-10-15T10:00:00Z",
            "2025-01-15T10:00:00Z",
            "2025-04-15T10:00:00Z",
            "2025-07-15T10:00:00Z",
            "2025-10-15T10:00:00Z",
            "2026-01-15T10:00:00Z",
            "2026-04-15T10:00:00Z",
            "2026-07-15T10:00:00Z",
        )
        for index, report_date in enumerate(D011_REPORT_DATES):
            source = _source(
                symbol,
                report_date,
                broadcast_dates[index],
                f"R{index}",
            )
            sources.append(source)
            evidence[source["source_id"]] = {
                "status": "READY",
                "source_id": source["source_id"],
                "xbrl_sha256": "x" * 64,
                "mutual_fund_percentage": 5.0,
                "error": None,
            }
        sources_by_symbol[symbol] = sources

    result = build_d011_result(
        universe=universe,
        master_status_by_symbol=master,
        sources_by_symbol=sources_by_symbol,
        evidence_by_source_id=evidence,
    )
    assert result["status"] == "PASS_SOURCE_FEASIBILITY"
    assert result["current_parse_ready_coverage"] == pytest.approx(1.0)
    assert result["adjacent_pair_parse_ready_coverage"] == pytest.approx(1.0)
    assert result["return_labels_opened"] is False


def test_source_result_fails_closed_when_master_sample_is_incomplete():
    universe = _universe()
    symbols = sample_symbols(universe)
    master = {
        symbol: {"status": "READY"}
        for symbol in symbols[:-1]
    }
    sources = {symbol: [] for symbol in symbols}
    with pytest.raises(AlphaContractError, match="master status"):
        build_d011_result(
            universe=universe,
            master_status_by_symbol=master,
            sources_by_symbol=sources,
            evidence_by_source_id={},
        )
