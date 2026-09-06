from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from marketlab.h003_candidates import FrozenTranscriptSource, H003CandidateError


def _module():
    path = Path("scripts/build_h003_candidates.py")
    spec = importlib.util.spec_from_file_location("build_h003_candidates", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sources(count: int = 23) -> tuple[FrozenTranscriptSource, ...]:
    return tuple(
        FrozenTranscriptSource(
            source_id=f"source-{index:03d}",
            symbol=f"S{index:03d}",
            seq_id=str(index),
            exchange_published_at_utc="2026-08-01T10:00:00Z",
            attachment_url=f"https://nsearchives.nseindia.com/{index}.pdf",
            discovery_row_sha256="a" * 64,
        )
        for index in range(count)
    )


def test_shards_are_disjoint_and_exactly_cover_frozen_order():
    module = _module()
    sources = _sources(23)
    shards = [
        module._select_sources(
            sources,
            sample_count=None,
            shard_count=8,
            shard_index=index,
        )
        for index in range(8)
    ]
    flattened = [source for shard in shards for source in shard]
    assert len(flattened) == len(sources)
    assert len({source.source_id for source in flattened}) == len(sources)
    for source_index, source in enumerate(sources):
        assert source in shards[source_index % 8]


def test_sharding_is_deterministic():
    module = _module()
    sources = _sources()
    first = module._select_sources(
        sources, sample_count=None, shard_count=5, shard_index=3
    )
    second = module._select_sources(
        sources, sample_count=None, shard_count=5, shard_index=3
    )
    assert first == second


def test_sample_and_shard_are_mutually_exclusive():
    module = _module()
    with pytest.raises(H003CandidateError, match="mutually exclusive"):
        module._select_sources(
            _sources(), sample_count=3, shard_count=2, shard_index=0
        )


@pytest.mark.parametrize(
    ("count", "index"),
    [(None, 0), (2, None), (0, 0), (2, -1), (2, 2)],
)
def test_invalid_shard_spec_fails_closed(count, index):
    module = _module()
    with pytest.raises(H003CandidateError):
        module._select_sources(
            _sources(), sample_count=None, shard_count=count, shard_index=index
        )
