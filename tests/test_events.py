from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.events import (
    HISTORICAL_RECONSTRUCTION,
    PROSPECTIVE,
    EventParseError,
    EventStore,
    parse_indas_html,
    sha256_bytes,
)
from marketlab.universe import build_universe_snapshot

FIXTURES = Path("data/fixtures/filings")


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _quote(symbol: str, *, isin: str, macro: str = "Consumer Discretionary") -> dict:
    return {
        "info": {"isin": isin, "listingDate": "01-Jan-2000"},
        "industryInfo": {
            "macro": macro,
            "sector": "Research Sector",
            "industry": "Research Industry",
            "basicIndustry": "Research Basic Industry",
        },
    }


def _ccl_universe(*, captured_at: datetime | None = None):
    index = {"timestamp": "01-Jul-2026 15:30:00", "data": [{"symbol": "CCL", "ffmc": 100}]}
    return build_universe_snapshot(
        index,
        lambda _: _quote("CCL", isin="INE421D01022"),
        cohort_id="FY27-Q1-TEST",
        selection_size=1,
        captured_at=captured_at or datetime(2026, 7, 1, tzinfo=UTC),
    )


def test_ccl_source_derived_fixture_parses_without_reinterpreting_ebitda():
    raw = _fixture("ccl_fy27_q1_consolidated_source_derived.html")
    event = parse_indas_html(
        raw.decode(),
        source_url="https://example.invalid/ccl",
        raw_sha256=sha256_bytes(raw),
        raw_path="raw/ccl.html",
        captured_at_utc="2026-09-06T10:00:00Z",
    )

    assert event.symbol == "CCL"
    assert event.isin == "INE421D01022"
    assert event.accounting_basis == "Consolidated"
    assert event.audited is False
    assert event.currency == "INR"
    assert event.rounding == "Lakhs"
    assert event.reporting_period_end == "30-06-2026"
    assert event.revenue_from_operations == 120044.62
    assert event.profit_before_tax == 12901.75
    assert event.total_profit == 11688.05
    assert event.basic_eps == 8.77
    assert event.diluted_eps == 8.76
    assert event.operating_profit is None
    assert event.operating_margin is None
    assert any(item.startswith("operating_profit:") for item in event.unresolved_fields)


def test_infosys_source_derived_fixture_preserves_audited_q4_and_large_inr_lakh_values():
    raw = _fixture("infy_fy26_q4_consolidated_source_derived.html")
    event = parse_indas_html(
        raw.decode(),
        source_url="https://example.invalid/infy",
        raw_sha256=sha256_bytes(raw),
        raw_path="raw/infy.html",
        captured_at_utc="2026-09-06T10:00:00Z",
    )

    assert event.symbol == "INFY"
    assert event.audited is True
    assert event.reporting_quarter == "Fourth quarter"
    assert event.currency == "INR"
    assert event.rounding == "Lakhs"
    assert event.revenue_from_operations == 4640200.0
    assert event.profit_before_exceptional_items_and_tax == 1079700.0
    assert event.basic_eps == 21.01


def test_shaily_source_derived_fixture_preserves_actuals_not_lakhs():
    raw = _fixture("shaily_fy26_q1_consolidated_source_derived.html")
    event = parse_indas_html(
        raw.decode(),
        source_url="https://example.invalid/shaily",
        raw_sha256=sha256_bytes(raw),
        raw_path="raw/shaily.html",
        captured_at_utc="2026-09-06T10:00:00Z",
    )

    assert event.symbol == "SHAILY"
    assert event.currency == "INR (in Actuals)"
    assert event.rounding is None
    assert event.revenue_from_operations == 2466927000.0
    assert event.total_profit == 411227000.0
    assert event.basic_eps == 8.95


def test_same_source_bytes_are_idempotent_and_preserve_first_capture_timestamp(tmp_path):
    raw = _fixture("ccl_fy27_q1_consolidated_source_derived.html")
    store = EventStore(tmp_path)
    first, created_one = store.reconstruct_bytes(
        raw,
        source_url="https://example.invalid/ccl",
        captured_at=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
    )
    second, created_two = store.reconstruct_bytes(
        raw,
        source_url="https://example.invalid/ccl",
        captured_at=datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
    )

    assert created_one is True
    assert created_two is False
    assert first.version_id == second.version_id
    assert first.provenance.captured_at_utc == "2026-09-06T10:00:00Z"
    assert second.provenance.captured_at_utc == first.provenance.captured_at_utc


def test_changed_source_bytes_create_new_version_of_same_economic_event(tmp_path):
    raw = _fixture("ccl_fy27_q1_consolidated_source_derived.html")
    corrected = raw.replace(b"1,20,044.62", b"1,20,045.62")
    store = EventStore(tmp_path)

    original, _ = store.reconstruct_bytes(raw, source_url="https://example.invalid/ccl")
    revision, created = store.reconstruct_bytes(
        corrected, source_url="https://example.invalid/ccl-revised"
    )

    assert created is True
    assert original.economic_event_id == revision.economic_event_id
    assert original.version_id != revision.version_id
    assert original.provenance.raw_sha256 != revision.provenance.raw_sha256
    assert revision.revenue_from_operations == 120045.62
    versions = list((tmp_path / "events" / original.economic_event_id).glob("*.json"))
    assert len(versions) == 2


def test_reconstruction_mode_is_hard_coded_for_current_store(tmp_path):
    raw = _fixture("shaily_fy26_q1_consolidated_source_derived.html")
    event, _ = EventStore(tmp_path).reconstruct_bytes(
        raw,
        source_url="https://example.invalid/shaily",
    )
    assert event.mode == HISTORICAL_RECONSTRUCTION


def test_prospective_capture_records_discovery_source_and_universe_hashes(tmp_path):
    raw = _fixture("ccl_fy27_q1_consolidated_source_derived.html")
    discovery = b'{"symbol":"CCL","exchdisstime":"27-Jul-2026 20:26:14"}'
    universe = _ccl_universe()
    event, created = EventStore(tmp_path).capture_prospective_bytes(
        raw,
        discovery_bytes=discovery,
        source_url=(
            "https://nsearchives.nseindia.com/corporate/ixbrl/"
            "INTEGRATED_FILING_INDAS_178875_27072026202614_iXBRL_WEB.html"
        ),
        exchange_published_at_utc="2026-07-27T14:56:14Z",
        universe=universe,
        captured_at=datetime(2026, 7, 27, 15, 0, tzinfo=UTC),
    )

    assert created is True
    assert event.mode == PROSPECTIVE
    assert event.schema_version == 2
    assert event.provenance.exchange_published_at_utc == "2026-07-27T14:56:14Z"
    assert event.provenance.discovery_sha256 == sha256_bytes(discovery)
    assert event.provenance.universe_snapshot_sha256 == universe.sha256
    assert event.provenance.cohort_id == "FY27-Q1-TEST"
    assert Path(event.provenance.raw_path).read_bytes() == raw
    assert Path(event.provenance.discovery_path or "").read_bytes() == discovery
    prospective_records = list(
        (tmp_path / "prospective-events" / event.economic_event_id).glob("*.json")
    )
    assert len(prospective_records) == 1


def test_historical_and_prospective_same_bytes_do_not_collapse_namespaces(tmp_path):
    raw = _fixture("ccl_fy27_q1_consolidated_source_derived.html")
    store = EventStore(tmp_path)
    historical, _ = store.reconstruct_bytes(raw, source_url="https://example.invalid/ccl")
    prospective, created = store.capture_prospective_bytes(
        raw,
        discovery_bytes=b'{"symbol":"CCL"}',
        source_url="https://example.invalid/ccl",
        exchange_published_at_utc="2026-07-27T14:56:14Z",
        universe=_ccl_universe(),
        captured_at=datetime(2026, 7, 27, 15, 0, tzinfo=UTC),
    )
    assert created is True
    assert historical.economic_event_id == prospective.economic_event_id
    assert historical.mode == HISTORICAL_RECONSTRUCTION
    assert prospective.mode == PROSPECTIVE
    assert (tmp_path / "events" / historical.economic_event_id).exists()
    assert (tmp_path / "prospective-events" / prospective.economic_event_id).exists()


def test_prospective_capture_rejects_symbol_outside_frozen_universe(tmp_path):
    raw = _fixture("shaily_fy26_q1_consolidated_source_derived.html")
    with pytest.raises(EventParseError, match="SHAILY is not eligible"):
        EventStore(tmp_path).capture_prospective_bytes(
            raw,
            discovery_bytes=b'{"symbol":"SHAILY"}',
            source_url="https://example.invalid/shaily",
            exchange_published_at_utc="2026-07-27T14:56:14Z",
            universe=_ccl_universe(),
            captured_at=datetime(2026, 7, 27, 15, 0, tzinfo=UTC),
        )


def test_prospective_capture_rejects_universe_frozen_after_publication(tmp_path):
    raw = _fixture("ccl_fy27_q1_consolidated_source_derived.html")
    universe = _ccl_universe(captured_at=datetime(2026, 7, 28, tzinfo=UTC))
    with pytest.raises(EventParseError, match="universe snapshot was frozen after"):
        EventStore(tmp_path).capture_prospective_bytes(
            raw,
            discovery_bytes=b'{"symbol":"CCL"}',
            source_url="https://example.invalid/ccl",
            exchange_published_at_utc="2026-07-27T14:56:14Z",
            universe=universe,
            captured_at=datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
        )


def test_prospective_capture_rejects_future_exchange_timestamp(tmp_path):
    raw = _fixture("ccl_fy27_q1_consolidated_source_derived.html")
    with pytest.raises(EventParseError, match="later than local capture time"):
        EventStore(tmp_path).capture_prospective_bytes(
            raw,
            discovery_bytes=b'{"symbol":"CCL"}',
            source_url="https://example.invalid/ccl",
            exchange_published_at_utc="2026-07-27T16:00:00Z",
            universe=_ccl_universe(),
            captured_at=datetime(2026, 7, 27, 15, 0, tzinfo=UTC),
        )


def test_same_prospective_source_bytes_cannot_silently_change_discovery_provenance(tmp_path):
    raw = _fixture("ccl_fy27_q1_consolidated_source_derived.html")
    store = EventStore(tmp_path)
    kwargs = {
        "source_url": "https://example.invalid/ccl",
        "exchange_published_at_utc": "2026-07-27T14:56:14Z",
        "universe": _ccl_universe(),
        "captured_at": datetime(2026, 7, 27, 15, 0, tzinfo=UTC),
    }
    store.capture_prospective_bytes(raw, discovery_bytes=b'{"v":1}', **kwargs)
    with pytest.raises(EventParseError, match="conflicting prospective provenance"):
        store.capture_prospective_bytes(raw, discovery_bytes=b'{"v":2}', **kwargs)
