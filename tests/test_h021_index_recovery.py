from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
import requests

from marketlab.h021_index_recovery import (
    ORIGINAL_FIRST_PACKET,
    ORIGINAL_PACKET_SHA,
    ORIGINAL_STOCK_SHA,
    SEALABLE_STATES,
    SOURCE_URLS,
    build_recovery,
    read_originals,
    validate_recovery,
)
from scripts.recover_h021_nifty500_original import retrieve_index_source, write_attempt


CAPTURE = "2026-10-12T15:00:00Z"
RECORD = "2026-10-12T15:01:00Z"


def _csv(*, day: str = "12-10-2026", close: str = "21822.75") -> bytes:
    return (
        "Index Name,Index Date,Open Index Value,Closing Index Value\n"
        "Nifty 50,12-10-2026,22593.2,22429.5\n"
        f"Nifty 500,{day},21936.25,{close}\n"
    ).encode()


def _source(name: str, raw: bytes | None = None, *, status: str = "OK") -> dict:
    if status == "OK" and raw is None:
        raw = _csv()
    return {
        "status": status,
        "url": SOURCE_URLS[name],
        "captured_at_utc": CAPTURE,
        "http_status": 200 if status == "OK" else 404,
        "raw": raw if status == "OK" else None,
        "error": None if status == "OK" else "NSE_DAILY_INDEX_NOT_PUBLISHED",
    }


def _built(*, primary: dict, mirror: dict) -> dict:
    return build_recovery(
        read_originals(Path(".")),
        source_candidates={"primary": primary, "nse_archive_mirror": mirror},
        recorded_at_utc=RECORD,
    )


def test_exact_original_partial_nse_stock_packet_is_preserved() -> None:
    base = read_originals(Path("."))
    assert base["original_packet_sha256"] == ORIGINAL_PACKET_SHA
    assert base["original_equity_sha256"] == ORIGINAL_STOCK_SHA
    assert base["original_stock_open_count"] == 10
    assert base["entry_session"] == "2026-10-12"
    assert base["original_first_index_status"] == "NOT_PUBLISHED"
    assert base["frozen_selection_symbols"] == [
        "VEDL", "ETERNAL", "DMART", "IDEA", "ADANIENSOL",
        "JSWSTEEL", "COALINDIA", "INFY", "GAIL", "POWERGRID"
    ]


def test_only_official_primary_oct12_csv_may_seal_unbackdated_supplement() -> None:
    result = _built(
        primary=_source("primary"),
        mirror=_source("nse_archive_mirror", status="NOT_PUBLISHED"),
    )
    validate_recovery(result)
    assert result["source_state"] == "OFFICIAL_PRIMARY_INDEX_VERIFIED"
    assert result["verified_primary_or_agreed_dual_index_source"] is True
    assert result["benchmark"]["corroborated_recovery_open"] == 21936.25
    assert result["benchmark"]["corroborated_recovery_close"] == 21822.75
    assert result["first_original_source_attempt_unmodified"] is True
    assert result["nifty500_price_index_not_tri"] is True
    assert result["first_original_equity_source"]["original_stock_open_count"] == 10
    assert result["stock_price_source_substituted"] is False
    assert result["actual_executable_open_trade_confirmed"] is False
    assert result["benchmark_excess_return_calculated"] is False
    assert result["return_outcomes_opened"] is False
    assert result["live_capital_allowed"] is False


def test_secondary_official_archive_host_only_is_not_an_approved_benchmark() -> None:
    result = _built(
        primary=_source("primary", status="NOT_PUBLISHED"),
        mirror=_source("nse_archive_mirror"),
    )
    assert result["source_state"] == "SECONDARY_NSE_ARCHIVE_ONLY_PENDING_CORROBORATION"
    assert result["verified_primary_or_agreed_dual_index_source"] is False
    assert result["benchmark"]["observed_secondary_open"] == 21936.25
    assert result["benchmark"]["corroborated_recovery_open"] is None
    assert result["benchmark"]["corroborated_recovery_close"] is None


def test_both_official_archive_hosts_agree_and_original_first_capture_stays_404() -> None:
    original = json.loads(ORIGINAL_FIRST_PACKET.read_text(encoding="utf-8"))
    original_copy = deepcopy(original)
    a = _built(primary=_source("primary"), mirror=_source("nse_archive_mirror"))
    validate_recovery(a)
    assert a["source_state"] == "OFFICIAL_DUAL_HOSTS_AGREE"
    assert a["verified_primary_or_agreed_dual_index_source"] is True
    assert original == original_copy
    assert original["benchmark_observation"]["open_index_value"] is None
    assert original["source_receipts"]["index"]["http_status"] == 404


def test_conflicting_official_index_host_csv_never_seals() -> None:
    result = _built(
        primary=_source("primary"),
        mirror=_source("nse_archive_mirror", _csv(close="21855.65")),
    )
    assert result["source_state"] == "CONFLICT_BETWEEN_OFFICIAL_NSE_ARCHIVE_HOSTS"
    assert result["verified_primary_or_agreed_dual_index_source"] is False
    assert result["benchmark"]["corroborated_recovery_close"] is None


def test_404_on_both_preserves_no_benchmark_and_original_source() -> None:
    result = _built(
        primary=_source("primary", status="NOT_PUBLISHED"),
        mirror=_source("nse_archive_mirror", status="NOT_PUBLISHED"),
    )
    assert result["source_state"] == "OFFICIAL_OCT12_INDEX_NOT_YET_AVAILABLE"
    assert result["raw_source_byte_counts_retained"] == {}
    assert result["first_original_equity_source"]["original_stock_open_count"] == 10
    assert result["benchmark_excess_return_calculated"] is False
    assert result["portfolio_eligibility_allowed"] is False


def test_wrong_index_session_row_or_html_is_never_accepted() -> None:
    bad_day = _built(
        primary=_source("primary", _csv(day="09-10-2026")),
        mirror=_source("nse_archive_mirror", status="NOT_PUBLISHED"),
    )
    assert bad_day["source_state"] == "BLOCKED_UNPARSEABLE_NSE_INDEX_SOURCE"
    assert bad_day["benchmark"]["corroborated_recovery_open"] is None
    html = _built(
        primary=_source("primary", b"<html>Access denied</html>"),
        mirror=_source("nse_archive_mirror", status="NOT_PUBLISHED"),
    )
    assert html["source_state"] == "BLOCKED_UNPARSEABLE_NSE_INDEX_SOURCE"
    assert html["verified_primary_or_agreed_dual_index_source"] is False


def test_missing_date_or_fake_source_hostname_and_wrong_timing_rejected() -> None:
    bad = _source("primary")
    bad["url"] = "https://archives.nseindia.com.evil.invalid/file.csv"
    with pytest.raises(ValueError, match="exact declared"):
        _built(primary=bad, mirror=_source("nse_archive_mirror"))
    bad = _source("primary")
    bad["captured_at_utc"] = "2026-10-12T09:55:00Z"
    with pytest.raises(ValueError, match="predate"):
        _built(primary=bad, mirror=_source("nse_archive_mirror"))


def test_packet_digest_cannot_be_modified_into_a_return() -> None:
    result = _built(
        primary=_source("primary"), mirror=_source("nse_archive_mirror")
    )
    result["return_outcomes_opened"] = True
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_recovery(result)


def test_original_official_csv_retained_by_sha_and_provenance(tmp_path: Path) -> None:
    original = read_originals(Path("."))
    candidates = {
        "primary": _source("primary"),
        "nse_archive_mirror": _source("nse_archive_mirror", status="NOT_PUBLISHED"),
    }
    out = write_attempt(
        tmp_path, original=original, sources=candidates, recorded_at_utc=RECORD
    )
    assert out["source_state"] in SEALABLE_STATES
    assert out["observed_index_primary_or_dual_verified"] is True
    assert len(out["original_raw_csv_files_retained"]) == 1
    path = tmp_path / out["original_raw_csv_files_retained"][0]["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == out[
        "original_raw_csv_files_retained"
    ][0]["sha256"]
    saved = json.loads((tmp_path / "index-source-evidence-v1.json").read_text())
    validate_recovery(saved)
    assert saved["packet_sha256"] == out["packet_sha256"]


def test_nse_access_denial_stops_immediately_without_redirect_bypass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Forbidden:
        status_code = 403
        content = b"Forbidden"

    def getter(url: str, **kwargs: object) -> Forbidden:
        calls.append((url, kwargs))
        return Forbidden()

    monkeypatch.setattr(requests, "get", getter)
    result = retrieve_index_source("primary", attempts=3, sleep_seconds=0)
    assert result["status"] == "ACCESS_BLOCKED"
    assert result["raw"] is None
    assert result["http_status"] == 403
    assert len(calls) == 1
    assert calls[0][0] == SOURCE_URLS["primary"]
    assert calls[0][1]["allow_redirects"] is False
