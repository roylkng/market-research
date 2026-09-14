from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketlab import h022_prospective as prospective
from marketlab.h003_candidates import (
    CANDIDATE_VERSION,
    COMMITMENT_DOMAIN_MARKERS,
    DEADLINE_MARKERS,
    EXTRACTION_RULE_ID,
    EXTRACTION_RULE_SHA256,
    FUTURE_MARKERS,
    PARSER_LIBRARY_VERSION,
    PARSER_VERSION,
    QUANTITATIVE_PATTERN,
)
from marketlab.h003_sources import SOURCE_RULE_ID
from marketlab.h022_p001_acquisition import (
    build_discovery_manifest,
    build_operational_context,
    canonical_hash,
)
from marketlab.h022_p001_stream import (
    H022P001StreamError,
    RetroactiveSourceGap,
    append_e002_record,
    append_sources,
    build_scan_manifest,
    new_e002_ledger,
    new_source_ledger,
    scan_complete,
    seal_pending_signals,
    unresolved_prior_source_ids,
    unresolved_source_records,
    validate_e002_ledger,
    validate_scan_manifest,
    validate_source_ledger,
    validate_stream_consistency,
)

UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")


def _universe() -> dict[str, object]:
    payload = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _source(
    *, symbol: str = "ABB", seq_id: str, published: str
) -> dict[str, object]:
    attachment = f"https://nsearchives.nseindia.com/{seq_id}.pdf"
    discovery_sha = canonical_hash({"seq_id": seq_id, "symbol": symbol})
    identity = {
        "rule_id": SOURCE_RULE_ID,
        "symbol": symbol,
        "seq_id": seq_id,
        "exchange_published_at_utc": published,
        "attachment_url": attachment,
        "discovery_row_sha256": discovery_sha,
    }
    return {
        "schema_version": 1,
        "source_id": canonical_hash(identity),
        "symbol": symbol,
        "seq_id": seq_id,
        "exchange_published_at_utc": published,
        "attachment_url": attachment,
        "announcement_description": "Analysts/Institutional Investor Meet/Con. Call Updates",
        "attachment_text": "Transcript of earnings conference call",
        "discovery_row_sha256": discovery_sha,
    }


def _e002(source: dict[str, object], *, text_chars: int = 1000) -> dict[str, object]:
    source_id = str(source["source_id"])
    symbol = str(source["symbol"])
    published = str(source["exchange_published_at_utc"])
    raw_sha = canonical_hash({"raw": source_id})
    text_sha = canonical_hash({"text": source_id})
    excerpt = "We expect revenue growth of 20% next year."
    lowered = excerpt.casefold()
    candidate: dict[str, object] = {
        "candidate_id": "",
        "rule_id": EXTRACTION_RULE_ID,
        "rule_sha256": EXTRACTION_RULE_SHA256,
        "candidate_version": CANDIDATE_VERSION,
        "source_id": source_id,
        "symbol": symbol,
        "exchange_published_at_utc": published,
        "raw_sha256": raw_sha,
        "parser_version": PARSER_VERSION,
        "page_number": 1,
        "line_start": 1,
        "line_end": 1,
        "excerpt": excerpt,
        "future_markers": [marker for marker in FUTURE_MARKERS if marker in lowered],
        "deadline_markers": [marker for marker in DEADLINE_MARKERS if marker in lowered],
        "domain_markers": [
            marker for marker in COMMITMENT_DOMAIN_MARKERS if marker in lowered
        ],
        "quantitative_tokens": [
            token.strip()
            for token in QUANTITATIVE_PATTERN.findall(excerpt)
            if token.strip()
        ],
        "disposition": "UNREVIEWED",
        "disposition_reason": None,
    }
    candidate["candidate_id"] = prospective._canonical_hash(
        {
            "rule_id": EXTRACTION_RULE_ID,
            "rule_sha256": EXTRACTION_RULE_SHA256,
            "candidate_version": CANDIDATE_VERSION,
            "source_id": source_id,
            "symbol": symbol,
            "raw_sha256": raw_sha,
            "page_number": 1,
            "line_start": 1,
            "line_end": 1,
            "excerpt": excerpt,
        }
    )
    record: dict[str, object] = {
        "schema_version": 1,
        "record_id": "",
        "rule_id": EXTRACTION_RULE_ID,
        "rule_sha256": EXTRACTION_RULE_SHA256,
        "source_id": source_id,
        "symbol": symbol,
        "exchange_published_at_utc": published,
        "attachment_url": source["attachment_url"],
        "status": "TEXT_READY",
        "failure_reason": None,
        "raw_sha256": raw_sha,
        "raw_byte_count": 1000,
        "parser_version": PARSER_VERSION,
        "parser_library_version": PARSER_LIBRARY_VERSION,
        "page_count": 1,
        "text_sha256": text_sha,
        "text_char_count": text_chars,
        "candidate_count": 1,
        "candidates": [candidate],
        "raw_path": f"raw/{source_id}.pdf",
        "text_path": f"text/{source_id}.txt",
    }
    unsigned = dict(record)
    unsigned.pop("record_id")
    record["record_id"] = prospective._canonical_hash(unsigned)
    prospective.validate_e002_record(record)
    return record


def _complete_scan_rows(sources: list[dict[str, object]]) -> list[dict[str, object]]:
    by_symbol: dict[str, list[dict[str, object]]] = {}
    for source in sources:
        by_symbol.setdefault(str(source["symbol"]), []).append(source)
    rows: list[dict[str, object]] = []
    for member in _universe()["members"]:
        symbol = str(member["symbol"])
        selected = by_symbol.get(symbol, [])
        rows.append(
            {
                "symbol": symbol,
                "coverage_status": "COMPLETE",
                "incomplete_reason": None,
                "discovery_sha256": canonical_hash({"scan": symbol}),
                "source_count": len(selected),
                "sources": selected,
            }
        )
    return rows


def _context() -> tuple[dict, dict, dict, dict]:
    universe = _universe()
    manifest = build_discovery_manifest(
        universe_snapshot=universe,
        rows=[
            {
                "symbol": str(member["symbol"]),
                "coverage_status": "COMPLETE",
                "incomplete_reason": None,
                "discovery_sha256": canonical_hash({"context": member["symbol"]}),
                "source_count": 0,
                "sources": [],
            }
            for member in universe["members"]
        ],
        generated_at_utc="2026-09-14T18:31:00Z",
    )
    gate, prior_index, operational = build_operational_context(
        universe_snapshot=universe,
        discovery_manifest=manifest,
        historical_records=[],
        catchup_records=[],
        completed_at_utc="2026-09-14T18:31:00Z",
    )
    return manifest, gate, prior_index, operational


def test_empty_stream_ledgers_are_hashed_and_valid() -> None:
    source = new_source_ledger()
    e002 = new_e002_ledger()
    validate_source_ledger(source)
    validate_e002_ledger(e002)
    assert source["record_count"] == 0
    assert e002["record_count"] == 0


def test_scan_manifest_requires_full_u001_accounting() -> None:
    source = _source(seq_id="s1", published="2026-09-15T02:00:00Z")
    manifest = build_scan_manifest(
        universe_snapshot=_universe(),
        cutoff_utc="2026-09-15T03:00:00Z",
        completed_at_utc="2026-09-15T03:01:00Z",
        rows=_complete_scan_rows([source]),
    )
    validate_scan_manifest(manifest, _universe())
    assert scan_complete(manifest)
    assert manifest["source_ids"] == [source["source_id"]]

    rows = _complete_scan_rows([])
    rows[0] = {
        "symbol": rows[0]["symbol"],
        "coverage_status": "INCOMPLETE",
        "incomplete_reason": "NSE unavailable",
        "discovery_sha256": None,
        "source_count": 0,
        "sources": [],
    }
    incomplete = build_scan_manifest(
        universe_snapshot=_universe(),
        cutoff_utc="2026-09-15T03:00:00Z",
        completed_at_utc="2026-09-15T03:01:00Z",
        rows=rows,
    )
    assert not scan_complete(incomplete)


def test_source_and_e002_ledgers_are_idempotent() -> None:
    source = _source(seq_id="s1", published="2026-09-15T02:00:00Z")
    source_ledger = append_sources(
        new_source_ledger(),
        [source],
        first_seen_at_utc="2026-09-15T03:00:00Z",
    )
    same = append_sources(
        source_ledger,
        [source],
        first_seen_at_utc="2026-09-15T04:00:00Z",
    )
    assert same == source_ledger

    record = _e002(source)
    e002_ledger = append_e002_record(new_e002_ledger(), record)
    assert append_e002_record(e002_ledger, record) == e002_ledger
    validate_stream_consistency(
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
        signal_ledger=prospective.new_signal_ledger(),
    )


def test_unresolved_source_blocks_later_same_symbol_signal() -> None:
    missing = _source(seq_id="missing", published="2026-09-15T02:00:00Z")
    later = _source(seq_id="later", published="2026-09-16T02:00:00Z")
    source_ledger = append_sources(
        new_source_ledger(),
        [missing, later],
        first_seen_at_utc="2026-09-16T03:00:00Z",
    )
    e002_ledger = append_e002_record(new_e002_ledger(), _e002(later))
    unresolved = unresolved_prior_source_ids(
        current_record=e002_ledger["records"][0],
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
    )
    assert unresolved == [missing["source_id"]]

    manifest, gate, prior_index, operational = _context()
    signals, blocked = seal_pending_signals(
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
        signal_ledger=prospective.new_signal_ledger(),
        static_prior_records=[],
        universe_snapshot=_universe(),
        core_gate=gate,
        discovery_manifest=manifest,
        prior_index=prior_index,
        operational_context=operational,
        frozen_at_utc="2026-09-16T03:30:00Z",
    )
    assert signals["record_count"] == 0
    assert blocked[0]["reason"] == "UNRESOLVED_EARLIER_SOURCE"
    assert blocked[0]["unresolved_prior_source_ids"] == [missing["source_id"]]


def test_resolving_gap_allows_chronological_signal_sealing() -> None:
    first = _source(seq_id="first", published="2026-09-15T02:00:00Z")
    second = _source(seq_id="second", published="2026-09-16T02:00:00Z")
    source_ledger = append_sources(
        new_source_ledger(),
        [first, second],
        first_seen_at_utc="2026-09-16T03:00:00Z",
    )
    e002_ledger = new_e002_ledger()
    e002_ledger = append_e002_record(e002_ledger, _e002(first, text_chars=2000))
    e002_ledger = append_e002_record(e002_ledger, _e002(second, text_chars=1000))
    manifest, gate, prior_index, operational = _context()
    signals, blocked = seal_pending_signals(
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
        signal_ledger=prospective.new_signal_ledger(),
        static_prior_records=[],
        universe_snapshot=_universe(),
        core_gate=gate,
        discovery_manifest=manifest,
        prior_index=prior_index,
        operational_context=operational,
        frozen_at_utc="2026-09-16T03:30:00Z",
    )
    assert blocked == []
    assert signals["record_count"] == 2
    first_signal, second_signal = signals["records"]
    assert first_signal["signal_status"] == "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
    assert second_signal["signal_status"] == "SIGNAL"
    assert second_signal["prior_source_id"] == first["source_id"]
    validate_stream_consistency(
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
        signal_ledger=signals,
    )


def test_equal_timestamp_unresolved_source_does_not_block_peer_current() -> None:
    first = _source(seq_id="same-a", published="2026-09-15T02:00:00Z")
    second = _source(seq_id="same-b", published="2026-09-15T02:00:00Z")
    source_ledger = append_sources(
        new_source_ledger(),
        [first, second],
        first_seen_at_utc="2026-09-15T03:00:00Z",
    )
    e002_ledger = append_e002_record(new_e002_ledger(), _e002(first))
    assert unresolved_prior_source_ids(
        current_record=e002_ledger["records"][0],
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
    ) == []
    assert [
        row["source"]["source_id"]
        for row in unresolved_source_records(source_ledger, e002_ledger)
    ] == [second["source_id"]]


def test_backfilled_source_before_sealed_signal_is_integrity_break() -> None:
    current = _source(seq_id="current", published="2026-09-16T02:00:00Z")
    source_ledger = append_sources(
        new_source_ledger(),
        [current],
        first_seen_at_utc="2026-09-16T03:00:00Z",
    )
    record = _e002(current)
    e002_ledger = append_e002_record(new_e002_ledger(), record)
    manifest, gate, prior_index, operational = _context()
    signals, _ = seal_pending_signals(
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
        signal_ledger=prospective.new_signal_ledger(),
        static_prior_records=[],
        universe_snapshot=_universe(),
        core_gate=gate,
        discovery_manifest=manifest,
        prior_index=prior_index,
        operational_context=operational,
        frozen_at_utc="2026-09-16T03:30:00Z",
    )
    older = _source(seq_id="backfill", published="2026-09-15T02:00:00Z")
    with pytest.raises(RetroactiveSourceGap, match="predates an already sealed"):
        append_sources(
            source_ledger,
            [older],
            first_seen_at_utc="2026-09-17T03:00:00Z",
            signal_ledger=signals,
        )


def test_source_identity_drift_same_seq_is_rejected() -> None:
    original = _source(seq_id="stable", published="2026-09-15T02:00:00Z")
    ledger = append_sources(
        new_source_ledger(),
        [original],
        first_seen_at_utc="2026-09-15T03:00:00Z",
    )
    changed = dict(original)
    changed["discovery_row_sha256"] = "f" * 64
    identity = {
        "rule_id": SOURCE_RULE_ID,
        "symbol": changed["symbol"],
        "seq_id": changed["seq_id"],
        "exchange_published_at_utc": changed["exchange_published_at_utc"],
        "attachment_url": changed["attachment_url"],
        "discovery_row_sha256": changed["discovery_row_sha256"],
    }
    changed["source_id"] = canonical_hash(identity)
    with pytest.raises(H022P001StreamError, match="identity drift"):
        append_sources(
            ledger,
            [changed],
            first_seen_at_utc="2026-09-16T03:00:00Z",
        )
