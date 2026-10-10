from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h023_acquisition import H023AcquisitionError as H023Error
from marketlab.hg007_ownership_source import (
    ISSUED_QIP_SHARES,
    _archive_url,
    _nse_master_url,
    evaluate_source_xbrl,
    select_latest_dated_master_source,
    validated_receipt,
)
from scripts import probe_hg007_inoxgreen_ownership as collector

CAPTURE = "2026-10-10T12:00:00Z"
EXCHANGE_ARCHIVE = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "INOXGREEN-SPECIAL-20260929.xml"
)


def _master(include_qip: bool = True) -> bytes:
    rows = [{
        "symbol": "INOXGREEN", "date": "30-Jun-2026",
        "broadcastDate": "15-Jul-2026 12:00:00",
        "recordId": 10,
        "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/old-20260630.xml",
    }]
    if include_qip:
        rows.append({
            "symbol": "INOXGREEN", "date": "29-Sep-2026",
            "broadcastDate": "30-Sep-2026 19:00:00",
            "recordId": 20, "xbrl": EXCHANGE_ARCHIVE,
        })
    return json.dumps(rows).encode()


def _xbrl(
    *,
    shares: int = ISSUED_QIP_SHARES,
    extra: int = 2467620,
    pledge: str = "true",
) -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:xbrldi="http://xbrl.org/2006/xbrldi">
  <xbrli:context id="MainI"><xbrli:entity/><xbrli:period><xbrli:instant>2026-09-29</xbrli:instant></xbrli:period></xbrli:context>
  <xbrli:context id="ShareholdingPattern_ContextI"><xbrli:entity/><xbrli:period><xbrli:instant>2026-09-29</xbrli:instant></xbrli:period></xbrli:context>
  <xbrli:context id="ShareholdingOfPromoterAndPromoterGroup_ContextI"><xbrli:entity/><xbrli:period><xbrli:instant>2026-09-29</xbrli:instant></xbrli:period><xbrli:scenario>
    <xbrldi:explicitMember dimension="in-shp:CategoryOfShareholdersAxis">in-shp:ShareholdingOfPromoterAndPromoterGroupMember</xbrldi:explicitMember>
  </xbrli:scenario></xbrli:context>
  <xbrli:context id="PublicShareholding_ContextI"><xbrli:entity/><xbrli:period><xbrli:instant>2026-09-29</xbrli:instant></xbrli:period><xbrli:scenario>
    <xbrldi:explicitMember dimension="in-shp:CategoryOfShareholdersAxis">in-shp:PublicShareholdingMember</xbrldi:explicitMember>
  </xbrli:scenario></xbrli:context>
  <Symbol>INOXGREEN</Symbol>
  <NumberOfFullyPaidUpEquityShares contextRef="ShareholdingPattern_ContextI" unitRef="shares">{shares}</NumberOfFullyPaidUpEquityShares>
  <NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities contextRef="ShareholdingPattern_ContextI" unitRef="shares">{shares+extra}</NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities>
  <ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="ShareholdingOfPromoterAndPromoterGroup_ContextI">0.537</ShareholdingAsAPercentageOfTotalNumberOfShares>
  <ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="PublicShareholding_ContextI">0.463</ShareholdingAsAPercentageOfTotalNumberOfShares>
  <WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup contextRef="MainI">{pledge}</WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup>
  <WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup contextRef="MainI">false</WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup>
  <WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup contextRef="MainI">false</WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup>
</xbrl>'''.encode()


def test_latest_selects_special_september_allotment_date_not_older_june() -> None:
    result = select_latest_dated_master_source(_master(), captured_at_utc=CAPTURE)
    assert result["selected_source"]["report_date"] == "2026-09-29"
    assert result["source_is_post_qip_as_of_report_date"] is True
    assert result["source_is_a_special_allotment_date_not_standard_quarter"] is True
    assert result["distinct_report_dates"] == ["2026-06-30", "2026-09-29"]
    assert result["original_master_sha256"] == hashlib.sha256(_master()).hexdigest()


def test_reconciled_xbrl_confirms_asof_pledge_boolean_not_pledged_quantity() -> None:
    selected = select_latest_dated_master_source(_master(), captured_at_utc=CAPTURE)
    reviewed = evaluate_source_xbrl(
        selected, _xbrl(), xbrl_captured_at_utc="2026-10-10T12:01:00Z"
    )
    validated_receipt(reviewed)
    assert reviewed["source_status"] == (
        "POST_QIP_XBRL_SHARE_COUNT_AND_GOVERNANCE_RECONCILED"
    )
    assert reviewed["original_reported_issued_basic_shares"] == 419_602_518
    assert reviewed["original_reported_fully_diluted_shares"] == 422_070_138
    assert reviewed["original_reported_option_and_other_instruments_difference"] == 2_467_620
    assert reviewed["official_reported_promoter_percentage"] == pytest.approx(53.7)
    assert reviewed["official_reported_promoter_pledge_boolean"] is True
    assert reviewed["official_reported_promoter_non_disposal_boolean"] is False
    assert reviewed["official_reported_raw_pledged_share_count"] is None
    assert reviewed["current_fully_diluted_market_cap_verified"] is False
    assert reviewed["current_promoter_pledge_quantity_verified"] is False
    assert reviewed["portfolio_eligibility_allowed"] is False
    assert reviewed["live_capital_allowed"] is False


def test_pre_qip_latest_remains_stale_and_does_not_assert_latest_pledge() -> None:
    m = select_latest_dated_master_source(_master(False), captured_at_utc=CAPTURE)
    assert m["source_is_post_qip_as_of_report_date"] is False
    # The first two source records in this test are separated by QIP.
    assert m["selected_source"]["report_date"] == "2026-06-30"
    review = evaluate_source_xbrl(
        m, _xbrl(shares=401_492_045, pledge="false"),
        xbrl_captured_at_utc="2026-10-10T12:01:00Z",
    )
    assert review["source_status"] == "PRE_QIP_ONLY_OFFICIAL_SHAREHOLDING_SOURCE"
    assert review["official_reported_promoter_pledge_boolean"] is None


def test_source_share_count_conflict_and_invalid_xbrl_do_not_promote_claims() -> None:
    m = select_latest_dated_master_source(_master(), captured_at_utc=CAPTURE)
    conflict = evaluate_source_xbrl(
        m, _xbrl(shares=410_000_000), xbrl_captured_at_utc="2026-10-10T12:01:00Z"
    )
    assert conflict["source_status"] == "POST_QIP_XBRL_SHARE_COUNT_DISAGREES_WITH_QIP"
    assert conflict["official_reported_promoter_pledge_boolean"] is None
    bad = evaluate_source_xbrl(
        m, b"<html>login page</html>", xbrl_captured_at_utc="2026-10-10T12:01:00Z"
    )
    assert bad["source_status"] == "POST_QIP_XBRL_UNPARSEABLE"
    assert bad["original_reported_issued_basic_shares"] is None


def test_future_report_and_ambiguous_revision_fail_closed() -> None:
    records = json.loads(_master())
    records[1]["broadcastDate"] = "11-Oct-2026 15:00:00"
    with pytest.raises(ValueError, match="future"):
        select_latest_dated_master_source(
            json.dumps(records).encode(), captured_at_utc=CAPTURE
        )
    records = json.loads(_master())
    duplicate = dict(records[1], recordId=21)
    records.append(duplicate)
    with pytest.raises(ValueError, match="ambiguous latest"):
        select_latest_dated_master_source(
            json.dumps(records).encode(), captured_at_utc=CAPTURE
        )


def test_invalid_and_spoofed_source_urls_refused() -> None:
    assert _archive_url(EXCHANGE_ARCHIVE) is True
    assert _archive_url(
        "https://nsearchives.nseindia.com.evil.invalid/corporate/xbrl/owner.xml"
    ) is False
    assert _nse_master_url(
        "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=INOXGREEN"
    ) is True
    assert not _nse_master_url(
        "https://www.nseindia.com@evil.invalid/api/corporate-share-holdings-master?index=equities&symbol=INOXGREEN"
    )
    records = json.loads(_master())
    records[1]["xbrl"] = "https://evil.example.com/fake.xml"
    with pytest.raises(ValueError, match="unapproved XBRL"):
        select_latest_dated_master_source(
            json.dumps(records).encode(), captured_at_utc=CAPTURE
        )


def test_dated_report_flags_cannot_authorize_current_fd_or_investing() -> None:
    selected = select_latest_dated_master_source(_master(), captured_at_utc=CAPTURE)
    packet = evaluate_source_xbrl(
        selected, _xbrl(), xbrl_captured_at_utc="2026-10-10T12:01:00Z"
    )
    altered = deepcopy(packet)
    altered["current_fully_diluted_market_cap_verified"] = True
    with pytest.raises(ValueError, match="cannot authorize"):
        validated_receipt(altered)


def test_content_addressed_original_master_and_xbrl_are_retained(
    tmp_path: Path,
) -> None:
    selected = select_latest_dated_master_source(_master(), captured_at_utc=CAPTURE)
    reviewed = evaluate_source_xbrl(
        selected, _xbrl(), xbrl_captured_at_utc="2026-10-10T12:01:00Z"
    )
    receipt = collector._receipt(
        "ORIGINAL_POST_QIP_MASTER_XBRL_RETAINED", reason="source only",
        master={"raw_sha256": hashlib.sha256(_master()).hexdigest()},
        latest=selected, reviewed=reviewed,
    )
    collector.retain_original(
        tmp_path, receipt, {"master.json": _master(), "original-xbrl.xml": _xbrl()}
    )
    contents = list((tmp_path / "raw" / "sha256").glob("*"))
    assert {f.suffix for f in contents} == {".xml", ".json"}
    assert json.loads((tmp_path / "receipt.json").read_text()) == receipt
    collector.retain_original(
        tmp_path, receipt, {"master.json": _master(), "original-xbrl.xml": _xbrl()}
    )
    with pytest.raises(ValueError, match="overwrite"):
        collector.retain_original(
            tmp_path, dict(receipt, state="FRAUD"),
            {"master.json": _master(), "original-xbrl.xml": _xbrl()},
        )


def test_403_does_not_trigger_fallback_or_fake_secondary_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collector, "master_session", lambda timeout: object())
    monkeypatch.setattr(
        collector, "fetch_master",
        lambda session, **kwargs: (_ for _ in ()).throw(H023Error("HTTP 403")),
    )
    receipt, raw = collector.acquire_source(timeout=8)
    assert receipt["state"] == "NSE_MASTER_SOURCE_UNAVAILABLE"
    assert "HTTP 403" in receipt["source_failure_or_limitation"]
    assert raw == {}
    assert receipt["live_capital_allowed"] is False




def test_explicit_original_nse_data_envelope_accepted_not_error_envelope() -> None:
    underlying = json.loads(_master())
    for key in ("data", "records"):
        wrapped = json.dumps({key: underlying, "total": len(underlying)}).encode()
        selected = select_latest_dated_master_source(
            wrapped, captured_at_utc=CAPTURE
        )
        assert selected["selected_source"]["report_date"] == "2026-09-29"
        assert selected["source_is_post_qip_as_of_report_date"] is True

    error_wrapped = json.dumps({
        "data": underlying, "status": "error", "message": "API unavailable"
    }).encode()
    with pytest.raises(ValueError, match="structured error"):
        select_latest_dated_master_source(
            error_wrapped, captured_at_utc=CAPTURE
        )
    wrong = json.dumps({"data": {"error": "blocked"}}).encode()
    with pytest.raises(TypeError, match="data/records list"):
        select_latest_dated_master_source(
            wrong, captured_at_utc=CAPTURE
        )


def test_actual_unknown_original_master_envelope_keeps_source_bytes_and_sha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from marketlab.hg007_ownership_source import NSE_MASTER_URL

    original = json.dumps({"status": "no data", "message": "not an array"}).encode()

    class SourceResponse:
        url = NSE_MASTER_URL
        history = ()
        status_code = 200
        content = original

    monkeypatch.setattr(collector, "master_session", lambda timeout: object())
    monkeypatch.setattr(collector, "fetch_master", lambda _session, **kw: SourceResponse())

    receipt, raw = collector.acquire_source(timeout=8.0)
    assert receipt["state"] == "NSE_MASTER_SOURCE_SCHEMA_UNVERIFIED"
    assert receipt["master_source_receipt"]["http_status"] == 200
    assert receipt["master_source_receipt"]["original_json_envelope_type"] == "dict"
    assert receipt["master_source_receipt"]["original_json_top_level_keys"] == [
        "message", "status"
    ]
    assert receipt["master_source_receipt"]["raw_sha256"] == hashlib.sha256(
        original
    ).hexdigest()
    assert raw == {"master.json": original}
    assert receipt["live_capital_allowed"] is False
    assert receipt["dated_original_xbrl_result"] is None
    collector.retain_original(tmp_path, receipt, raw)
    actual = tmp_path / "raw" / "sha256" / (
        hashlib.sha256(original).hexdigest() + ".json"
    )
    assert actual.read_bytes() == original


def test_wrapped_original_nse_records_reach_only_official_xbrl(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    from marketlab.hg007_ownership_source import NSE_MASTER_URL

    rows = json.dumps({"data": json.loads(_master())}).encode()

    class Master:
        url = NSE_MASTER_URL
        status_code = 200
        content = rows
        history = ()

    class Archive:
        url = EXCHANGE_ARCHIVE
        status_code = 200
        content = _xbrl()
        history = ()

    calls = []

    def fake_xbrl(_session: object, **kwargs: object) -> Archive:
        calls.append(kwargs)
        return Archive()

    monkeypatch.setattr(collector, "master_session", lambda timeout: object())
    monkeypatch.setattr(collector, "fetch_master", lambda _session, **kw: Master())
    monkeypatch.setattr(collector, "xbrl_session", lambda: object())
    monkeypatch.setattr(collector, "fetch_xbrl", fake_xbrl)
    receipt, raw = collector.acquire_source(timeout=8.0)
    assert receipt["state"] == "ORIGINAL_POST_QIP_MASTER_XBRL_RETAINED"
    assert receipt["dated_original_xbrl_result"]["source_status"] == (
        "POST_QIP_XBRL_SHARE_COUNT_AND_GOVERNANCE_RECONCILED"
    )
    assert receipt["dated_original_xbrl_result"][
        "official_reported_promoter_pledge_boolean"
    ] is True
    assert receipt["current_pledged_promoter_share_quantity_confirmed"] is False
    assert raw == {"master.json": rows, "original-xbrl.xml": _xbrl()}
    assert len(calls) == 1
    assert calls[0]["url"] == EXCHANGE_ARCHIVE
    assert calls[0]["attempts"] == 1
