from __future__ import annotations

import json
from copy import deepcopy
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
    H022P001AcquisitionError,
    build_discovery_manifest,
    build_operational_context,
    build_static_prior_index,
    canonical_hash,
    capture_latency_status,
    catchup_query_dates,
    discovery_complete,
    seal_operational_signal,
    validate_discovery_manifest,
    validate_static_prior_index,
)

UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")


def _universe() -> dict[str, object]:
    payload = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _e002_record(
    *,
    source_id: str,
    symbol: str = "ABB",
    published: str,
    text_chars: int = 1000,
    raw_char: str = "a",
    text_char: str = "b",
) -> dict[str, object]:
    raw_sha = raw_char * 64
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
        "attachment_url": f"https://nsearchives.nseindia.com/{source_id}.pdf",
        "status": "TEXT_READY",
        "failure_reason": None,
        "raw_sha256": raw_sha,
        "raw_byte_count": 1234,
        "parser_version": PARSER_VERSION,
        "parser_library_version": PARSER_LIBRARY_VERSION,
        "page_count": 1,
        "text_sha256": text_char * 64,
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


def _catchup_source(*, symbol: str = "ABB", seq_id: str = "ctx-1") -> dict[str, str]:
    published = "2026-09-10T03:00:00Z"
    attachment = f"https://nsearchives.nseindia.com/{seq_id}.pdf"
    discovery_sha = "d" * 64
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


def _complete_manifest_rows(source: dict[str, str] | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for member in _universe()["members"]:
        symbol = str(member["symbol"])
        sources = [source] if source is not None and symbol == source["symbol"] else []
        rows.append(
            {
                "symbol": symbol,
                "coverage_status": "COMPLETE",
                "incomplete_reason": None,
                "discovery_sha256": canonical_hash({"symbol": symbol, "probe": 1}),
                "source_count": len(sources),
                "sources": sources,
            }
        )
    return rows


def test_catchup_query_dates_cover_exact_india_dates() -> None:
    assert tuple(item.isoformat() for item in catchup_query_dates()) == (
        "2026-09-06",
        "2026-09-14",
    )


def test_full_u001_discovery_manifest_is_hashed_and_complete() -> None:
    universe = _universe()
    source = _catchup_source()
    manifest = build_discovery_manifest(
        universe_snapshot=universe,
        rows=_complete_manifest_rows(source),
        generated_at_utc="2026-09-14T18:31:00Z",
    )
    validate_discovery_manifest(manifest, universe)
    assert discovery_complete(manifest)
    assert manifest["member_count"] == 100
    assert manifest["catchup_source_ids"] == [source["source_id"]]


def test_incomplete_discovery_cannot_seal_operational_context() -> None:
    universe = _universe()
    rows = _complete_manifest_rows()
    rows[0] = {
        "symbol": rows[0]["symbol"],
        "coverage_status": "INCOMPLETE",
        "incomplete_reason": "NSE acquisition unavailable",
        "discovery_sha256": None,
        "source_count": 0,
        "sources": [],
    }
    manifest = build_discovery_manifest(
        universe_snapshot=universe,
        rows=rows,
        generated_at_utc="2026-09-14T18:31:00Z",
    )
    assert not discovery_complete(manifest)
    with pytest.raises(H022P001AcquisitionError, match="discovery is incomplete"):
        build_operational_context(
            universe_snapshot=universe,
            discovery_manifest=manifest,
            historical_records=[],
            catchup_records=[],
            completed_at_utc="2026-09-14T18:31:00Z",
        )


def test_static_prior_index_uses_latest_prestart_timestamp_group() -> None:
    universe = _universe()
    historical = _e002_record(
        source_id="1" * 64,
        published="2026-09-05T03:00:00Z",
        raw_char="a",
        text_char="b",
    )
    source = _catchup_source()
    catchup = _e002_record(
        source_id=source["source_id"],
        published=source["exchange_published_at_utc"],
        raw_char="c",
        text_char="d",
    )
    index = build_static_prior_index(
        universe_snapshot=universe,
        historical_records=[historical],
        catchup_records=[catchup],
        built_at_utc="2026-09-14T18:31:00Z",
    )
    validate_static_prior_index(index, universe)
    abb = next(row for row in index["entries"] if row["symbol"] == "ABB")
    assert abb["status"] == "UNIQUE_PRIOR"
    assert abb["latest_prior_timestamp_utc"] == source["exchange_published_at_utc"]
    assert abb["records"][0]["source_id"] == source["source_id"]
    assert abb["records"][0]["disposition"] == "CONTEXT_ONLY_PRE_START"


def test_static_prior_index_preserves_latest_timestamp_ambiguity() -> None:
    universe = _universe()
    first = _e002_record(
        source_id="1" * 64,
        published="2026-09-05T03:00:00Z",
        raw_char="a",
        text_char="b",
    )
    second = _e002_record(
        source_id="2" * 64,
        published="2026-09-05T03:00:00Z",
        raw_char="c",
        text_char="d",
    )
    index = build_static_prior_index(
        universe_snapshot=universe,
        historical_records=[first, second],
        catchup_records=[],
        built_at_utc="2026-09-14T18:31:00Z",
    )
    abb = next(row for row in index["entries"] if row["symbol"] == "ABB")
    assert abb["status"] == "AMBIGUOUS_PRIOR_TIMESTAMP"
    assert len(abb["records"]) == 2


def test_operational_signal_refuses_omitted_frozen_prior() -> None:
    universe = _universe()
    source = _catchup_source()
    catchup = _e002_record(
        source_id=source["source_id"],
        published=source["exchange_published_at_utc"],
        text_chars=2000,
        raw_char="c",
        text_char="d",
    )
    manifest = build_discovery_manifest(
        universe_snapshot=universe,
        rows=_complete_manifest_rows(source),
        generated_at_utc="2026-09-14T18:31:00Z",
    )
    gate, prior_index, operational = build_operational_context(
        universe_snapshot=universe,
        discovery_manifest=manifest,
        historical_records=[],
        catchup_records=[catchup],
        completed_at_utc="2026-09-14T18:31:00Z",
    )
    current = _e002_record(
        source_id="3" * 64,
        published="2026-09-15T03:00:00Z",
        text_chars=1000,
        raw_char="e",
        text_char="f",
    )
    with pytest.raises(H022P001AcquisitionError, match="omits frozen static prior"):
        seal_operational_signal(
            current_record=current,
            context_records=[],
            universe_snapshot=universe,
            core_gate=gate,
            discovery_manifest=manifest,
            prior_index=prior_index,
            operational_context=operational,
            signal_frozen_at_utc="2026-09-15T04:00:00Z",
        )

    sealed = seal_operational_signal(
        current_record=current,
        context_records=[catchup],
        universe_snapshot=universe,
        core_gate=gate,
        discovery_manifest=manifest,
        prior_index=prior_index,
        operational_context=operational,
        signal_frozen_at_utc="2026-09-15T04:00:00Z",
    )
    assert sealed["signal_status"] == "SIGNAL"
    assert sealed["prior_source_id"] == catchup["source_id"]
    assert sealed["prior_index_sha256"] == prior_index["prior_index_sha256"]
    prospective.validate_signal_record(sealed)


def test_operational_context_requires_exact_discovered_catchup_set() -> None:
    universe = _universe()
    source = _catchup_source()
    manifest = build_discovery_manifest(
        universe_snapshot=universe,
        rows=_complete_manifest_rows(source),
        generated_at_utc="2026-09-14T18:31:00Z",
    )
    with pytest.raises(H022P001AcquisitionError, match="extraction set differs"):
        build_operational_context(
            universe_snapshot=universe,
            discovery_manifest=manifest,
            historical_records=[],
            catchup_records=[],
            completed_at_utc="2026-09-14T18:31:00Z",
        )


def test_capture_latency_status_fails_late_freeze() -> None:
    assert (
        capture_latency_status(
            signal_frozen_at_utc="2026-09-15T03:30:00Z",
            nominal_entry_open_utc="2026-09-15T03:45:00Z",
        )
        == "EXECUTABLE_AT_H022_X001_ENTRY"
    )
    assert (
        capture_latency_status(
            signal_frozen_at_utc="2026-09-15T04:00:00Z",
            nominal_entry_open_utc="2026-09-15T03:45:00Z",
        )
        == "LATE_SIGNAL_FREEZE"
    )


def test_prior_index_digest_detects_mutation() -> None:
    index = build_static_prior_index(
        universe_snapshot=_universe(),
        historical_records=[],
        catchup_records=[],
        built_at_utc="2026-09-14T18:31:00Z",
    )
    changed = deepcopy(index)
    changed["entries"][0]["status"] = "UNIQUE_PRIOR"
    with pytest.raises(H022P001AcquisitionError, match="digest mismatch"):
        validate_static_prior_index(changed, _universe())
