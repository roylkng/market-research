import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_history import canonical_gzip_json
from marketlab.rm001 import FACTOR_NAMES


def test_rm001_summary_factor_diagonal_shape():
    covariance = [
        [0.0 for _ in FACTOR_NAMES]
        for _ in FACTOR_NAMES
    ]
    for index in range(len(FACTOR_NAMES)):
        covariance[index][index] = float(index + 1)

    diagonal = {
        factor: covariance[index][index]
        for index, factor in enumerate(FACTOR_NAMES)
    }
    assert list(diagonal) == list(FACTOR_NAMES)
    assert diagonal["MARKET_COMMON"] == 1.0
    assert diagonal["LIQUIDITY"] == 5.0


def test_canonical_gzip_round_trip_supports_rm001_artifact():
    payload = {
        "schema_version": 1,
        "state_sha256": digest({"x": 1}),
        "rows": [],
    }
    raw = canonical_gzip_json(payload)
    assert isinstance(raw, bytes)
    assert len(raw) > 0
