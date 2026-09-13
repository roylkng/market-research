from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from marketlab import h022_expanded_sources as expanded
from marketlab import h022_historical_universe as historical
from marketlab.h003_sources import TranscriptSource


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _reconstruction() -> dict:
    pre = [f"S{index:03d}" for index in range(200)]
    post = pre[1:] + ["NEW"]
    union = sorted(set(pre) | set(post))
    document = {
        "schema_version": 1,
        "rule_id": "H022-UH001",
        "hypothesis_id": "H022",
        "evidence_class": "HISTORICAL_MEMBERSHIP_RECONSTRUCTION",
        "anchor_as_of": "2026-08-31",
        "anchor_source_url": "https://example.test/nifty200.csv",
        "anchor_raw_sha256": "a" * 64,
        "anchor_member_count": 200,
        "pre_march_member_count": 200,
        "expanded_union_member_count": len(union),
        "expanded_union_members": [
            {
                "symbol": symbol,
                "company_name": f"Company {symbol}",
                "industry": "Industry",
                "series": "EQ",
                "isin": f"ISIN-{symbol}",
                "identity_source": "TEST",
            }
            for symbol in union
        ],
        "membership_intervals": [
            {
                "interval_id": "old",
                "start": "2025-10-01",
                "end": "2026-03-29",
                "member_count": 200,
                "symbols": pre,
            },
            {
                "interval_id": "new",
                "start": "2026-03-30",
                "end": "2026-09-06",
                "member_count": 200,
                "symbols": post,
            },
        ],
        "current_u001_member_count": 100,
        "current_u001_in_expanded_union_count": 100,
        "expanded_union_additional_vs_current_u001_count": len(union) - 100,
        "expanded_union_additional_vs_current_u001_symbols": union[100:],
        "temporary_demerger_constituents": {"events": []},
        "ad_hoc_base_membership_audit_status": "REQUIRED_BEFORE_EXPANDED_OUTCOME_EVALUATION",
        "historical_u001_reconstructed": False,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    document["reconstruction_sha256"] = _canonical_hash(document)
    historical.validate_reconstruction(document)
    return document


def _audit() -> dict:
    return {
        "audit_status": "COMPLETE_NO_ADDITIONAL_PERMANENT_BASE_CHANGES",
        "additional_permanent_base_change_count": 0,
        "expanded_nifty200_union_ready_for_transcript_replay": True,
        "outcome_data_attached": False,
    }


def _source(symbol: str, published: str) -> TranscriptSource:
    return TranscriptSource(
        schema_version=1,
        source_id=f"source-{symbol}-{published}",
        symbol=symbol,
        seq_id="1",
        exchange_published_at_utc=published,
        attachment_url="https://nsearchives.nseindia.com/corporate/test.pdf",
        announcement_description="Analysts/Institutional Investor Meet/Con. Call Updates",
        attachment_text="Transcript",
        discovery_row_sha256="b" * 64,
    )


def test_membership_status_uses_ist_event_date() -> None:
    reconstruction = _reconstruction()
    assert expanded.membership_status_for_source(
        symbol="S000",
        exchange_published_at_utc="2025-09-30T18:29:59+00:00",
        reconstruction=reconstruction,
    ) == "PRE_CHALLENGE_CONTEXT"
    assert expanded.membership_status_for_source(
        symbol="S000",
        exchange_published_at_utc="2025-10-01T03:00:00+00:00",
        reconstruction=reconstruction,
    ) == "SIGNAL_ELIGIBLE"
    assert expanded.membership_status_for_source(
        symbol="S000",
        exchange_published_at_utc="2026-04-01T03:00:00+00:00",
        reconstruction=reconstruction,
    ) == "CONTEXT_ONLY_NONMEMBER"
    assert expanded.membership_status_for_source(
        symbol="NEW",
        exchange_published_at_utc="2026-04-01T03:00:00+00:00",
        reconstruction=reconstruction,
    ) == "SIGNAL_ELIGIBLE"


def test_coverage_record_preserves_context_and_signal_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    reconstruction = _reconstruction()
    selected = (
        _source("S001", "2025-09-01T03:00:00+00:00"),
        _source("S001", "2025-11-01T03:00:00+00:00"),
    )
    monkeypatch.setattr(expanded, "select_transcript_sources", lambda *args, **kwargs: selected)
    record = expanded.build_coverage_record(
        [],
        b"[]",
        symbol="S001",
        captured_at=datetime(2026, 9, 13, tzinfo=UTC),
        reconstruction=reconstruction,
    )
    assert record.coverage_status == "COMPLETE"
    assert record.source_count == 2
    assert record.signal_eligible_source_count == 1
    assert record.context_only_source_count == 1
    assert [item.membership_status for item in record.sources] == [
        "PRE_CHALLENGE_CONTEXT",
        "SIGNAL_ELIGIBLE",
    ]


def test_zero_source_company_is_retained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(expanded, "select_transcript_sources", lambda *args, **kwargs: ())
    record = expanded.build_coverage_record(
        [],
        b"[]",
        symbol="S001",
        captured_at=datetime(2026, 9, 13, tzinfo=UTC),
        reconstruction=_reconstruction(),
    )
    assert record.coverage_status == "COMPLETE_ZERO_SOURCE"
    assert record.source_count == 0
    assert record.sources == ()


def test_incomplete_record_blocks_bundle_freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    reconstruction = _reconstruction()
    monkeypatch.setattr(expanded, "EXPECTED_MEMBER_COUNT", 201)
    monkeypatch.setattr(expanded, "RECONSTRUCTION_SHA256", reconstruction["reconstruction_sha256"])
    records = [
        expanded.incomplete_coverage_record(
            symbol=row["symbol"],
            captured_at=datetime(2026, 9, 13, tzinfo=UTC),
            reason="source fetch failed",
        )
        for row in reconstruction["expanded_union_members"]
    ]
    bundle = expanded.build_coverage_bundle(
        records,
        reconstruction=reconstruction,
        audit=_audit(),
        generated_at=datetime(2026, 9, 13, tzinfo=UTC),
        source_rule_sha256="c" * 64,
    )
    assert bundle["member_count"] == 201
    assert bundle["incomplete_count"] == 201
    assert bundle["freeze_ready"] is False


def test_bundle_hash_detects_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    reconstruction = _reconstruction()
    monkeypatch.setattr(expanded, "EXPECTED_MEMBER_COUNT", 201)
    monkeypatch.setattr(expanded, "RECONSTRUCTION_SHA256", reconstruction["reconstruction_sha256"])
    records = [
        expanded.incomplete_coverage_record(
            symbol=row["symbol"],
            captured_at=datetime(2026, 9, 13, tzinfo=UTC),
            reason="source fetch failed",
        )
        for row in reconstruction["expanded_union_members"]
    ]
    bundle = expanded.build_coverage_bundle(
        records,
        reconstruction=reconstruction,
        audit=_audit(),
        generated_at=datetime(2026, 9, 13, tzinfo=UTC),
        source_rule_sha256="c" * 64,
    )
    bundle["transcript_source_count"] = 99
    with pytest.raises(expanded.ExpandedSourceError, match="hash mismatch"):
        expanded.validate_coverage_bundle(
            bundle,
            reconstruction=reconstruction,
            audit=_audit(),
        )
