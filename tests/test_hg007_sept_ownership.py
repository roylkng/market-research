from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from marketlab import hg007_sept_ownership as m
from scripts import acquire_hg007_sept_ownership as collector


def _master(*, report="30-Sep-2026", broadcast="09-Oct-2026 13:00:28", record=1001) -> bytes:
    return json.dumps([
        {
            "symbol": "INOXGREEN",
            "recordId": record,
            "date": report,
            "broadcastDate": broadcast,
            "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/inoxgreen_sep2026.xml",
        }
    ]).encode("utf-8")


def _xbrl(*, day="2026-09-30", basic=419_602_518, diluted=422_070_138) -> bytes:
    return f"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:in-capmkt="http://www.sebi.gov.in/xbrl">
 <xbrli:context id="ShareholdingPattern_ContextI">
  <xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>{day}</xbrli:instant></xbrli:period>
 </xbrli:context>
 <xbrli:context id="MainI">
  <xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>{day}</xbrli:instant></xbrli:period>
 </xbrli:context>
 <in-capmkt:Symbol contextRef="MainI">INOXGREEN</in-capmkt:Symbol>
 <in-capmkt:NumberOfFullyPaidUpEquityShares
   contextRef="ShareholdingPattern_ContextI" unitRef="shares">{basic}</in-capmkt:NumberOfFullyPaidUpEquityShares>
 <in-capmkt:NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities
   contextRef="ShareholdingPattern_ContextI" unitRef="shares">{diluted}</in-capmkt:NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities>
</xbrli:xbrl>""".encode()


OBSERVED="2026-10-10T15:00:00Z"


def _mock_governance(monkeypatch: pytest.MonkeyPatch, pledge=True) -> None:
    monkeypatch.setattr(m, "parse_current_governance_xbrl", lambda *args, **kwargs: {
        "parser_status": "CORE_READY",
        "promoter_percentage": 53.7,
        "public_percentage": 46.3,
        "promoter_encumbrance": {
            "pledge": pledge,
            "non_disposal_undertaking": False,
            "other_encumbrance": False,
        },
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    })


def test_future_filing_is_not_retroactively_available() -> None:
    future=_master(broadcast="13-Oct-2026 13:00:28")
    source, summary = m.select_official_asof_master(future, captured_at_utc=OBSERVED)
    assert source is None
    assert summary["sept_2026_sources_broadcast_by_capture_count"] == 0
    snap=m.build_ownership_snapshot(
        master_raw=future, xbrl_raw=None, observed_at_utc=OBSERVED
    )
    assert snap["current_state"]=="SEPT_REPORT_NOT_OBSERVED_ON_OFFICIAL_MASTER_AT_CAPTURE"
    assert snap["share_counts_as_of_report_date"] is None
    assert snap["as_of_2026_10_10_fully_diluted_shares_independently_proven"] is False


def test_latest_official_revision_is_selected_but_ties_are_blocked() -> None:
    original=json.loads(_master())
    revised=json.loads(_master(broadcast="10-Oct-2026 20:00:28",record=1002))
    source, summary=m.select_official_asof_master(
        json.dumps(original+revised).encode(),
        captured_at_utc="2026-10-10T12:00:00Z",
    )
    assert source["record_id"]=="1001"
    assert summary["sept_2026_sources_broadcast_by_capture_count"]==1
    with pytest.raises(ValueError, match="ambiguous latest"):
        m.select_official_asof_master(
            json.dumps(original+json.loads(_master(record=1003))).encode(),
            captured_at_utc=OBSERVED,
        )


def test_exact_sept_xbrl_is_reporting_period_evidence_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_governance(monkeypatch)
    xml=_xbrl()
    snap=m.build_ownership_snapshot(
        master_raw=_master(), xbrl_raw=xml, observed_at_utc=OBSERVED
    )
    m.validate_ownership_snapshot(snap)
    assert snap["current_state"]=="SEPT_OFFICIAL_XBRL_SHARE_COUNTS_AND_GOVERNANCE_CORE_READY"
    assert snap["selected_report_date"]=="2026-09-30"
    assert snap["share_counts_as_of_report_date"]["fully_paid_shares"]==419_602_518
    assert snap["share_counts_as_of_report_date"]["fully_diluted_shares"]==422_070_138
    assert snap["reported_sept_fully_diluted_minus_basic_securities"]==2_467_620
    assert snap["governance_as_of_report_date"]["promoter_encumbrance"]["pledge"] is True
    assert snap["original_official_xbrl_sha256"]==hashlib.sha256(xml).hexdigest()
    assert snap["promoter_pledged_share_count_verified"] is False
    assert snap["secondary_vendor_reported_4900000_pledged_shares_adopted"] is False
    assert snap["as_of_2026_10_10_fully_diluted_shares_independently_proven"] is False
    assert snap["live_capital_allowed"] is False


def test_basic_qip_disagreement_is_not_silently_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_governance(monkeypatch)
    snap=m.build_ownership_snapshot(
        master_raw=_master(), xbrl_raw=_xbrl(basic=401_492_045),
        observed_at_utc=OBSERVED
    )
    assert snap["current_state"]=="SEPT_QUARTER_BASIC_SHARE_COUNT_DIFFERS_FROM_QIP"
    assert snap["as_of_2026_10_10_fully_diluted_shares_independently_proven"] is False


def test_wrong_context_date_or_symbol_blocks_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_governance(monkeypatch)
    snap=m.build_ownership_snapshot(
        master_raw=_master(), xbrl_raw=_xbrl(day="2026-06-30"),
        observed_at_utc=OBSERVED
    )
    assert snap["current_state"]=="OFFICIAL_XBRL_PARSE_OR_PERIOD_BLOCKED"
    assert snap["share_counts_as_of_report_date"] is None
    snap=m.build_ownership_snapshot(
        master_raw=_master(),
        xbrl_raw=_xbrl().replace(b"INOXGREEN</", b"FICTITIOUS</"),
        observed_at_utc=OBSERVED
    )
    assert snap["current_state"]=="OFFICIAL_XBRL_PARSE_OR_PERIOD_BLOCKED"


def test_missing_source_and_blocked_archive_are_not_filled() -> None:
    snap=m.build_ownership_snapshot(
        master_raw=None, xbrl_raw=None, observed_at_utc=OBSERVED,
        master_failure="HTTP_403_NO_BYPASS",
    )
    assert snap["current_state"]=="OFFICIAL_MASTER_UNAVAILABLE"
    assert snap["share_counts_as_of_report_date"] is None
    snap=m.build_ownership_snapshot(
        master_raw=_master(), xbrl_raw=None, observed_at_utc=OBSERVED,
        xbrl_failure="HTTP_403_NO_BYPASS",
    )
    assert snap["current_state"]=="SEPT_REPORT_OFFICIAL_XBRL_UNAVAILABLE"
    assert snap["original_official_master_receipt"]["master_original_sha256"]


def test_retained_raw_bytes_and_report_are_hash_verified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _mock_governance(monkeypatch)
    master=_master()
    xml=_xbrl()
    report=m.build_ownership_snapshot(
        master_raw=master,xbrl_raw=xml,observed_at_utc=OBSERVED
    )
    collector._retain(tmp_path,report,master,xml)
    assert json.loads((tmp_path/"sept-2026-source-observation-v1.json").read_text())==report
    assert (tmp_path/"raw/master/sha256"/(hashlib.sha256(master).hexdigest()+".json")).read_bytes()==master
    assert (tmp_path/"raw/xbrl/sha256"/(hashlib.sha256(xml).hexdigest()+".xml")).read_bytes()==xml
    collector._retain(tmp_path,report,master,xml)


def test_nse_source_acquisition_does_not_follow_unapproved_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Resp:
        url = "https://redirect.invalid/unrelated"
        content=_master()
    monkeypatch.setattr(collector,"master_session",lambda timeout: object())
    monkeypatch.setattr(collector,"fetch_master",lambda *args,**kwargs: Resp())
    snap,master,xml=collector._acquire(timeout=5)
    assert snap["current_state"]=="OFFICIAL_MASTER_UNAVAILABLE"
    assert master is None and xml is None
    assert "response URL changed" in snap["source_error_or_block_reason"]


def test_no_unverified_4_9m_pledge_can_be_promoted() -> None:
    snap=m.build_ownership_snapshot(
        master_raw=_master(), xbrl_raw=None, observed_at_utc=OBSERVED,
        xbrl_failure="SOURCE_NOT_YET_READY",
    )
    snap["secondary_vendor_reported_4900000_pledged_shares_adopted"]=True
    with pytest.raises(ValueError,match="cannot promote"):
        m.validate_ownership_snapshot(snap)
