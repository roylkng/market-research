from __future__ import annotations

from pathlib import Path

import pytest

from marketlab.events import (
    XBRL_PARSER_VERSION,
    EventParseError,
    EventStore,
    parse_indas_xbrl,
    sha256_bytes,
)

FIXTURE = Path("data/fixtures/filings/infy_fy26_q2_consolidated_source_derived.xml")


def _parse(raw: bytes):
    return parse_indas_xbrl(
        raw.decode(),
        source_url="https://example.invalid/infy-q2.xml",
        raw_sha256=sha256_bytes(raw),
        raw_path="raw/infy-q2.xml",
        captured_at_utc="2026-09-06T14:00:00Z",
    )


def test_source_derived_xbrl_parses_primary_quarter_without_ytd_leakage():
    raw = FIXTURE.read_bytes()
    event = _parse(raw)

    assert event.parser_version == XBRL_PARSER_VERSION
    assert event.symbol == "INFY"
    assert event.isin == "INE009A01021"
    assert event.company_name == "INFOSYS LIMITED"
    assert event.accounting_basis == "Consolidated"
    assert event.reporting_quarter == "Second quarter"
    assert event.reporting_period_start == "2025-07-01"
    assert event.reporting_period_end == "2025-09-30"
    assert event.audited is True
    assert event.currency == "INR"
    assert event.rounding == "Crores"
    assert event.revenue_from_operations == 444900000000.0
    assert event.profit_before_tax == 102290000000.0
    assert event.basic_eps == 17.76
    assert event.diluted_eps == 17.74
    assert event.basic_eps != 34.23
    assert event.provenance.content_type == "application/xml"
    assert event.provenance.source_mode == "NSE_INTEGRATED_FILING_XBRL"


def test_event_store_dispatches_xml_and_preserves_exact_raw_bytes(tmp_path):
    raw = FIXTURE.read_bytes()
    event, created = EventStore(tmp_path).reconstruct_bytes(
        raw,
        source_url="https://example.invalid/infy-q2.xml",
    )

    assert created is True
    assert event.parser_version == XBRL_PARSER_VERSION
    assert event.basic_eps == 17.76
    assert Path(event.provenance.raw_path).read_bytes() == raw
    assert event.provenance.raw_sha256 == sha256_bytes(raw)


def test_xbrl_rejects_conflicting_primary_context_fact():
    raw = FIXTURE.read_text(encoding="utf-8")
    conflicting = raw.replace(
        "<in-capmkt:ISIN contextRef=\"OneD\">",
        "<in-capmkt:ISIN contextRef=\"OneD\">INE000000000</in-capmkt:ISIN>"
        "<in-capmkt:ISIN contextRef=\"OneD\">",
        1,
    )

    with pytest.raises(EventParseError, match="conflicting XBRL facts for ISIN"):
        _parse(conflicting.encode())


def test_xbrl_requires_one_unambiguous_symbol_context():
    raw = FIXTURE.read_text(encoding="utf-8")
    ambiguous = raw.replace(
        "</xbrli:xbrl>",
        '<in-capmkt:Symbol contextRef="FourD">INFY</in-capmkt:Symbol></xbrli:xbrl>',
    )

    with pytest.raises(EventParseError, match="one unambiguous Symbol fact"):
        _parse(ambiguous.encode())


def test_xbrl_rejects_non_xbrl_xml_root():
    with pytest.raises(EventParseError, match="root is not an XBRL instance"):
        parse_indas_xbrl(
            "<?xml version='1.0'?><root />",
            source_url="https://example.invalid/not-xbrl.xml",
            raw_sha256="0" * 64,
            raw_path="raw/not-xbrl.xml",
            captured_at_utc="2026-09-06T14:00:00Z",
        )
