from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_entry_attempt_replay import (
    materialize_original_entry_attempts,
    replay_original_entry_attempt,
)
from scripts.replay_h021_entry_attempts import (
    FIRST_OBSERVATIONS,
    load_original_frozen_inputs,
)

FIRST_ATTEMPT = "38246531921-1.json"
FIRST_PACKET_SHA = "c314c0f001476f9ff221ca5055fb6b185702f862d4a455c5f0bb0e2f151dacbd"
STOCK_RAW_SHA = "818f673b3cdb96ae8ec4e466c7c4fd3a28d035482173a675dd24f9437a3ecd99"


def _replay(attempt: dict | None = None, source_root: Path = FIRST_OBSERVATIONS) -> dict:
    intent, universe = load_original_frozen_inputs(Path("."))
    if attempt is None:
        attempt = json.loads(
            (source_root / "attempts" / FIRST_ATTEMPT).read_text(encoding="utf-8")
        )
    return replay_original_entry_attempt(
        frozen_intent=intent,
        frozen_universe=universe,
        attempt=attempt,
        source_root=source_root,
    )


def test_real_oct12_first_source_recovers_ten_official_eq_opens_no_index() -> None:
    packet = _replay()
    assert packet["packet_sha256"] == FIRST_PACKET_SHA
    assert packet["session_date_ist"] == "2026-10-12"
    assert packet["source_observation_status"] == "PARTIAL_OR_BLOCKED_SOURCE_OBSERVATION"
    assert packet["observed_official_stock_open_count"] == 10
    assert packet["source_receipts"]["udiff"]["status"] == "OK"
    assert packet["source_receipts"]["udiff"]["raw_sha256"] == STOCK_RAW_SHA
    assert packet["source_receipts"]["udiff"]["raw_byte_count"] == 207055
    assert packet["source_receipts"]["index"]["status"] == "NOT_PUBLISHED"
    assert packet["source_receipts"]["index"]["http_status"] == 404
    assert packet["benchmark_observation"]["open_index_value"] is None
    assert packet["benchmark_observation"]["close_index_value"] is None
    assert [x["symbol"] for x in packet["stock_observations"]] == [
        "VEDL", "ETERNAL", "DMART", "IDEA", "ADANIENSOL",
        "JSWSTEEL", "COALINDIA", "INFY", "GAIL", "POWERGRID",
    ]
    for row in packet["stock_observations"]:
        assert row["status"] == "OFFICIAL_OHLC_OBSERVED_NOT_EXECUTABLE_FILL"
        assert row["open_price_inr"] is not None and row["open_price_inr"] > 0
        assert row["actual_trade_fill_confirmed"] is False
    for f in (
        "entry_trades_executed", "execution_and_liquidity_verified",
        "corporate_action_adjustments_verified", "dividends_and_total_return_basis_verified",
        "return_outcomes_opened", "expected_returns_calculated",
        "portfolio_eligibility_allowed", "live_capital_allowed",
    ):
        assert packet[f] is False


def test_source_hash_and_benchmark_spoof_cannot_pass_as_official() -> None:
    attempt = json.loads(
        (FIRST_OBSERVATIONS / "attempts" / FIRST_ATTEMPT).read_text(encoding="utf-8")
    )
    altered = deepcopy(attempt)
    altered["source_receipts"]["index"]["status"] = "OK"
    with pytest.raises(ValueError, match="missing|hash|count|source"):
        _replay(altered)

    altered = deepcopy(attempt)
    altered["source_receipts"]["index"]["official_source_url"] = (
        "https://example.com/synthetic-nifty500.csv"
    )
    with pytest.raises(ValueError, match="source URL|original|entry|NSE"):
        _replay(altered)

    altered = deepcopy(attempt)
    altered["packet_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="differs"):
        _replay(altered)


def test_original_udiff_file_tamper_is_detected_before_price_parsing(tmp_path: Path) -> None:
    p = FIRST_OBSERVATIONS
    attempts_dir = tmp_path / "attempts"
    attempts_dir.mkdir(parents=True)
    shutil.copyfile(p / "attempts" / FIRST_ATTEMPT, attempts_dir / FIRST_ATTEMPT)
    originals = tmp_path / "raw" / "sha256"
    originals.mkdir(parents=True)
    filename = STOCK_RAW_SHA + ".zip"
    raw = (p / "raw" / "sha256" / filename).read_bytes()
    (originals / filename).write_bytes(raw + b"modified")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        _replay(source_root=tmp_path)


def test_idempotent_replay_refuses_modified_existing_immutable_packet(
    tmp_path: Path,
) -> None:
    intent, universe = load_original_frozen_inputs(Path("."))
    out = tmp_path / "reconstructed"
    kwargs = {
        "frozen_intent": intent, "frozen_universe": universe,
        "source_root": FIRST_OBSERVATIONS, "out_root": out,
    }
    first = materialize_original_entry_attempts(**kwargs)
    assert first["attempt_count_verified"] >= 1
    assert first["new_original_source_attempt_packets"] >= 1
    assert first["partial_source_attempt_count"] >= 1
    assert first["future_holding_returns_opened"] is False
    assert first["live_capital_allowed"] is False
    replayed = json.loads((out / FIRST_ATTEMPT).read_text(encoding="utf-8"))
    assert replayed["packet_sha256"] == FIRST_PACKET_SHA
    again = materialize_original_entry_attempts(**kwargs, verify_existing=True)
    assert again["new_original_source_attempt_packets"] == 0
    assert again["existing_packets_reverified"] == first["attempt_count_verified"]
    path = out / FIRST_ATTEMPT
    path.write_text(
        path.read_text(encoding="utf-8") + '{"fabricated":true}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source attempt replay was modified"):
        materialize_original_entry_attempts(**kwargs)


def test_first_original_source_replay_cli_is_safe_and_source_bound(tmp_path: Path) -> None:
    out = tmp_path / "packets"
    cmd = [
        sys.executable, "scripts/replay_h021_entry_attempts.py",
        "--out-root", str(out),
    ]
    completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
    result = json.loads(completed.stdout)
    assert result["attempt_count_verified"] >= 1
    assert result["partial_source_attempt_count"] >= 1
    assert result["future_holding_returns_opened"] is False
    assert result["portfolio_eligibility_allowed"] is False
    subprocess.run(
        cmd + ["--verify-existing"], check=True, text=True, capture_output=True
    )
