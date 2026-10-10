from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.nse import NSEAcquisitionError
from marketlab.ss002_p001_source_gaps import (
    MAX_AUTOMATED_ATTEMPTS_PER_DAY,
    append_source_failure,
    build_source_failure,
    source_attempts_for_day,
    validate_source_failure,
)
from scripts import run_ss002_p001_daily as runner

DAY = date(2026, 10, 9)
CAPTURED = "2026-10-10T12:10:00Z"


def _attempt(
    *,
    run: str = "github-100001-1",
    error: str = "NSE corporate_announcements failed: Read timed out. (read timeout=25.0)",
    phase: str = "CORPORATE_ANNOUNCEMENTS_FETCH",
) -> dict:
    return build_source_failure(
        source_day=DAY,
        recorded_at_utc=CAPTURED,
        source_phase=phase,
        exception=NSEAcquisitionError(error),
        attempt_identity=run,
    )


def test_timeout_never_means_zero_market_announcements(tmp_path: Path) -> None:
    result = _attempt()
    assert result["source_state"] == "OFFICIAL_SOURCE_UNAVAILABLE_NO_CANONICAL_CAPTURE"
    assert result["source_failure_reason"] == "OFFICIAL_NSE_TIMEOUT_OR_NETWORK_UNAVAILABLE"
    assert result["announcement_count"] is None
    assert result["raw_announcement_bytes_retained"] is False
    assert result["source_day_zero_announcements_proven"] is False
    assert result["return_outcomes_opened"] is False
    assert result["live_capital_allowed"] is False
    receipt = append_source_failure(tmp_path, result)
    assert receipt.exists()
    assert receipt.name == "github-100001-1.json"
    assert len(source_attempts_for_day(tmp_path, DAY)) == 1
    assert not (tmp_path / "2026-10-09-v1.json").exists()
    assert append_source_failure(tmp_path, result) == receipt


def test_strict_attempt_identity_and_digest_prevent_fabricated_success() -> None:
    with pytest.raises(ValueError, match="unsupported characters"):
        _attempt(run="../../bad-attempt")
    obj = _attempt()
    obj["announcement_count"] = 0
    with pytest.raises(AlphaContractError, match="fabricated announcement"):
        validate_source_failure(obj, expected_day=DAY)
    obj = _attempt()
    obj["exception_summary"] = "source succeeded"
    with pytest.raises(AlphaContractError, match="hash mismatch"):
        validate_source_failure(obj, expected_day=DAY)
    obj = _attempt()
    obj["live_capital_allowed"] = True
    with pytest.raises(AlphaContractError, match="cannot set"):
        validate_source_failure(obj, expected_day=DAY)


def test_retry_limit_skips_old_unresolved_gap_but_manual_can_recover(
    tmp_path: Path,
) -> None:
    for number in range(MAX_AUTOMATED_ATTEMPTS_PER_DAY):
        append_source_failure(tmp_path, _attempt(run=f"github-10000{number}-1"))
    automatic = runner.pending_source_dates(
        tmp_path,
        today_ist=date(2026, 10, 12),
        start_date=None,
        end_date=None,
    )
    assert DAY not in automatic
    assert date(2026, 10, 10) in automatic
    assert date(2026, 10, 11) in automatic
    assert len(source_attempts_for_day(tmp_path, DAY)) == 3
    manual = runner.pending_source_dates(
        tmp_path, today_ist=date(2026, 10, 12),
        start_date=DAY, end_date=DAY,
    )
    assert manual == [DAY]
    (tmp_path / "2026-10-09-v1.json").write_text("record sealed")
    assert runner.pending_source_dates(
        tmp_path, today_ist=date(2026, 10, 12),
        start_date=DAY, end_date=DAY,
    ) == []


def test_bad_old_attempt_blocks_resolver_instead_of_ignoring_it(tmp_path: Path) -> None:
    receipt = append_source_failure(tmp_path, _attempt())
    obj = json.loads(receipt.read_text(encoding="utf-8"))
    obj["attempt_identity"] = "bogus-id"
    receipt.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(AlphaContractError, match="file identity mismatch|hash mismatch"):
        runner.pending_source_dates(
            tmp_path, today_ist=date(2026, 10, 12),
            start_date=DAY, end_date=DAY,
        )


def test_real_runner_nse_announcement_outage_is_recorded_not_rethrown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    class FakeNSE:
        def __init__(self, *, timeout: float, attempts: int) -> None:
            assert timeout == 25
            assert attempts == 4

        def all_equity_csv(self) -> bytes:
            return b"official equity list fixture"

        def corporate_announcements_with_raw(self, symbol, *, from_date, to_date):
            assert symbol is None
            assert from_date == to_date == "09-10-2026"
            raise NSEAcquisitionError("NSE corporate_announcements failed: Read timed out")

    monkeypatch.setattr(runner, "NSEClient", FakeNSE)
    monkeypatch.setenv("GITHUB_RUN_ID", "38056665478")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setattr(
        sys, "argv", [
            "run_ss002_p001_daily.py",
            "--repo-root", str(tmp_path),
            "--start-date", "2026-10-09",
            "--end-date", "2026-10-09",
        ],
    )
    runner.main()
    root = tmp_path / "research/prospective/ss002-p001"
    observed = source_attempts_for_day(root, DAY)
    assert len(observed) == 1
    assert observed[0]["source_phase"] == "CORPORATE_ANNOUNCEMENTS_FETCH"
    assert observed[0]["attempt_identity"] == "github-38056665478-1"
    assert not (root / "2026-10-09-v1.json").exists()
    assert not (root / "raw").exists()


def test_real_runner_equity_master_outage_remains_a_gap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    class FakeNSE:
        def __init__(self, *, timeout: float, attempts: int) -> None:
            pass

        def all_equity_csv(self) -> bytes:
            raise NSEAcquisitionError("HTTP 403")

    monkeypatch.setattr(runner, "NSEClient", FakeNSE)
    monkeypatch.setenv("GITHUB_RUN_ID", "38056665479")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setattr(
        sys, "argv", [
            "run_ss002_p001_daily.py",
            "--repo-root", str(tmp_path),
            "--start-date", "2026-10-09",
            "--end-date", "2026-10-09",
        ],
    )
    runner.main()
    root = tmp_path / "research/prospective/ss002-p001"
    record = source_attempts_for_day(root, DAY)[0]
    assert record["source_phase"] == "EQUITY_MASTER_FETCH"
    assert record["source_failure_reason"] == "OFFICIAL_NSE_HTTP_REJECTED"
    assert record["announcement_count"] is None
    assert not (root / "2026-10-09-v1.json").exists()
