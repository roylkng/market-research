from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from marketlab.events import HISTORICAL_RECONSTRUCTION, parse_indas_html, sha256_bytes
from marketlab.h002_historical_identity import (
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
    assert symbols_equivalent("LTM", "LTIM")
    assert symbols_equivalent("INFY", "INFY")
    assert not symbols_equivalent("TMPV", "TATAMOTORS")
    assert not symbols_equivalent("M&M", "MM")


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
