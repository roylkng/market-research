from datetime import UTC, datetime

from marketlab.h003_content import FrozenTranscriptSource, TranscriptContentStore


def test_content_identity_ignores_fetch_time_for_same_failure(tmp_path):
    source = FrozenTranscriptSource(
        source_id="source-1",
        symbol="TEST",
        seq_id="1",
        exchange_published_at_utc="2026-07-01T10:00:00Z",
        attachment_url="https://nsearchives.nseindia.com/corporate/test.pdf",
        discovery_row_sha256="a" * 64,
    )
    store = TranscriptContentStore(tmp_path)
    first = store.record_failure(
        source,
        fetched_at=datetime(2026, 9, 6, 10, tzinfo=UTC),
        status="FETCH_FAILED",
        error="same error",
    )
    second = store.record_failure(
        source,
        fetched_at=datetime(2026, 9, 6, 12, tzinfo=UTC),
        status="FETCH_FAILED",
        error="same error",
    )
    assert first.fetched_at_utc != second.fetched_at_utc
    assert first.content_id == second.content_id
