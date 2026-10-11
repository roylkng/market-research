from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_reg31_check import (
    MASTER_URL,
    QIP_BASIC_ISSUED_SHARES,
    build_post_qip_shareholding_evidence,
    choose_post_qip_filing,
    require_independently_verified_enterprise_value,
)
from scripts.acquire_hg007_post_qip_reg31 import _get_exact, write_source_receipt

CUTOFF = "2026-10-12T02:00:00Z"
OFFICIAL_XML = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "inoxgreen_shareholding_29092026.xml"
)


def _master(
    *,
    report_date: str = "29-Sep-2026",
    broadcast: str = "30-Sep-2026 12:00:00",
    url: str = OFFICIAL_XML,
) -> bytes:
    return json.dumps([{
        "symbol":"INOXGREEN",
        "date":report_date,
        "broadcastDate":broadcast,
        "recordId":"REG31-INOXGREEN-SEP-2026",
        "xbrl":url,
    }]).encode("utf-8")


def _xml(*, paid: int = QIP_BASIC_ISSUED_SHARES,
         fd: int = QIP_BASIC_ISSUED_SHARES + 2_467_620) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<root xmlns:x="urn:shares">
  <x:Symbol>INOXGREEN</x:Symbol>
  <x:NumberOfFullyPaidUpEquityShares contextRef="ShareholdingPattern_ContextI" unitRef="shares">{paid}</x:NumberOfFullyPaidUpEquityShares>
  <x:NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities contextRef="ShareholdingPattern_ContextI" unitRef="shares">{fd}</x:NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities>
</root>""".encode()


def _audit(master: bytes | None, xml: bytes | None,
           *, master_status: str = "OK", xml_status: str = "OK") -> dict:
    return build_post_qip_shareholding_evidence(
        master_raw=master, xbrl_raw=xml,
        master_status=master_status,
        xbrl_status=xml_status,
        observed_at_utc=CUTOFF,
        source_message="ORIGINAL_TEST_FIXTURE_ONLY",
    )


def test_official_post_qip_special_date_can_be_selected_even_if_not_quarter_end() -> None:
    row = choose_post_qip_filing(_master(), observed_at_utc=CUTOFF)
    assert row is not None
    assert row["report_date"] == "2026-09-29"
    assert row["record_id"] == "REG31-INOXGREEN-SEP-2026"
    assert row["xbrl_url"] == OFFICIAL_XML
    assert len(row["original_master_row_sha256"]) == 64


def test_fully_paid_and_diluted_source_counts_are_distinct_and_no_capital() -> None:
    report = _audit(_master(), _xml())
    assert report["evidence_status"] == "ORIGINAL_REPORTED_POST_QIP_SHARE_COUNTS_CAPTURED"
    assert report["reported_share_counts"]["fully_paid_shares"] == 419_602_518
    assert report["reported_share_counts"]["fully_diluted_shares"] == 422_070_138
    assert report["reported_dilution_instruments_increment_not_necessarily_esop"] == 2_467_620
    assert report["reported_promoter_and_pledge_context"] is not None
    assert report["reported_promoter_and_pledge_context"]["parser_status"] == "CORE_PARSE_FAILED"
    assert report["promoter_pledge_independently_document_reviewed"] is False
    for key in (
        "source_is_current_as_of_future_investment_decision",
        "full_post_qip_equity_market_cap_approved",
        "cash_adjusted_enterprise_value_approved",
        "equity_expected_return_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert report[key] is False
    with pytest.raises(ValueError, match="net cash basis still blocked"):
        require_independently_verified_enterprise_value(report)


def test_older_march_reg31_or_future_unpublished_revision_is_never_current() -> None:
    master = _master(report_date="31-Mar-2026")
    assert choose_post_qip_filing(master, observed_at_utc=CUTOFF) is None
    report = _audit(master, None, xml_status="NOT_ATTEMPTED")
    assert report["evidence_status"] == "NO_ELIGIBLE_POST_QIP_ORIGINAL_REG31_FILING"
    assert report["reported_share_counts"] is None

    future = _master(broadcast="12-Oct-2026 15:00:00")
    assert choose_post_qip_filing(future, observed_at_utc=CUTOFF) is None
    report = _audit(future, None, xml_status="NOT_ATTEMPTED")
    assert report["evidence_status"] == "NO_ELIGIBLE_POST_QIP_ORIGINAL_REG31_FILING"


def test_stale_post_qip_filing_sharecount_can_never_override_completed_qip() -> None:
    doc = _xml(paid=401_492_045, fd=403_959_665)
    result = _audit(_master(), doc)
    assert result["evidence_status"] == "BLOCKED_ORIGINAL_SHARE_COUNT_BELOW_COMPLETED_QIP"
    assert result["reported_share_counts"]["fully_paid_shares"] == 401_492_045
    assert result["cash_adjusted_enterprise_value_approved"] is False


def test_unknown_xml_values_are_retained_but_never_inferred() -> None:
    result = _audit(_master(), b"<html>blocked</html>")
    assert result["evidence_status"] == "BLOCKED_ORIGINAL_XML_SHARE_COUNTS_UNPARSABLE"
    assert result["reported_share_counts"] is None
    assert result["xbrl_original_raw_sha256"] == hashlib.sha256(
        b"<html>blocked</html>"
    ).hexdigest()


def test_ambiguous_broadcast_and_wrong_original_host_fail_closed() -> None:
    with pytest.raises(ValueError, match="XBRL URL invalid"):
        choose_post_qip_filing(
            _master(url="https://nsearchives.nseindia.com.evil.invalid/x.xml"),
            observed_at_utc=CUTOFF,
        )
    one = json.loads(_master())[0]
    other = deepcopy(one)
    other["recordId"] = "OTHER-REVISION"
    with pytest.raises(ValueError, match="ambiguous"):
        choose_post_qip_filing(
            json.dumps([one,other]).encode(), observed_at_utc=CUTOFF
        )
    with pytest.raises(ValueError, match="recordId duplicated"):
        choose_post_qip_filing(json.dumps([one,one]).encode(), observed_at_utc=CUTOFF)


def test_missing_official_source_is_not_empty_success() -> None:
    record = _audit(
        None, None, master_status="BLOCKED", xml_status="NOT_ATTEMPTED"
    )
    assert record["master_source_state"] == "BLOCKED"
    assert record["evidence_status"] == "MASTER_SOURCE_BLOCKED"
    assert record["selected_original_filing"] is None
    with pytest.raises(ValueError, match="original bytes inconsistent"):
        _audit(None, None, master_status="OK", xml_status="NOT_ATTEMPTED")


def test_raw_nse_source_retention_is_sha_verified(tmp_path: Path) -> None:
    master, xml = _master(), _xml()
    record = _audit(master,xml)
    write_source_receipt(tmp_path,record,master,xml)
    assert json.loads((tmp_path/"observation-v1.json").read_text()) == record
    assert len(list((tmp_path/"raw"/"sha256").iterdir())) == 2
    write_source_receipt(tmp_path,record,master,xml)
    with pytest.raises(ValueError, match="digest mismatch"):
        write_source_receipt(tmp_path,record,master,xml+b"altered")


def test_redirect_and_403_are_not_retried_or_bypassed() -> None:
    calls = []

    class FakeResp:
        status_code=403
        content=b"blocked"
        url=MASTER_URL

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append((url,kwargs))
            return FakeResp()

    raw,status,reason = _get_exact(
        FakeSession(), MASTER_URL,
        params={"index":"equities","symbol":"INOXGREEN"},max_bytes=10000,
    )
    assert raw is None
    assert status == "BLOCKED"
    assert "NO_ACCESS_BYPASS" in reason
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
