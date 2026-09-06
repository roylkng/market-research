from datetime import UTC, datetime

import pytest

from marketlab.h003_sources import (
    SOURCE_RULE_SHA256,
    H003SourceError,
    build_coverage_bundle,
    build_coverage_record,
    load_and_validate_source_rule,
    select_transcript_sources,
)
from marketlab.universe import build_universe_snapshot
from tests.universe_fixtures import make_nifty200_sources


def _row(
    *,
    symbol="INFY",
    seq="1",
    timestamp="28-Jul-2026 20:24:54",
    text="Infosys Limited has informed the Exchange regarding 'Earnings Call Transcript'.",
    desc="Updates",
    url="https://nsearchives.nseindia.com/corporate/infy-transcript.pdf",
):
    return {
        "symbol": symbol,
        "seq_id": seq,
        "exchdisstime": timestamp,
        "attchmntText": text,
        "desc": desc,
        "attchmntFile": url,
    }


def _universe():
    index, constituents = make_nifty200_sources(
        [
            {
                "symbol": "INFY",
                "ffmc": 1000,
                "industry": "Information Technology",
                "isin": "INE009A01021",
                "company_name": "Infosys Ltd.",
            },
            {
                "symbol": "RELIANCE",
                "ffmc": 900,
                "industry": "Oil Gas & Consumable Fuels",
                "isin": "INE002A01018",
                "company_name": "Reliance Industries Ltd.",
            },
        ]
    )
    return build_universe_snapshot(
        index,
        constituents,
        cohort_id="FY27-Q2-2026-09-06",
        selection_size=2,
        captured_at=datetime(2026, 9, 6, 12, 21, tzinfo=UTC),
    )


def test_frozen_h003_source_rule_hash_validates():
    document = load_and_validate_source_rule("registry/h003_source_rule.yaml")
    assert document["sha256"] == SOURCE_RULE_SHA256
    assert document["live_capital"] is False


def test_selects_results_call_transcripts_and_excludes_non_results_transcripts():
    payload = [
        _row(seq="1"),
        _row(
            seq="2",
            text="Transcript of the 45th Annual General Meeting",
            url="https://nsearchives.nseindia.com/corporate/agm.pdf",
        ),
        _row(
            seq="3",
            text="Transcript of Investor AI Day 2026",
            url="https://nsearchives.nseindia.com/corporate/ai-day.pdf",
        ),
        _row(
            seq="4",
            desc="Investor Presentation",
            text="Investor Presentation for financial results",
            url="https://nsearchives.nseindia.com/corporate/presentation.pdf",
        ),
        _row(
            seq="5",
            text="Transcript of the discussion on the financial results for the quarter ended June 30, 2026",
            url="https://nsearchives.nseindia.com/corporate/results-transcript.pdf",
        ),
    ]
    selected = select_transcript_sources(payload, symbol="INFY")
    assert [item.seq_id for item in selected] == ["1", "5"]


def test_source_window_is_enforced_on_exchange_timestamp():
    payload = [
        _row(seq="old", timestamp="31-Aug-2024 23:59:59"),
        _row(seq="inside", timestamp="01-Sep-2024 00:00:00", url="https://nsearchives.nseindia.com/corporate/inside.pdf"),
        _row(seq="late", timestamp="07-Sep-2026 00:00:00", url="https://nsearchives.nseindia.com/corporate/late.pdf"),
    ]
    assert [item.seq_id for item in select_transcript_sources(payload, symbol="INFY")] == ["inside"]


def test_conflicting_duplicate_attachment_fails_closed():
    shared = "https://nsearchives.nseindia.com/corporate/shared.pdf"
    with pytest.raises(H003SourceError, match="ambiguous duplicate"):
        select_transcript_sources(
            [_row(seq="1", url=shared), _row(seq="2", url=shared)],
            symbol="INFY",
        )


def test_zero_matching_transcripts_is_complete_zero_source():
    raw = b'[{"symbol":"INFY","desc":"Investor Presentation"}]'
    record = build_coverage_record(
        [{"symbol": "INFY", "desc": "Investor Presentation"}],
        raw,
        symbol="INFY",
        captured_at=datetime(2026, 9, 6, 13, tzinfo=UTC),
    )
    assert record.coverage_status == "COMPLETE_ZERO_SOURCE"
    assert record.source_count == 0
    assert record.discovery_sha256 is not None


def test_bundle_requires_exact_frozen_universe_partition():
    universe = _universe()
    infy = build_coverage_record(
        [_row()],
        b"infy",
        symbol="INFY",
        captured_at=datetime(2026, 9, 6, 13, tzinfo=UTC),
    )
    reliance = build_coverage_record(
        [],
        b"reliance",
        symbol="RELIANCE",
        captured_at=datetime(2026, 9, 6, 13, tzinfo=UTC),
    )
    bundle = build_coverage_bundle(
        [infy, reliance],
        universe=universe,
        generated_at=datetime(2026, 9, 6, 14, tzinfo=UTC),
    )
    assert bundle.member_count == 2
    assert bundle.complete_count == 1
    assert bundle.complete_zero_source_count == 1
    assert bundle.incomplete_count == 0
    assert bundle.transcript_source_count == 1
