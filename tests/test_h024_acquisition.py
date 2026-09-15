from __future__ import annotations

from datetime import UTC, datetime

import pytest

from marketlab.h024_acquisition import (
    H024AcquisitionError,
    build_xbrl_evidence,
    canonical_hash,
    discover_sources,
    normalize_exchange_timestamp,
    source_from_discovery_row,
    trailing_discovery_window,
)


def _row(**overrides) -> dict:
    row = {
        "symbol": "AAA",
        "companyName": "AAA Limited",
        "regulation": "Regulation 7 (2)",
        "appId": "APP-1",
        "prevAppId": "",
        "typeOfSubmission": "Original",
        "revisionRemark": "",
        "broadcastDateTime": "2026-09-15T18:00:00",
        "exchdisstime": "2026-09-15T18:00:02",
        "xmlFileName": "https://nsearchives.nseindia.com/corporate/xbrl/a.xml",
        "ixbrl": "https://nsearchives.nseindia.com/corporate/xbrl/a_WEB.html",
    }
    row.update(overrides)
    return row


def _xml(*, revised: str = "false", mode: str = "Market Purchase") -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:co="http://example.test/co">
 <xbrli:context id="MainI"><xbrli:entity><xbrli:identifier scheme="test">AAA</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-09-15</xbrli:instant></xbrli:period></xbrli:context>
 <xbrli:context id="Disclosure1"><xbrli:entity><xbrli:identifier scheme="test">AAA</xbrli:identifier><xbrli:segment><xbrldi:typedMember dimension="co:ChangeInHoldingOfSecuritiesOfPromotersAxis"><co:DisclosureDomain>Disclosure1</co:DisclosureDomain></xbrldi:typedMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-09-15</xbrli:instant></xbrli:period></xbrli:context>
 <co:Symbol contextRef="MainI">AAA</co:Symbol>
 <co:DisclosureUnderRegulation contextRef="MainI">Regulation 7 (2)</co:DisclosureUnderRegulation>
 <co:RevisedFilling contextRef="MainI">{revised}</co:RevisedFilling>
 <co:DateOfFiling contextRef="MainI">2026-09-15</co:DateOfFiling>
 <co:CategoryOfPerson contextRef="Disclosure1">Promoter</co:CategoryOfPerson>
 <co:NameOfThePerson contextRef="Disclosure1">Example Insider</co:NameOfThePerson>
 <co:TypeOfInstrument contextRef="Disclosure1">Equity</co:TypeOfInstrument>
 <co:SecuritiesHeldPriorToAcquisitionOrDisposalNumberOfSecurity contextRef="Disclosure1" unitRef="shares">1000000</co:SecuritiesHeldPriorToAcquisitionOrDisposalNumberOfSecurity>
 <co:SecuritiesHeldPriorToAcquisitionOrDisposalPercentageOfShareholding contextRef="Disclosure1" unitRef="pure">0.40</co:SecuritiesHeldPriorToAcquisitionOrDisposalPercentageOfShareholding>
 <co:SecuritiesAcquiredOrDisposedNumberOfSecurity contextRef="Disclosure1" unitRef="shares">10000</co:SecuritiesAcquiredOrDisposedNumberOfSecurity>
 <co:SecuritiesAcquiredOrDisposedValueOfSecurity contextRef="Disclosure1" unitRef="INR">12500000</co:SecuritiesAcquiredOrDisposedValueOfSecurity>
 <co:SecuritiesAcquiredOrDisposedTransactionType contextRef="Disclosure1">Buy</co:SecuritiesAcquiredOrDisposedTransactionType>
 <co:SecuritiesHeldPostAcquistionOrDisposalNumberOfSecurity contextRef="Disclosure1" unitRef="shares">1010000</co:SecuritiesHeldPostAcquistionOrDisposalNumberOfSecurity>
 <co:SecuritiesHeldPostAcquistionOrDisposalPercentageOfShareholding contextRef="Disclosure1" unitRef="pure">0.41</co:SecuritiesHeldPostAcquistionOrDisposalPercentageOfShareholding>
 <co:DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyFromDate contextRef="Disclosure1">2026-09-14</co:DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyFromDate>
 <co:DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyToDate contextRef="Disclosure1">2026-09-14</co:DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyToDate>
 <co:ModeOfAcquisitionOrDisposal contextRef="Disclosure1">{mode}</co:ModeOfAcquisitionOrDisposal>
 <co:ExchangeOnWhichTheTradeWasExecuted contextRef="Disclosure1">NSE</co:ExchangeOnWhichTheTradeWasExecuted>
 <co:DateOfIntimationToCompany contextRef="Disclosure1">2026-09-15</co:DateOfIntimationToCompany>
</xbrli:xbrl>'''.encode()


def test_exchange_timestamp_is_interpreted_as_ist_and_normalized_to_utc() -> None:
    assert normalize_exchange_timestamp("2026-09-15T18:00:02") == "2026-09-15T12:30:02Z"
    assert normalize_exchange_timestamp("2026-09-15T12:30:02+00:00") == "2026-09-15T12:30:02Z"


def test_source_identity_excludes_mutable_discovery_row_hash() -> None:
    first = source_from_discovery_row(_row(extraMutableField="first"))
    second = source_from_discovery_row(_row(extraMutableField="second"))
    assert first is not None and second is not None
    assert first["source_id"] == second["source_id"]
    assert first["discovery_row_sha256"] != second["discovery_row_sha256"]


def test_discovery_filters_other_regulations_and_rejects_bad_archive_hosts() -> None:
    assert source_from_discovery_row(_row(regulation="Regulation 7 (3)")) is None
    with pytest.raises(H024AcquisitionError, match="approved NSE archive"):
        source_from_discovery_row(_row(xmlFileName="https://example.com/a.xml"))


def test_discover_sources_deduplicates_identical_rows_and_rejects_app_id_drift() -> None:
    row = _row()
    assert len(discover_sources([row, dict(row)])) == 1
    drifted = _row(exchdisstime="2026-09-15T18:01:00")
    with pytest.raises(H024AcquisitionError, match="conflicting source identity"):
        discover_sources([row, drifted])


def test_ready_xbrl_evidence_reports_direct_purchase_without_primary_weighting() -> None:
    source = source_from_discovery_row(_row())
    assert source is not None
    evidence = build_xbrl_evidence(source, _xml())
    assert evidence["status"] == "READY"
    assert evidence["direct_market_purchase_count"] == 1
    assert evidence["direct_market_purchase_value_inr"] == pytest.approx(12_500_000.0)
    assert evidence["direct_market_purchase_quantity"] == 10_000
    assert evidence["direct_market_purchase_actor_count"] == 1
    assert evidence["direct_market_purchase_ownership_delta_pp"] == pytest.approx(1.0)
    assert len(evidence["xbrl_sha256"]) == 64


def test_revision_metadata_must_agree_with_raw_xbrl() -> None:
    revision_source = source_from_discovery_row(_row(typeOfSubmission="Revision"))
    assert revision_source is not None
    blocked = build_xbrl_evidence(revision_source, _xml(revised="false"))
    assert blocked["status"] == "PARSE_BLOCKED"
    ready = build_xbrl_evidence(revision_source, _xml(revised="true"))
    assert ready["status"] == "READY"


def test_nonqualifying_raw_transaction_is_ready_but_has_zero_direct_purchases() -> None:
    source = source_from_discovery_row(_row())
    assert source is not None
    evidence = build_xbrl_evidence(source, _xml(mode="ESOP"))
    assert evidence["status"] == "READY"
    assert evidence["direct_market_purchase_count"] == 0


def test_trailing_discovery_window_uses_ist_calendar_date() -> None:
    start, end = trailing_discovery_window(
        now_utc=datetime(2026, 9, 15, 20, 0, tzinfo=UTC),
        lookback_days=7,
    )
    assert start.isoformat() == "2026-09-10"
    assert end.isoformat() == "2026-09-16"


def test_canonical_hash_rejects_nan() -> None:
    with pytest.raises(H024AcquisitionError, match="finite JSON"):
        canonical_hash({"bad": float("nan")})
