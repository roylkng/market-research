from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.h021_capture import (
    CANONICAL_UNIVERSE_BLOB_SHA,
    CANONICAL_UNIVERSE_PATH,
    validate_full_capture,
)
from marketlab.h021_capture_draft import (
    DRAFT_STATE,
    PENDING_STATE,
    build_capture_draft,
)


def _universe() -> dict:
    return {
        "members": [
            {
                "symbol": "AAA",
                "company_name": "Alpha Ltd.",
                "isin": "INE000000001",
                "series": "EQ",
                "constituent_industry": "Industrials",
                "rank": 1,
            },
            {
                "symbol": "BBB",
                "company_name": "Beta Ltd.",
                "isin": "INE000000002",
                "series": "EQ",
                "constituent_industry": "Technology",
                "rank": 2,
            },
        ]
    }


def _batches() -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "universe_path": CANONICAL_UNIVERSE_PATH,
        "universe_git_blob_sha": CANONICAL_UNIVERSE_BLOB_SHA,
        "expected_member_count": 2,
        "batches": [
            {"batch_id": "B01", "rank_min": 1, "rank_max": 1},
            {"batch_id": "B02", "rank_min": 2, "rank_max": 2},
        ],
    }


def test_draft_is_derived_exactly_from_frozen_identity() -> None:
    draft = build_capture_draft("2026-09-18", _universe(), _batches())

    assert draft["logical_capture_id"] == "2026-09-18-full-u001-v1"
    assert draft["draft_state"] == DRAFT_STATE
    assert draft["captured_at_utc"] is None
    assert [row["symbol"] for row in draft["observations"]] == ["AAA", "BBB"]
    assert [row["isin"] for row in draft["observations"]] == [
        "INE000000001",
        "INE000000002",
    ]
    assert [row["universe_rank"] for row in draft["observations"]] == [1, 2]
    assert [row["batch_id"] for row in draft["observations"]] == ["B01", "B02"]
    assert all(row["data_state"] == PENDING_STATE for row in draft["observations"])
    assert all(row["source_status"] == PENDING_STATE for row in draft["observations"])
    assert all(row["period_ending"] is None for row in draft["observations"])
    assert all(row["eps_currency"] is None for row in draft["observations"])


def test_incomplete_draft_is_intentionally_not_sealable() -> None:
    draft = build_capture_draft("2026-09-18", _universe(), _batches())

    errors = validate_full_capture(draft, _universe(), _batches())

    assert any("captured_at_utc" in error for error in errors)
    assert any("invalid data_state" in error for error in errors)
    assert any("invalid fiscal_period" in error for error in errors)
    assert any("source_url" in error for error in errors)
    assert any("retrieval_notes must be a non-empty string" in error for error in errors)


def test_correction_draft_requires_explicit_reason() -> None:
    with pytest.raises(ValueError, match="correction_reason"):
        build_capture_draft("2026-09-18", _universe(), _batches(), version=2)

    corrected = build_capture_draft(
        "2026-09-18",
        _universe(),
        _batches(),
        version=2,
        correction_reason="Correct an identified transcription error.",
    )
    assert corrected["logical_capture_id"] == "2026-09-18-full-u001-v2"
    assert corrected["correction_reason"] == "Correct an identified transcription error."


def test_v1_rejects_correction_reason() -> None:
    with pytest.raises(ValueError, match="v1 capture draft"):
        build_capture_draft(
            "2026-09-18",
            _universe(),
            _batches(),
            correction_reason="not a correction",
        )


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_initializer_cli_is_idempotent_and_refuses_overwrite(tmp_path: Path) -> None:
    universe = tmp_path / "universe.json"
    batches = tmp_path / "batches.json"
    output = tmp_path / "capture-draft.json"
    _write_json(universe, _universe())
    _write_json(batches, _batches())

    script = Path(__file__).resolve().parents[1] / "scripts" / "init_h021_capture_draft.py"
    command = [
        sys.executable,
        str(script),
        "--capture-date",
        "2026-09-18",
        "--universe",
        str(universe),
        "--batches",
        str(batches),
        "--out",
        str(output),
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    second = subprocess.run(command, check=True, capture_output=True, text=True)
    assert "state=CREATED" in first.stdout
    assert "state=UNCHANGED" in second.stdout

    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["observations"][0]["company_name"] = "Changed"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    conflict = subprocess.run(command, check=False, capture_output=True, text=True)
    assert conflict.returncode != 0
    assert "capture draft already exists with different content" in conflict.stderr
