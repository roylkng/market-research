from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from marketlab.h021 import validate_snapshot
from marketlab.h021_capture import (
    CANONICAL_BATCH_SPEC_PATH,
    CANONICAL_PROTOCOL_PATH,
    CANONICAL_SOURCE_VERSION,
    CANONICAL_UNIVERSE_BLOB_SHA,
    CANONICAL_UNIVERSE_PATH,
    verify_capture_bundle,
)

LEGACY_BASENAME = "2026-09-11-full-u001-v1.json.gz"
LEGACY_GZIP_SHA256 = "94bdbbc4fa4e8fa70f1535797f165dfbab52d0f937cade91425824422f9d2c33"
LEGACY_JSON_SHA256 = "bd87a3bb942a60e7f625293577487b8850b67530b3126bea5bb7d9d9e999d434"
LEGACY_CAPTURE_ID = "2026-09-11-full-u001-v1"
LEGACY_CAPTURE_DATE = "2026-09-11"
LEGACY_CAPTURED_AT = "2026-09-11T13:15:12Z"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _manifest_path(path: Path) -> Path:
    if not path.name.endswith(".json.gz"):
        raise ValueError("H021 capture filename must end with .json.gz")
    return path.with_name(path.name[:-8] + ".manifest.json")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"H021 manifest must be an object: {path}")
    return payload


def _strict_legacy(
    raw_gzip: bytes,
    manifest: dict[str, Any],
    *,
    path: Path,
    universe: dict[str, Any],
    batch_spec: dict[str, Any],
) -> dict[str, Any]:
    if path.name != LEGACY_BASENAME or manifest.get("schema_version") != 1:
        raise ValueError("H021 unrecognized legacy capture bundle")
    expected = {
        "hypothesis_id": "H021",
        "logical_capture_id": LEGACY_CAPTURE_ID,
        "capture_date_ist": LEGACY_CAPTURE_DATE,
        "captured_at_utc": LEGACY_CAPTURED_AT,
        "source_version": CANONICAL_SOURCE_VERSION,
        "universe_path": CANONICAL_UNIVERSE_PATH,
        "universe_git_blob_sha": CANONICAL_UNIVERSE_BLOB_SHA,
        "protocol_path": CANONICAL_PROTOCOL_PATH,
        "batch_spec_path": CANONICAL_BATCH_SPEC_PATH,
        "payload_gzip_sha256": LEGACY_GZIP_SHA256,
        "payload_uncompressed_sha256": LEGACY_JSON_SHA256,
        "payload_encoding": "gzip",
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"H021 legacy manifest {key} mismatch")
    if manifest.get("payload_path") != (
        f"research/prospective/h021/captures/{LEGACY_BASENAME}"
    ):
        raise ValueError("H021 legacy manifest payload path mismatch")
    if len(raw_gzip) != manifest.get("payload_gzip_bytes"):
        raise ValueError("H021 legacy compressed byte length mismatch")
    if _sha(raw_gzip) != LEGACY_GZIP_SHA256:
        raise ValueError("H021 legacy gzip SHA mismatch")

    try:
        raw_json = gzip.decompress(raw_gzip)
    except (OSError, EOFError) as exc:
        raise ValueError("H021 legacy gzip is invalid") from exc
    if len(raw_json) != manifest.get("payload_uncompressed_bytes"):
        raise ValueError("H021 legacy JSON byte length mismatch")
    if _sha(raw_json) != LEGACY_JSON_SHA256:
        raise ValueError("H021 legacy JSON SHA mismatch")

    try:
        snapshot = json.loads(
            raw_json.decode("utf-8"),
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("H021 legacy snapshot is invalid JSON") from exc
    if not isinstance(snapshot, dict):
        raise TypeError("H021 legacy snapshot must be an object")

    for key in (
        "hypothesis_id",
        "logical_capture_id",
        "capture_date_ist",
        "captured_at_utc",
        "source_version",
        "universe_path",
        "universe_git_blob_sha",
        "protocol_path",
        "batch_spec_path",
        "outcomes_opened",
        "live_capital_allowed",
    ):
        if key in snapshot and snapshot[key] != expected[key]:
            raise ValueError(f"H021 legacy snapshot {key} mismatch")
        if (
            key in ("hypothesis_id", "capture_date_ist", "captured_at_utc")
            and snapshot.get(key) != expected[key]
        ):
            raise ValueError(f"H021 legacy required snapshot {key} mismatch")

    # The v1 writer may omit selected manifest-owned source identity fields.
    # Restore only those already authenticated by exact, pinned bytes.
    for key in ("source_version", "universe_path", "universe_git_blob_sha"):
        snapshot.setdefault(key, manifest[key])
    if snapshot.get("logical_capture_id") not in (None, LEGACY_CAPTURE_ID):
        raise ValueError("H021 legacy logical capture ID mismatch")

    errors = validate_snapshot(snapshot)
    if errors:
        raise ValueError({"legacy_snapshot_validation_errors": errors})

    members = universe.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise ValueError("H021 legacy requires the frozen 100-member universe")
    if batch_spec.get("universe_git_blob_sha") != CANONICAL_UNIVERSE_BLOB_SHA:
        raise ValueError("H021 legacy frozen batch universe SHA mismatch")
    if batch_spec.get("universe_path") != CANONICAL_UNIVERSE_PATH:
        raise ValueError("H021 legacy frozen batch universe path mismatch")

    by_symbol = {
        row["symbol"]: row
        for row in members
        if isinstance(row, dict) and isinstance(row.get("symbol"), str)
    }
    observations = snapshot["observations"]
    if len(by_symbol) != 100 or len(observations) != 100:
        raise ValueError("H021 legacy must contain exactly 100 unique members")
    observed = {row["symbol"]: row for row in observations}
    if set(observed) != set(by_symbol):
        raise ValueError("H021 legacy frozen symbol set mismatch")

    batches = batch_spec.get("batches")
    if not isinstance(batches, list):
        raise TypeError("H021 legacy frozen batch definitions missing")
    for symbol, observation in observed.items():
        member = by_symbol[symbol]
        source_isin = observation.get("isin")
        if source_isin is not None and source_isin != member.get("isin"):
            raise ValueError(f"H021 legacy {symbol} ISIN mismatch")
        rank = member.get("rank")
        if observation.get("universe_rank") not in (None, rank):
            raise ValueError(f"H021 legacy {symbol} universe rank mismatch")
        valid_batches = [
            b["batch_id"] for b in batches
            if isinstance(b, dict)
            and isinstance(rank, int)
            and b.get("rank_min", 0) <= rank <= b.get("rank_max", 0)
        ]
        if len(valid_batches) != 1:
            raise ValueError(f"H021 legacy {symbol} batch definition is ambiguous")
        if observation.get("batch_id") not in (None, valid_batches[0]):
            raise ValueError(f"H021 legacy {symbol} batch mismatch")

    captured = datetime.fromisoformat(snapshot["captured_at_utc"])
    if captured.tzinfo is None or captured.date() != date.fromisoformat(LEGACY_CAPTURE_DATE):
        raise ValueError("H021 legacy capture timestamp/date mismatch")
    return snapshot


def load_h021_capture_compatible(
    path: Path,
    *,
    universe: dict[str, Any],
    batch_spec: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Strictly verify v2 bundles or one pinned immutable Sep-11 v1 bundle."""
    manifest = _load_json(_manifest_path(path))
    payload_gzip = path.read_bytes()
    if manifest.get("schema_version") == 2:
        return verify_capture_bundle(payload_gzip, manifest, universe, batch_spec), manifest
    if manifest.get("schema_version") == 1:
        return (
            _strict_legacy(
                payload_gzip,
                manifest,
                path=path,
                universe=universe,
                batch_spec=batch_spec,
            ),
            manifest,
        )
    raise ValueError("H021 capture manifest schema is unsupported")
