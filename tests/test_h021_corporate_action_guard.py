from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_corporate_action_guard import (
    _official_source_url,
    require_h021_price_basis_clearance,
    screen_h021_corporate_actions,
)
from scripts.screen_h021_corporate_actions import frozen_original_ten

URL = "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
CAPTURE = "2026-12-01T13:00:00Z"
PREPARED = "2026-12-01T13:30:00Z"


def _run(rows: object, *, start: str = "2026-10-12", end: str = "2026-11-30") -> dict:
    raw = json.dumps(rows, sort_keys=True).encode()
    receipt = {
        "url": URL,
        "status": "OK",
        "http_status": 200,
        "captured_at_utc": CAPTURE,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }
    return screen_h021_corporate_actions(
        symbols_to_isins=frozen_original_ten(),
        interval_start=start,
        interval_end=end,
        raw_source=raw,
        source_receipt=receipt,
        prepared_at_utc=PREPARED,
    )


def test_frozen_ten_identity_and_original_source_no_clearance() -> None:
    selected = frozen_original_ten()
    assert list(selected) == [
        "VEDL", "ETERNAL", "DMART", "IDEA", "ADANIENSOL",
        "JSWSTEEL", "COALINDIA", "INFY", "GAIL", "POWERGRID",
    ]
    result = _run({"data": []})
    assert result["source_state"] == "SOURCE_SCREENED_COVERAGE_NOT_CERTIFIED"
    assert result["selected_symbol_count"] == 10
    assert result["corporate_event_hazard_count"] == 0
    assert result["separately_verified_exhaustive_source_coverage"] is False
    assert all(row["raw_price_return_eligible"] is False for row in result["symbol_states"])
    with pytest.raises(ValueError, match="remains unverified"):
        require_h021_price_basis_clearance(result)


def test_detects_share_changes_and_dividends_without_changing_h021_selection() -> None:
    selected = frozen_original_ten()
    result = _run({
        "data": [
            {"symbol": "VEDL", "subject": "Stock Split 1:5", "exDate": "10-Nov-2026"},
            {"symbol": "ETERNAL", "subject": "RIGHTS ISSUE", "exDate": "15-Nov-2026"},
            {"symbol": "DMART", "purpose": "Bonus Issue", "exDate": "18-Nov-2026"},
            {"symbol": "GAIL", "subject": "Merger Scheme of Arrangement", "exDate": "20-Nov-2026"},
            {"symbol": "INFY", "subject": "Interim Dividend", "exDate": "28-Nov-2026"},
            {"symbol": "COALINDIA", "subject": "Bonus Issue", "exDate": "05-Dec-2026"},
            {"symbol": "IGNORED", "subject": "Stock Split", "exDate": "10-Nov-2026"},
        ]
    })
    assert result["corporate_event_hazard_count"] == 5
    assert result["unclassified_event_count"] == 0
    by_symbol = {row["symbol"]: row for row in result["symbol_states"]}
    for symbol in ("VEDL", "ETERNAL", "DMART", "GAIL"):
        assert by_symbol[symbol]["state"] == "BLOCKED_ACTION_OR_IDENTITY_HAZARD"
        assert by_symbol[symbol]["source_reported_hazards"][0]["classification"] == (
            "SHARE_BASIS_ACTION"
        )
    assert by_symbol["INFY"]["source_reported_hazards"][0]["classification"] == (
        "CASH_DIVIDEND_ACTION"
    )
    assert by_symbol["COALINDIA"]["source_reported_hazards"] == []
    assert all(by_symbol[s]["isin"] == selected[s] for s in selected)
    assert result["return_outcomes_opened"] is False
    assert result["live_capital_allowed"] is False


def test_unrecognized_event_and_wrong_isin_block_silently_clearing() -> None:
    raw = {
        "data": [
            {"symbol": "VEDL", "subject": "Unknown corporate event", "exDate": "14-Nov-2026"},
            {"symbol": "IDEA", "purpose": "Bonus", "exDate": "unparseable"},
            {"symbol": "GAIL", "purpose": "Dividend", "exDate": "22-Nov-2026", "isin": "INEWRONG1234"},
        ]
    }
    result = _run(raw)
    assert result["corporate_event_hazard_count"] == 0
    assert result["unclassified_event_count"] == 3
    affected = {row["symbol"]: row for row in result["symbol_states"]
                if row["source_unknown_events"]}
    assert set(affected) == {"VEDL", "IDEA", "GAIL"}
    assert all(x["state"] == "BLOCKED_ACTION_OR_IDENTITY_HAZARD" for x in affected.values())


def test_invalid_json_and_error_envelopes_never_become_clean_empty_lists() -> None:
    invalid = _run({"error": "blocked"})
    assert invalid["source_state"] == "BLOCKED_UNVERIFIABLE_SOURCE_SCHEMA"
    assert invalid["source_returned_row_count"] is None
    assert not any(x["raw_price_return_eligible"] for x in invalid["symbol_states"])
    invalid_rows = _run({"data": [None, 1, {"symbol": "INFY"}]})
    assert invalid_rows["source_state"] == "BLOCKED_UNVERIFIABLE_SOURCE_SCHEMA"


def test_missing_and_blocked_source_cannot_prove_comparable_returns() -> None:
    no_source = screen_h021_corporate_actions(
        symbols_to_isins=frozen_original_ten(),
        interval_start="2026-10-12",
        interval_end="2026-10-30",
        raw_source=None,
        source_receipt=None,
        prepared_at_utc="2026-10-31T05:00:00Z",
    )
    assert no_source["source_state"] == "NO_ORIGINAL_SOURCE"
    assert no_source["share_adjustment_factors_verified"] is False

    blocked = screen_h021_corporate_actions(
        symbols_to_isins=frozen_original_ten(),
        interval_start="2026-10-12",
        interval_end="2026-10-30",
        raw_source=None,
        source_receipt={
            "url": URL,
            "status": "ACCESS_BLOCKED",
            "http_status": 403,
            "captured_at_utc": "2026-10-31T05:00:00Z",
            "error": "HTTP_403_NO_BYPASS",
        },
        prepared_at_utc="2026-10-31T05:15:00Z",
    )
    assert blocked["source_state"] == "BLOCKED_ACCESS_BLOCKED"
    with pytest.raises(ValueError, match="remains unverified"):
        require_h021_price_basis_clearance(blocked)


def test_refuses_spoofed_url_bad_hash_and_early_capture() -> None:
    raw = b'{"data":[]}'
    good_receipt = {
        "url": URL,
        "status": "OK",
        "http_status": 200,
        "captured_at_utc": CAPTURE,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }
    wrong = deepcopy(good_receipt)
    wrong["url"] = "https://www.nseindia.com.evil.invalid/api/corporates-corporateActions"
    with pytest.raises(ValueError, match="official NSE URL"):
        screen_h021_corporate_actions(
            symbols_to_isins=frozen_original_ten(),
            interval_start="2026-10-12",
            interval_end="2026-11-30",
            raw_source=raw,
            source_receipt=wrong,
            prepared_at_utc=PREPARED,
        )
    wrong = deepcopy(good_receipt)
    wrong["raw_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        screen_h021_corporate_actions(
            symbols_to_isins=frozen_original_ten(),
            interval_start="2026-10-12",
            interval_end="2026-11-30",
            raw_source=raw,
            source_receipt=wrong,
            prepared_at_utc=PREPARED,
        )
    stale = deepcopy(good_receipt)
    stale["captured_at_utc"] = "2026-11-30T03:00:00Z"
    checked = screen_h021_corporate_actions(
        symbols_to_isins=frozen_original_ten(),
        interval_start="2026-10-12",
        interval_end="2026-11-30",
        raw_source=raw,
        source_receipt=stale,
        prepared_at_utc=PREPARED,
    )
    assert checked["source_state"] == "BLOCKED_SOURCE_CAPTURE_BEFORE_INTERVAL_END"
    assert not checked["symbol_states"][0]["raw_price_return_eligible"]


def test_screen_is_immutable_and_cannot_be_self_promoted() -> None:
    screen = _run({"data": []})
    copied = deepcopy(screen)
    copied["share_adjustment_factors_verified"] = True
    with pytest.raises(ValueError, match="modified"):
        require_h021_price_basis_clearance(copied)

    screen["separately_verified_exhaustive_source_coverage"] = True
    screen["share_adjustment_factors_verified"] = True
    screen["dividends_total_return_basis_verified"] = True
    # Even a recomputed source-screen digest cannot replace independent review.
    from marketlab.h021_corporate_action_guard import _digest

    screen["packet_sha256"] = _digest(
        {key: value for key, value in screen.items() if key != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="only a hazard screen"):
        require_h021_price_basis_clearance(screen)


def test_cli_without_original_nse_bytes_reports_blocked_not_fake_clearance(
    tmp_path: Path,
) -> None:
    out = tmp_path / "screen.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/screen_h021_corporate_actions.py",
            "--interval-end",
            "2026-11-30",
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["source_state"] == "NO_ORIGINAL_SOURCE"
    assert result["selected_symbol_count"] == 10
    assert result["return_outcomes_opened"] is False
    fail = subprocess.run(
        [
            sys.executable,
            "scripts/screen_h021_corporate_actions.py",
            "--interval-end",
            "2026-11-30",
            "--require-return-clearance",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert fail.returncode != 0
    assert "remains unverified" in fail.stderr


def test_official_endpoint_detection_has_no_hostname_substring_loophole() -> None:
    assert _official_source_url(URL)
    assert not _official_source_url(
        "https://www.nseindia.com.evil.invalid/api/corporates-corporateActions"
    )
    assert not _official_source_url("http://www.nseindia.com/api/corporates-corporateActions")
    assert not _official_source_url("https://www.nseindia.com@evil.invalid/api/corporates-corporateActions")
