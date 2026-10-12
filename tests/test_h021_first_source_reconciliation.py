from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from marketlab.h021_entry_observation import (
    _canonical_hash,
    build_entry_observation,
    validate_entry_observation,
)
from marketlab.h021_first_source_reconciliation import (
    NSE_INDEX_CSV_SHA,
    ORIGINAL_STOCK_SHA,
    RECOVERY_PATH,
    load_pinned_reconciliation_sources,
    reconcile_source_packet,
    validate_reconciliation,
)
from marketlab.h021_index_recovery import ORIGINAL_STOCK_PATH
from marketlab.marketdata import index_snapshot_url, udiff_url
from scripts.acquire_h021_first_entry import load_and_verify_sources

CAPTURED = "2026-10-12T16:10:00Z"
RECORDED = "2026-10-12T16:15:00Z"


def _synthetic_later_full_packet() -> dict:
    """Simulate later original CSV availability; never commit invented prices."""
    intent, universe = load_and_verify_sources()
    stock = ORIGINAL_STOCK_PATH.read_bytes()
    index = (
        Path("research/prospective/h021/index-recovery/raw/sha256")
        / f"{NSE_INDEX_CSV_SHA}.csv"
    ).read_bytes()
    assert hashlib.sha256(stock).hexdigest() == ORIGINAL_STOCK_SHA
    assert hashlib.sha256(index).hexdigest() == NSE_INDEX_CSV_SHA
    return build_entry_observation(
        intent, universe,
        udiff_source={
            "url": udiff_url(date(2026, 10, 12)),
            "captured_at_utc": CAPTURED,
            "status": "OK",
            "http_status": 200,
            "raw": stock,
            "error": None,
        },
        index_source={
            "url": index_snapshot_url(date(2026, 10, 12)),
            "captured_at_utc": CAPTURED,
            "status": "OK",
            "http_status": 200,
            "raw": index,
            "error": None,
        },
        recorded_at_utc=RECORDED,
    )


def _source_join(later: dict | None = None) -> dict:
    original, supplement = load_pinned_reconciliation_sources(Path("."))
    return reconcile_source_packet(
        first_attempt=original,
        source_supplement=supplement,
        later_complete=_synthetic_later_full_packet() if later is None else later,
    )


def test_existing_double_nse_official_index_is_pinned_without_rewriting_first_404() -> None:
    original, supplement = load_pinned_reconciliation_sources(Path("."))
    assert original["source_receipts"]["index"]["status"] == "NOT_PUBLISHED"
    assert original["source_receipts"]["index"]["http_status"] == 404
    assert original["benchmark_observation"]["open_index_value"] is None
    assert supplement["source_state"] == "OFFICIAL_DUAL_HOSTS_AGREE"
    assert supplement["verified_primary_or_agreed_dual_index_source"] is True
    assert supplement["source_receipts"]["primary"]["raw_sha256"] == NSE_INDEX_CSV_SHA
    assert supplement["source_receipts"]["nse_archive_mirror"]["raw_sha256"] == NSE_INDEX_CSV_SHA
    assert supplement["benchmark"]["corroborated_recovery_open"] == 21936.25
    assert supplement["benchmark"]["corroborated_recovery_close"] == 21822.75
    assert json.loads(RECOVERY_PATH.read_text()) == supplement


def test_complete_recovered_source_can_be_crosschecked_without_opening_returns() -> None:
    full = _synthetic_later_full_packet()
    validate_entry_observation(full)
    assert full["source_observation_status"] == "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED"
    assert full["observed_official_stock_open_count"] == 10
    report = _source_join(full)
    validate_reconciliation(report)
    assert report["all_ten_original_open_high_low_close_observations_identical"] is True
    assert report["stock_and_benchmark_source_complete"] is True
    assert report["original_index_404_receipt_retained"] is True
    assert report["nifty500_open_from_agreed_official_sources"] == 21936.25
    assert report["nifty500_close_from_agreed_official_sources"] == 21822.75
    assert report["first_executable_fill_verified"] is False
    assert report["dividend_cash_entitlement_verified"] is False
    assert report["nifty500_tri_total_return_basis_verified"] is False
    assert report["benchmark_excess_calculated"] is False
    assert report["expected_returns_calculated"] is False
    assert report["live_capital_allowed"] is False


def test_cannot_silently_revise_one_original_12_oct_vedl_open() -> None:
    full = _synthetic_later_full_packet()
    full["stock_observations"][0]["open_price_inr"] = 999.0
    full["packet_sha256"] = _canonical_hash(
        {key: value for key, value in full.items() if key != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="later source cannot revise"):
        _source_join(full)


def test_cannot_replace_corresponding_nifty500_close_or_index_raw_sha() -> None:
    full = _synthetic_later_full_packet()
    full["benchmark_observation"]["close_index_value"] = 9999.0
    full["packet_sha256"] = _canonical_hash(
        {key: value for key, value in full.items() if key != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="benchmark differs"):
        _source_join(full)

    full = _synthetic_later_full_packet()
    full["source_receipts"]["index"]["raw_sha256"] = "a" * 64
    full["packet_sha256"] = _canonical_hash(
        {key: value for key, value in full.items() if key != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="benchmark differs"):
        _source_join(full)


def test_no_backdated_nifty500_index_capture_time() -> None:
    full = _synthetic_later_full_packet()
    full["source_receipts"]["index"]["captured_at_utc"] = "2026-10-12T11:00:00Z"
    full["packet_sha256"] = _canonical_hash(
        {key: value for key, value in full.items() if key != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="cannot backdate"):
        _source_join(full)


def test_tampered_p018_original_index_supplement_fails_before_replay() -> None:
    original, supplement = load_pinned_reconciliation_sources(Path("."))
    changed = deepcopy(supplement)
    changed["benchmark"]["corroborated_recovery_open"] += 10
    with pytest.raises(ValueError, match="source supplement hash mismatch"):
        reconcile_source_packet(
            first_attempt=original, source_supplement=changed,
            later_complete=_synthetic_later_full_packet()
        )


def test_source_only_cli_reproducible_and_immutable(tmp_path: Path) -> None:
    simulated_full = tmp_path / "first-full.json"
    simulated_full.write_text(
        json.dumps(_synthetic_later_full_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    target = tmp_path / "reconciliation.json"
    command = [
        sys.executable,
        "scripts/reconcile_h021_first_full_source.py",
        "--full-path", str(simulated_full), "--out", str(target),
    ]
    summary = subprocess.run(
        command, capture_output=True, text=True, check=True
    )
    brief = json.loads(summary.stdout)
    assert brief["stock_and_benchmark_source_complete"] is True
    assert brief["source_original_404_preserved"] is True
    assert brief["returns_calculated"] is False
    assert brief["live_capital_allowed"] is False
    assert json.loads(target.read_text(encoding="utf-8")) == _source_join()
    subprocess.run(
        command + ["--verify-existing"],
        check=True, capture_output=True, text=True
    )
    target.write_text(target.read_text(encoding="utf-8") + "fake")
    failed = subprocess.run(
        command + ["--verify-existing"],
        check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "reconciliation has drifted" in failed.stderr
