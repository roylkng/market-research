from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_special_shp import (
    AUDIT_ID,
    BASIC_QIP_SHARES,
    BROADCAST_UTC,
    MASTER_PATH,
    REPORT_DATE,
    SPECIAL_ID,
    SPECIAL_URL,
    interpret_special_xbrl,
    verify_original_special_master,
)
from scripts import collect_hg007_special_shp as collector


def test_original_oct8_broadcast_sept29_qip_is_not_regular_quarter() -> None:
    record = verify_original_special_master(Path("."))
    assert record["special_source_id"] == SPECIAL_ID
    assert record["original_xbrl_url"] == SPECIAL_URL
    assert record["as_of_allotment_date"] == REPORT_DATE
    assert record["exchange_first_public_broadcast_at_utc"] == BROADCAST_UTC
    assert record["issuer_master_promoter_percentage"] == 53.7
    assert record["issuer_master_public_percentage"] == 46.3
    assert record["special_not_standard_september_quarter"] is True


def test_original_source_has_exact_issuer_no_company_substitution(tmp_path: Path) -> None:
    target = tmp_path / MASTER_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(MASTER_PATH.read_bytes())
    assert verify_original_special_master(tmp_path)["special_source_id"] == SPECIAL_ID
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="original NSE.*bytes changed"):
        verify_original_special_master(tmp_path)


def test_special_xbrl_must_have_actual_post_qip_basic_and_asof_pledge_boolean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import marketlab.hg007_special_shp as impl

    monkeypatch.setattr(
        impl, "parse_shareholding_counts",
        lambda raw, *, symbol: {
            "fully_paid_shares": BASIC_QIP_SHARES,
            "fully_diluted_shares": BASIC_QIP_SHARES + 2_467_620,
        },
    )
    monkeypatch.setattr(
        impl, "parse_current_governance_xbrl",
        lambda raw, *, symbol, report_date, source_url: {
            "parser_status": "CORE_READY",
            "promoter_percentage": 53.7,
            "public_percentage": 46.3,
            "promoter_encumbrance": {"pledge": True},
        },
    )
    result = interpret_special_xbrl(
        verify_original_special_master(Path(".")),
        b"<xbrl>" + b"x" * 2500 + b"</xbrl>",
        retrieved_at_utc="2026-10-11T02:20:00Z",
    )
    assert result["issuer_capital_date"] == "2026-09-29"
    assert result["nse_public_broadcast_utc"] == "2026-10-08T13:24:47Z"
    assert result["reported_issued_basic_shares_as_of_sep29"] == 419_602_518
    assert result["reported_dilutive_instruments_delta_to_basic"] == 2_467_620
    assert result["promoter_pledge_boolean_as_of_report"] is True
    assert result["claim_of_4_9m_pledged_shares_verified"] is False
    assert result["current_asof_oct11_fully_diluted_shares_confirmed"] is False
    assert result["stock_expected_returns_calculated"] is False
    assert result["live_capital_allowed"] is False
    assert result["portfolio_eligibility_allowed"] is False


def test_qip_capital_mismatch_or_time_travel_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import marketlab.hg007_special_shp as impl

    monkeypatch.setattr(
        impl, "parse_shareholding_counts",
        lambda raw, *, symbol: {
            "fully_paid_shares": 401_492_045,
            "fully_diluted_shares": 403_959_665,
        },
    )
    monkeypatch.setattr(
        impl, "parse_current_governance_xbrl",
        lambda raw, *, symbol, report_date, source_url: {
            "parser_status": "CORE_READY",
            "promoter_percentage": 53.7,
            "public_percentage": 46.3,
            "promoter_encumbrance": {"pledge": True},
        },
    )
    master = verify_original_special_master(Path("."))
    with pytest.raises(ValueError, match="QIP basic shares"):
        interpret_special_xbrl(
            master, b"<xbrl>" + b"x"*1200,
            retrieved_at_utc="2026-10-11T02:20:00Z",
        )
    with pytest.raises(ValueError, match="before NSE broadcast"):
        interpret_special_xbrl(
            master, b"<xbrl>" + b"x"*1200,
            retrieved_at_utc="2026-10-08T12:00:00Z",
        )


def test_collector_blocked_response_retains_source_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from marketlab.h023_acquisition import H023AcquisitionError

    monkeypatch.setattr(collector, "xbrl_session", lambda: object())

    def unavailable(*args, **kwargs):
        raise H023AcquisitionError("HTTP 403")

    monkeypatch.setattr(collector, "fetch_xbrl", unavailable)
    report, raw = collector.collect_source(Path("."))
    assert report["status"] == "XBRL_SOURCE_UNAVAILABLE"
    assert raw is None
    assert report["live_capital_allowed"] is False
    assert report["pledge_quantity_4_9m_certified"] is False
    collector.save_source(tmp_path, report, raw)
    assert not (tmp_path/"raw").exists()
    original_receipt = json.loads((tmp_path/"original-receipt-v1.json").read_text())
    assert original_receipt["status"] == "XBRL_SOURCE_UNAVAILABLE"


def test_raw_sha_and_retained_xml_must_match_receipt(tmp_path: Path) -> None:
    raw = b"<xbrl>" + b"a" * 2000 + b"</xbrl>"
    digest = hashlib.sha256(raw).hexdigest()
    packet = {
        "audit_id": AUDIT_ID,
        "original_xbrl_sha256": digest,
        "status": "ORIGINAL_XBRL_BYTES_CAPTURED_SEMANTICS_BLOCKED",
        "oct11_current_shares_certified": False,
        "live_capital_allowed": False,
    }
    collector.save_source(tmp_path, packet, raw)
    assert (tmp_path/"raw"/f"{digest}.xml").read_bytes() == raw
    collector.save_source(tmp_path, deepcopy(packet), raw)
    broken = deepcopy(packet)
    broken["original_xbrl_sha256"] = "0"*64
    with pytest.raises(ValueError, match="SHA mismatch"):
        collector.save_source(tmp_path, broken, raw)
    assert json.loads((tmp_path/"original-receipt-v1.json").read_text()) == packet


def test_bad_source_row_and_duplicate_id_are_rejected() -> None:
    original = verify_original_special_master(Path("."))
    original["special_source_id"] = "another_id"
    with pytest.raises(ValueError, match="substituted"):
        interpret_special_xbrl(
            original, b"<xbrl>"+b"x"*2000,
            retrieved_at_utc="2026-10-11T02:20:00Z",
        )
