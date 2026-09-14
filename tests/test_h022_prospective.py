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

UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")


def _universe() -> dict[str, object]:
    payload = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _e002_record(
    *,
    source_id: str,
    symbol: str = "ABB",
    published: str = "2026-09-15T03:00:00Z",
    text_chars: int = 1000,
    raw_char: str = "a",
    text_char: str = "b",
) -> dict[str, object]:
    raw_sha = raw_char * 64
    excerpt = "We expect revenue growth of 20% next year."
    lowered = excerpt.casefold()
    future_markers = [marker for marker in FUTURE_MARKERS if marker in lowered]
    deadline_markers = [marker for marker in DEADLINE_MARKERS if marker in lowered]
    domain_markers = [marker for marker in COMMITMENT_DOMAIN_MARKERS if marker in lowered]
    quantitative_tokens = [
        token.strip()
        for token in QUANTITATIVE_PATTERN.findall(excerpt)
        if token.strip()
    ]
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
        "future_markers": future_markers,
        "deadline_markers": deadline_markers,
        "domain_markers": domain_markers,
        "quantitative_tokens": quantitative_tokens,
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
    return record


def _gate(universe: dict[str, object]) -> dict[str, object]:
    symbols = [str(row["symbol"]) for row in universe["members"]]
    return prospective.build_context_gate(
        universe_snapshot=universe,
        discovery_manifest_sha256="d" * 64,
        covered_symbols=symbols,
        catchup_source_ids=[],
        completed_at_utc="2026-09-14T18:31:00Z",
    )


def _seal(
    current: dict[str, object],
    context: list[dict[str, object]],
    universe: dict[str, object],
    gate: dict[str, object],
) -> dict[str, object]:
    return prospective.seal_signal_record(
        current_record=current,
        context_records=context,
        universe_snapshot=universe,
        context_gate=gate,
        signal_frozen_at_utc="2026-09-15T04:00:00Z",
    )


def test_frozen_u001_snapshot_validates() -> None:
    members = prospective.validate_universe_snapshot(_universe())
    assert len(members) == 100
    assert "ABB" in members


def test_u001_rejects_financial_services_member(monkeypatch: pytest.MonkeyPatch) -> None:
    universe = _universe()
    universe["members"][0]["constituent_industry"] = "Financial Services"
    unsigned = dict(universe)
    unsigned.pop("sha256", None)
    tampered_sha = prospective._canonical_hash(unsigned)
    universe["sha256"] = tampered_sha
    monkeypatch.setattr(prospective, "COHORT_SHA256", tampered_sha)
    with pytest.raises(prospective.H022ProspectiveError, match="financial company"):
        prospective.validate_universe_snapshot(universe)


def test_e002_record_and_candidate_digests_are_verified() -> None:
    record = _e002_record(source_id="valid")
    prospective.validate_e002_record(record)

    semantic_tamper = deepcopy(record)
    semantic_tamper["candidates"][0]["excerpt"] = (
        "We expect revenue growth of 25% next year."
    )
    unsigned = dict(semantic_tamper)
    unsigned.pop("record_id")
    semantic_tamper["record_id"] = prospective._canonical_hash(unsigned)
    with pytest.raises(prospective.H022ProspectiveError):
        prospective.validate_e002_record(semantic_tamper)

    stale_candidate_digest = deepcopy(record)
    stale_candidate_digest["candidates"][0]["excerpt"] = (
        "We expect revenue growth of 20% next year. "
    )
    unsigned = dict(stale_candidate_digest)
    unsigned.pop("record_id")
    stale_candidate_digest["record_id"] = prospective._canonical_hash(unsigned)
    with pytest.raises(prospective.H022ProspectiveError, match="candidate digest mismatch"):
        prospective.validate_e002_record(stale_candidate_digest)


def test_e002_accepts_anchor_only_future_markers_when_excerpt_has_more() -> None:
    record = _e002_record(source_id="anchor-only")
    candidate = record["candidates"][0]
    anchor = "We expect revenue growth of 20% next year."
    excerpt = f"{anchor} We plan capacity expansion."
    lowered = excerpt.casefold()
    candidate["excerpt"] = excerpt
    candidate["line_end"] = 2
    candidate["future_markers"] = [
        marker for marker in FUTURE_MARKERS if marker in anchor.casefold()
    ]
    candidate["deadline_markers"] = [
        marker for marker in DEADLINE_MARKERS if marker in lowered
    ]
    candidate["domain_markers"] = [
        marker for marker in COMMITMENT_DOMAIN_MARKERS if marker in lowered
    ]
    candidate["quantitative_tokens"] = [
        token.strip()
        for token in QUANTITATIVE_PATTERN.findall(excerpt)
        if token.strip()
    ]
    all_excerpt_future = [marker for marker in FUTURE_MARKERS if marker in lowered]
    assert len(all_excerpt_future) > len(candidate["future_markers"])
    candidate["candidate_id"] = prospective._canonical_hash(
        {
            "rule_id": EXTRACTION_RULE_ID,
            "rule_sha256": EXTRACTION_RULE_SHA256,
            "candidate_version": CANDIDATE_VERSION,
            "source_id": record["source_id"],
            "symbol": record["symbol"],
            "raw_sha256": record["raw_sha256"],
            "page_number": candidate["page_number"],
            "line_start": candidate["line_start"],
            "line_end": candidate["line_end"],
            "excerpt": excerpt,
        }
    )
    unsigned = dict(record)
    unsigned.pop("record_id")
    record["record_id"] = prospective._canonical_hash(unsigned)
    prospective.validate_e002_record(record)


def test_pre_start_source_is_not_prospectively_eligible() -> None:
    universe = _universe()
    current = _e002_record(
        source_id="prestart",
        published="2026-09-14T18:29:59Z",
    )
    with pytest.raises(prospective.H022ProspectiveError, match="not prospectively eligible"):
        _seal(current, [], universe, _gate(universe))


def test_incomplete_context_gate_blocks_signal() -> None:
    universe = _universe()
    gate = _gate(universe)
    gate["status"] = "PENDING"
    unsigned = dict(gate)
    unsigned.pop("context_gate_sha256")
    gate["context_gate_sha256"] = prospective._canonical_hash(unsigned)
    current = _e002_record(source_id="current")
    with pytest.raises(prospective.H022ProspectiveError, match="not complete"):
        _seal(current, [], universe, gate)


def test_no_prior_is_explicit_no_signal() -> None:
    universe = _universe()
    record = _seal(
        _e002_record(source_id="current"),
        [],
        universe,
        _gate(universe),
    )
    assert record["signal_status"] == "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
    assert record["primary_signal"] is None
    assert record["deltas"] is None


def test_signal_uses_latest_strictly_earlier_prior_and_exact_density_delta() -> None:
    universe = _universe()
    older = _e002_record(
        source_id="older",
        published="2026-08-01T03:00:00Z",
        text_chars=500,
        raw_char="c",
        text_char="d",
    )
    latest = _e002_record(
        source_id="latest",
        published="2026-09-10T03:00:00Z",
        text_chars=2000,
        raw_char="e",
        text_char="f",
    )
    current = _e002_record(source_id="current", text_chars=1000)
    record = _seal(current, [older, latest], universe, _gate(universe))

    assert record["signal_status"] == "SIGNAL"
    assert record["prior_source_id"] == "latest"
    assert record["prior_source_disposition"] == "CONTEXT_ONLY_PRE_START"
    assert record["primary_signal"] == pytest.approx(5.0)
    assert record["deltas"]["forward_commitment_density_delta"] == pytest.approx(5.0)


def test_latest_earlier_multi_source_timestamp_is_ambiguous() -> None:
    universe = _universe()
    prior_a = _e002_record(
        source_id="prior-a",
        published="2026-09-10T03:00:00Z",
        raw_char="c",
        text_char="d",
    )
    prior_b = _e002_record(
        source_id="prior-b",
        published="2026-09-10T03:00:00Z",
        raw_char="e",
        text_char="f",
    )
    record = _seal(
        _e002_record(source_id="current"),
        [prior_a, prior_b],
        universe,
        _gate(universe),
    )
    assert record["signal_status"] == "NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP"
    assert record["prior_group_source_ids"] == ["prior-a", "prior-b"]


def test_multiple_current_sources_at_same_timestamp_share_unique_prior() -> None:
    universe = _universe()
    gate = _gate(universe)
    prior = _e002_record(
        source_id="prior",
        published="2026-09-10T03:00:00Z",
        text_chars=2000,
        raw_char="c",
        text_char="d",
    )
    current_a = _e002_record(
        source_id="current-a",
        raw_char="e",
        text_char="f",
    )
    current_b = _e002_record(
        source_id="current-b",
        raw_char="1",
        text_char="2",
    )
    sealed_a = _seal(current_a, [prior, current_b], universe, gate)
    sealed_b = _seal(current_b, [prior, current_a], universe, gate)
    assert sealed_a["signal_status"] == "SIGNAL"
    assert sealed_b["signal_status"] == "SIGNAL"
    assert sealed_a["prior_source_id"] == "prior"
    assert sealed_b["prior_source_id"] == "prior"


def test_future_context_is_rejected() -> None:
    universe = _universe()
    current = _e002_record(source_id="current")
    future = _e002_record(
        source_id="future",
        published="2026-09-16T03:00:00Z",
        raw_char="c",
        text_char="d",
    )
    with pytest.raises(prospective.H022ProspectiveError, match="future context"):
        _seal(current, [future], universe, _gate(universe))


def test_signal_record_hash_is_deterministic() -> None:
    universe = _universe()
    gate = _gate(universe)
    prior = _e002_record(
        source_id="prior",
        published="2026-09-10T03:00:00Z",
        raw_char="c",
        text_char="d",
    )
    current = _e002_record(source_id="current")
    first = _seal(current, [prior], universe, gate)
    second = _seal(current, [prior], universe, gate)
    assert first == second
    prospective.validate_signal_record(first)


def test_forbidden_outcome_field_is_rejected_before_signal_generation() -> None:
    universe = _universe()
    current = _e002_record(source_id="current")
    current["gross_excess_pp"] = 99.0
    with pytest.raises(prospective.H022ProspectiveError, match="forbidden price/outcome key"):
        _seal(current, [], universe, _gate(universe))


def test_append_only_ledger_is_idempotent_but_rejects_changed_bytes() -> None:
    universe = _universe()
    signal = _seal(
        _e002_record(source_id="current"),
        [],
        universe,
        _gate(universe),
    )
    ledger = prospective.new_signal_ledger()
    ledger = prospective.append_signal_record(ledger, signal)
    assert prospective.append_signal_record(ledger, signal) == ledger

    changed = deepcopy(signal)
    changed["signal_frozen_at_utc"] = "2026-09-15T05:00:00Z"
    changed["signal_record_sha256"] = prospective._signal_record_hash(changed)
    prospective.validate_signal_record(changed)
    with pytest.raises(prospective.H022ProspectiveError, match="different immutable bytes"):
        prospective.append_signal_record(ledger, changed)
