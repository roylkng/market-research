from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h023_acquisition import H023AcquisitionError
from marketlab.hg007_shp_source import (
    MASTER_URL,
    review_original_xbrl,
    select_latest_official_filing,
)
from scripts import acquire_hg007_inoxgreen_shp as collector


def _row(day: str, broadcast: str, record_id: str) -> dict:
    return {
        "date": day,
        "symbol": "INOXGREEN",
        "broadcastDate": broadcast,
        "recordId": record_id,
        "xbrl": f"https://nsearchives.nseindia.com/corporate/xbrl/{record_id}.xml",
    }


def _master() -> bytes:
    rows = [
        _row("30-JUN-2026", "10-JUL-2026 11:20:00", "old"),
        _row("29-SEP-2026", "29-SEP-2026 14:00:00", "post_qip_event"),
        _row("30-SEP-2026", "10-OCT-2026 08:30:00", "new"),
    ]
    return json.dumps(rows).encode("utf-8")


def test_master_source_distinguishes_official_reg31_and_special_allotment() -> None:
    report = select_latest_official_filing(
        _master(), captured_at_utc="2026-10-11T03:00:00Z"
    )
    assert report["issuer"] == "INOXGREEN"
    assert report["master_url"] == MASTER_URL
    assert report["standard_quarter_candidate_count"] == 2
    assert report["visible_by_capture_quarter_count"] == 2
    assert report["sept30_quarter_filing_visible_at_capture"] is True
    assert report["original_latest_visible_standard_quarter"]["report_date"] == (
        "2026-09-30"
    )
    assert report["original_latest_visible_standard_quarter"]["record_id"] == "new"
    assert len(report["special_nonstandard_september_event_rows"]) == 1
    assert report["special_nonstandard_september_event_rows"][0][
        "qip_special_event_not_standard_reg31"
    ] is True
    assert report["asof_sep30_esop_balance_source_verified"] is False
    assert report["full_oct11_current_fd_certified"] is False
    assert report["legacy_h023_source_ledger_reused"] is False


def test_only_pre_capture_broadcast_visible_and_no_future_leakage() -> None:
    prior = select_latest_official_filing(
        _master(), captured_at_utc="2026-10-09T13:00:00Z"
    )
    assert prior["sept30_quarter_filing_visible_at_capture"] is False
    assert prior["original_latest_visible_standard_quarter"]["report_date"] == (
        "2026-06-30"
    )


def test_missing_source_and_ambiguous_same_broadcast_fail_closed() -> None:
    empty = select_latest_official_filing(
        b"[]", captured_at_utc="2026-10-11T03:00:00Z"
    )
    assert empty["original_latest_visible_standard_quarter"] is None
    assert empty["sept30_quarter_filing_visible_at_capture"] is False
    malformed = json.dumps({"data": [_row("30-SEP-2026", "10-OCT-2026 08:30:00", "a")]}).encode()
    with pytest.raises(TypeError, match="list"):
        select_latest_official_filing(
            malformed, captured_at_utc="2026-10-11T03:00:00Z"
        )
    duplicates = [
        _row("30-SEP-2026", "10-OCT-2026 08:30:00", "a"),
        _row("30-SEP-2026", "10-OCT-2026 08:30:00", "b"),
    ]
    with pytest.raises(ValueError, match="competing latest"):
        select_latest_official_filing(
            json.dumps(duplicates).encode(), captured_at_utc="2026-10-11T03:00:00Z"
        )
    changed_symbol = [_row("30-SEP-2026", "10-OCT-2026 08:30:00", "a")]
    changed_symbol[0]["symbol"] = "NOTINOXGREEN"
    with pytest.raises(ValueError, match="source identity"):
        select_latest_official_filing(
            json.dumps(changed_symbol).encode(),
            captured_at_utc="2026-10-11T03:00:00Z",
        )


def test_xbrl_retains_sep30_esop_and_pledge_with_exact_asof_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import marketlab.hg007_shp_source as module

    monkeypatch.setattr(
        module, "parse_shareholding_counts",
        lambda raw, *, symbol: {
            "fully_paid_shares": 419_602_518,
            "fully_diluted_shares": 422_070_138,
        },
    )
    monkeypatch.setattr(
        module, "parse_current_governance_xbrl",
        lambda raw, *, symbol, report_date, source_url: {
            "parser_status": "CORE_READY",
            "promoter_percentage": 53.7,
            "promoter_encumbrance": {"pledge": True},
            "core_failure_reason": None,
        },
    )
    discovery = select_latest_official_filing(
        _master(), captured_at_utc="2026-10-11T03:00:00Z"
    )
    result = review_original_xbrl(
        discovery, b"<xbrl>source</xbrl>",
        retrieved_at_utc="2026-10-11T03:00:03Z",
    )
    assert result["report_date"] == "2026-09-30"
    assert result["fully_paid_issued_shares_in_filing"] == 419_602_518
    assert result["outstanding_options_convertibles_delta_to_basic"] == 2_467_620
    assert result["promoter_pledge_declared_as_of_report"] is True
    assert result["sept30_promoter_pledge_independently_sourced"] is True
    assert result["sept30_options_balance_independently_sourced"] is True
    assert result["actual_pledged_share_quantity_verified"] is False
    assert result["current_oct11_fully_diluted_shares_verified"] is False
    assert result["company_target_price_authorized"] is False
    assert result["live_capital_allowed"] is False

    monkeypatch.setattr(
        module, "parse_shareholding_counts",
        lambda raw, *, symbol: {
            "fully_paid_shares": 419_602_517,
            "fully_diluted_shares": 422_070_138,
        },
    )
    conflict = review_original_xbrl(
        discovery, b"<xbrl>different</xbrl>",
        retrieved_at_utc="2026-10-11T03:01:00Z",
    )
    assert conflict["issuer_basic_qip_xbrl_conflict"] is True
    assert conflict["sept30_options_balance_independently_sourced"] is False
    assert conflict["sept30_promoter_pledge_independently_sourced"] is False


def test_collector_failure_keeps_original_unavailable_not_a_false_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collector, "master_session", lambda timeout: object())

    def fail_fetch(session, *, symbol, timeout, attempts):
        raise H023AcquisitionError("source failed HTTP 403")

    monkeypatch.setattr(collector, "fetch_master", fail_fetch)
    attempt, raw = collector.attempt_official_shareholding_acquisition()
    assert attempt["status"] == "MASTER_UNAVAILABLE_OR_MALFORMED"
    assert "403" in attempt["blocking_reason"]
    assert raw == {}
    assert attempt["current_fd_shares_verified"] is False
    assert attempt["reported_pledge_change_verified"] is False
    assert attempt["portfolio_eligibility_allowed"] is False


def test_source_bytes_retention_verified_and_no_rewrite(tmp_path: Path) -> None:
    data = _master()
    obj = select_latest_official_filing(
        data, captured_at_utc="2026-10-11T03:00:00Z"
    )
    attempt = {
        "schema_version": 1,
        "collector_id": collector.COLLECTOR_ID,
        "status": "MASTER_CAPTURED",
        "master_source": obj,
        "official_xbrl_review": None,
        "current_fd_shares_verified": False,
        "live_capital_allowed": False,
    }
    original = deepcopy(attempt)
    collector.retain_acquisition(tmp_path, attempt, {"master": data})
    assert attempt == original
    receipt = json.loads((tmp_path / "receipt-v1.json").read_text())
    sha = hashlib.sha256(data).hexdigest()
    assert receipt["original_content_addressed_sources"]["master"]["sha256"] == sha
    assert (tmp_path / "source" / f"master-{sha}.json").read_bytes() == data
    with pytest.raises(ValueError, match="overwritten"):
        collector.retain_acquisition(
            tmp_path, {**attempt, "status": "UNEXPECTED"}, {"master": data}
        )


def test_source_xbrl_retrieved_before_master_source_rejected() -> None:
    obj = select_latest_official_filing(
        _master(), captured_at_utc="2026-10-11T03:00:00Z"
    )
    with pytest.raises(ValueError, match="before the original source master"):
        review_original_xbrl(
            obj, b"<xml>data</xml>", retrieved_at_utc="2026-10-10T03:00:00Z"
        )
