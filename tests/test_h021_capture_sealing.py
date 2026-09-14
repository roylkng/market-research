from __future__ import annotations

import copy
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.h021_capture import (
    CANONICAL_BATCH_SPEC_PATH,
    CANONICAL_COMPARISON_CONTRACT_PATH,
    CANONICAL_PROTOCOL_PATH,
    CANONICAL_SOURCE_VERSION,
    CANONICAL_UNIVERSE_BLOB_SHA,
    CANONICAL_UNIVERSE_PATH,
    build_capture_artifacts,
    validate_full_capture,
    verify_artifact_bytes,
    verify_capture_bundle,
)


def _universe(count: int = 4) -> dict:
    return {
        "members": [
            {
                "symbol": f"S{rank:02d}",
                "rank": rank,
                "isin": f"INE{rank:09d}",
            }
            for rank in range(1, count + 1)
        ]
    }


def _batches(count: int = 4) -> dict:
    midpoint = count // 2
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "universe_path": CANONICAL_UNIVERSE_PATH,
        "universe_git_blob_sha": CANONICAL_UNIVERSE_BLOB_SHA,
        "expected_member_count": count,
        "batches": [
            {"batch_id": "B01", "rank_min": 1, "rank_max": midpoint},
            {"batch_id": "B02", "rank_min": midpoint + 1, "rank_max": count},
        ],
    }


def _snapshot(count: int = 4) -> dict:
    universe = _universe(count)
    rows = []
    for member in universe["members"]:
        rank = member["rank"]
        rows.append(
            {
                "symbol": member["symbol"],
                "isin": member["isin"],
                "universe_rank": rank,
                "batch_id": "B01" if rank <= count // 2 else "B02",
                "data_state": "OBSERVED",
                "retrieval_notes": "explicit annual consensus observation",
                "fiscal_period": "FY27",
                "consensus_eps": 10.0 + rank,
                "revenue_growth_forecast_pct": 12.0,
                "profit_growth_estimate_pct": 15.0,
                "analyst_count": 6,
                "target_price_inr": 100.0 + rank,
                "source_observed_market_date": "2026-09-18",
                "source_url": f"https://stockanalysis.com/stocks/s{rank:02d}/forecast/",
                "source_status": "PUBLIC_STOCKANALYSIS_SP_GLOBAL",
            }
        )
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "logical_capture_id": "2026-09-18-full-u001-v1",
        "capture_date_ist": "2026-09-18",
        "captured_at_utc": "2026-09-18T13:00:00Z",
        "source_version": CANONICAL_SOURCE_VERSION,
        "universe_path": CANONICAL_UNIVERSE_PATH,
        "universe_git_blob_sha": CANONICAL_UNIVERSE_BLOB_SHA,
        "protocol_path": CANONICAL_PROTOCOL_PATH,
        "comparison_contract_path": CANONICAL_COMPARISON_CONTRACT_PATH,
        "batch_spec_path": CANONICAL_BATCH_SPEC_PATH,
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "observations": rows,
    }


def test_build_capture_artifacts_is_deterministic_and_complete() -> None:
    snapshot = _snapshot()
    universe = _universe()
    batches = _batches()

    first = build_capture_artifacts(snapshot, universe, batches)
    second = build_capture_artifacts(snapshot, universe, batches)

    assert first.payload_json == second.payload_json
    assert first.payload_gzip == second.payload_gzip
    assert first.manifest == second.manifest
    assert first.manifest["coverage_summary"]["total"] == 4
    assert first.manifest["coverage_summary"]["OBSERVED"] == 4
    assert first.manifest["coverage_summary"]["explicit_consensus_eps"] == 4
    assert [row["processed"] for row in first.manifest["batch_summary"]] == [2, 2]
    assert gzip.decompress(first.payload_gzip) == first.payload_json


def test_full_capture_rejects_symbol_substitution() -> None:
    snapshot = _snapshot()
    snapshot["observations"][-1]["symbol"] = "SUBSTITUTE"

    errors = validate_full_capture(snapshot, _universe(), _batches())

    assert any("symbol set differs" in error for error in errors)


def test_full_capture_rejects_identity_and_batch_drift() -> None:
    snapshot = _snapshot()
    snapshot["observations"][0]["isin"] = "WRONG"
    snapshot["observations"][1]["universe_rank"] = 99
    snapshot["observations"][2]["batch_id"] = "B01"

    errors = validate_full_capture(snapshot, _universe(), _batches())

    assert any("ISIN mismatch" in error for error in errors)
    assert any("universe_rank mismatch" in error for error in errors)
    assert any("batch_id mismatch" in error for error in errors)


def test_full_capture_rejects_stale_values_for_source_blocked_row() -> None:
    snapshot = _snapshot()
    row = snapshot["observations"][0]
    row["data_state"] = "SOURCE_BLOCKED"
    row["retrieval_notes"] = "provider denied public retrieval"

    errors = validate_full_capture(snapshot, _universe(), _batches())

    assert any("must not carry forward forecast values" in error for error in errors)


def test_full_capture_accepts_source_blocked_row_with_null_current_values() -> None:
    snapshot = _snapshot()
    row = snapshot["observations"][0]
    row["data_state"] = "SOURCE_BLOCKED"
    row["retrieval_notes"] = "provider denied public retrieval"
    for field in (
        "consensus_eps",
        "revenue_growth_forecast_pct",
        "profit_growth_estimate_pct",
        "analyst_count",
        "target_price_inr",
    ):
        row[field] = None

    assert validate_full_capture(snapshot, _universe(), _batches()) == []


def test_full_capture_rejects_source_version_and_india_date_drift() -> None:
    snapshot = _snapshot()
    snapshot["source_version"] = "new-provider-after-outcomes"
    snapshot["captured_at_utc"] = "2026-09-17T12:00:00Z"

    errors = validate_full_capture(snapshot, _universe(), _batches())

    assert any("source_version" in error for error in errors)
    assert any("India date" in error for error in errors)


def test_full_capture_rejects_unsafe_or_mismatched_capture_id() -> None:
    snapshot = _snapshot()
    snapshot["logical_capture_id"] = "../../escape"
    errors = validate_full_capture(snapshot, _universe(), _batches())
    assert any("YYYY-MM-DD-full-u001-vN" in error for error in errors)

    snapshot = _snapshot()
    snapshot["logical_capture_id"] = "2026-09-19-full-u001-v1"
    errors = validate_full_capture(snapshot, _universe(), _batches())
    assert any("date must equal capture_date_ist" in error for error in errors)


def test_correction_version_requires_reason() -> None:
    snapshot = _snapshot()
    snapshot["logical_capture_id"] = "2026-09-18-full-u001-v2"
    errors = validate_full_capture(snapshot, _universe(), _batches())
    assert any("correction_reason" in error for error in errors)

    snapshot["correction_reason"] = "Corrected one current-capture transcription error."
    assert validate_full_capture(snapshot, _universe(), _batches()) == []


def test_verify_artifact_bytes_detects_tampering() -> None:
    artifacts = build_capture_artifacts(_snapshot(), _universe(), _batches())

    restored = verify_artifact_bytes(artifacts.payload_gzip, artifacts.manifest)
    assert restored == _snapshot()

    tampered = bytearray(artifacts.payload_gzip)
    tampered[-1] ^= 1
    with pytest.raises(ValueError):
        verify_artifact_bytes(bytes(tampered), artifacts.manifest)


def test_verify_capture_bundle_rejects_false_manifest_summary() -> None:
    artifacts = build_capture_artifacts(_snapshot(), _universe(), _batches())
    manifest = copy.deepcopy(artifacts.manifest)
    manifest["coverage_summary"]["OBSERVED"] = 3

    with pytest.raises(ValueError, match="coverage_summary"):
        verify_capture_bundle(artifacts.payload_gzip, manifest, _universe(), _batches())


def test_verify_artifact_bytes_rejects_payload_manifest_identity_drift() -> None:
    artifacts = build_capture_artifacts(_snapshot(), _universe(), _batches())
    manifest = copy.deepcopy(artifacts.manifest)
    manifest["capture_date_ist"] = "2026-09-19"

    with pytest.raises(ValueError, match="capture_date_ist"):
        verify_artifact_bytes(artifacts.payload_gzip, manifest)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_sealing_cli_is_idempotent_and_rejects_conflicting_reuse(tmp_path: Path) -> None:
    draft = tmp_path / "draft.json"
    universe = tmp_path / "universe.json"
    batches = tmp_path / "batches.json"
    out_dir = tmp_path / "sealed"
    _write_json(draft, _snapshot())
    _write_json(universe, _universe())
    _write_json(batches, _batches())

    script = Path(__file__).resolve().parents[1] / "scripts" / "seal_h021_capture.py"
    command = [
        sys.executable,
        str(script),
        "--draft",
        str(draft),
        "--universe",
        str(universe),
        "--batches",
        str(batches),
        "--out-dir",
        str(out_dir),
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    second = subprocess.run(command, check=True, capture_output=True, text=True)
    assert "'payload': 'CREATED'" in first.stdout
    assert "'payload': 'UNCHANGED'" in second.stdout

    changed = copy.deepcopy(_snapshot())
    changed["observations"][0]["consensus_eps"] = 999.0
    _write_json(draft, changed)
    conflict = subprocess.run(command, check=False, capture_output=True, text=True)
    assert conflict.returncode != 0
    assert "immutable H021 capture path already exists" in conflict.stderr
