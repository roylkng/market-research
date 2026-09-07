from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from marketlab.events import HISTORICAL_RECONSTRUCTION, parse_indas_html, sha256_bytes
from marketlab.h002_historical_identity import (
    historical_discovery_query_symbols,
    historical_isins_equivalent,
    historical_symbol_variants,
    is_non_comparable_predecessor,
    normalize_symbol_for_h002,
    symbols_equivalent,
)

FIXTURES = Path("data/fixtures/filings")


def _event():
    raw = (FIXTURES / "ccl_fy27_q1_consolidated_source_derived.html").read_bytes()
    return parse_indas_html(
        raw.decode(),
        source_url="https://nsearchives.nseindia.com/example-ccl.xml",
        raw_sha256=sha256_bytes(raw),
        raw_path="raw/ccl.xml",
        captured_at_utc="2026-09-07T06:00:00Z",
        mode=HISTORICAL_RECONSTRUCTION,
        exchange_published_at_utc="2026-07-27T14:56:14Z",
        discovery_sha256="a" * 64,
        discovery_path="discovery/a.json",
    )


def test_only_registered_symbol_aliases_are_equivalent():
    assert symbols_equivalent("BAJAJ-AUTO", "BAJAJAUTO")
    assert symbols_equivalent("BAJAJAUTO", "BAJAJ-AUTO")
    assert symbols_equivalent("LTM", "LTIM")
    assert symbols_equivalent("LTIM", "LTM")
    assert symbols_equivalent("ETERNAL", "ZOMATO")
    assert symbols_equivalent("ZOMATO", "ETERNAL")
    assert symbols_equivalent("INFY", "INFY")
    assert not symbols_equivalent("TMPV", "TATAMOTORS")
    assert not symbols_equivalent("TATAMOTORS", "TMPV")
    assert not symbols_equivalent("M&M", "MM")


def test_point_in_time_ticker_can_discover_post_rename_filing_alias():
    assert historical_symbol_variants("ZOMATO") == ("ZOMATO", "ETERNAL")
    assert historical_symbol_variants("ETERNAL") == ("ETERNAL", "ZOMATO")
    assert historical_symbol_variants("LTIM") == ("LTIM", "LTM")
    assert historical_symbol_variants("LTM") == ("LTM", "LTIM")


def test_tata_motors_successor_is_retrieval_only_not_economic_equivalence():
    assert historical_discovery_query_symbols("TATAMOTORS") == ("TATAMOTORS", "TMPV")
    assert historical_symbol_variants("TATAMOTORS") == ("TATAMOTORS",)
    assert not symbols_equivalent("TATAMOTORS", "TMPV")
    assert not symbols_equivalent("TMPV", "TATAMOTORS")


def test_registered_official_source_isin_inconsistencies_are_exact_only():
    assert historical_isins_equivalent("PERSISTENT", "INE262H01016", "INE262H01021")
    assert historical_isins_equivalent("OBEROIRLTY", "INE903I01010", "INE093I01010")
    assert historical_isins_equivalent("TATATECH", "INE142M01017", "INE142M01025")
    assert not historical_isins_equivalent("OBEROIRLTY", "INE903I01010", "INE000000000")
    assert not historical_isins_equivalent("TATATECH", "INE142M01017", "INE142M01099")


def test_tata_motors_predecessor_is_explicitly_non_comparable():
    assert is_non_comparable_predecessor("TMPV", "TATAMOTORS")
    assert not is_non_comparable_predecessor("LTM", "LTIM")


def test_calculation_view_normalizes_symbol_without_changing_evidence_identity():
    event = _event()
    aliased = replace(event, symbol="BAJAJAUTO")
    normalized = normalize_symbol_for_h002(
        aliased,
        canonical_symbol="BAJAJ-AUTO",
    )
    assert normalized.symbol == "BAJAJ-AUTO"
    assert normalized.reporting_quarter == event.reporting_quarter
    assert normalized.reporting_period_end == event.reporting_period_end
    assert normalized.economic_event_id == event.economic_event_id
    assert normalized.version_id == event.version_id
