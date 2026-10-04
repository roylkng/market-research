from __future__ import annotations

import pytest

from marketlab.gf001_schema_audit import (
    GF001SchemaError,
    audit_shareholding_xbrl,
)


def _xml(
    *,
    promoter: str = "0.60",
    public: str = "0.40",
    mutual_fund: str = "0.08",
    dimensional_promoter: bool = False,
) -> bytes:
    dimension = (
        """
        <xbrldi:explicitMember dimension="in-shp:TestAxis">in-shp:Member</xbrldi:explicitMember>
        """
        if dimensional_promoter
        else ""
    )
    return f"""<?xml version="1.0"?>
<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:in-shp="http://www.sebi.gov.in/xbrl/shareholding">
 <xbrli:context id="PromoterAndPromoterGroup_ContextI">
  <xbrli:entity>
   <xbrli:identifier scheme="test">1</xbrli:identifier>
   <xbrli:segment>{dimension}</xbrli:segment>
  </xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
 </xbrli:context>
 <xbrli:context id="PublicShareholder_ContextI">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
 </xbrli:context>
 <xbrli:context id="MutualFundsOrUTI_ContextI">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
 </xbrli:context>
 <in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares
  contextRef="PromoterAndPromoterGroup_ContextI" unitRef="pure">{promoter}</in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
 <in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares
  contextRef="PublicShareholder_ContextI" unitRef="pure">{public}</in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
 <in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares
  contextRef="MutualFundsOrUTI_ContextI" unitRef="pure">{mutual_fund}</in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
 <in-shp:NumberOfSharesPledgedOrOtherwiseEncumbered
  contextRef="PromoterAndPromoterGroup_ContextI" unitRef="shares">100</in-shp:NumberOfSharesPledgedOrOtherwiseEncumbered>
</xbrli:xbrl>
""".encode()


def test_current_fraction_schema_finds_three_aggregate_families() -> None:
    result = audit_shareholding_xbrl(
        _xml(),
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )

    assert result["promoter_aggregate_ready"] is True
    assert result["public_aggregate_ready"] is True
    assert result["mutual_fund_aggregate_ready"] is True
    assert result["aggregate_scale_semantics"] == "FRACTION_0_TO_1"
    assert result["aggregate_families"]["PROMOTER_GROUP"]["numeric_value"] == pytest.approx(
        0.60
    )
    assert any(
        row["concept"] == "NumberOfSharesPledgedOrOtherwiseEncumbered"
        for row in result["keyword_facts"]
    )


def test_percentage_point_schema_is_detected_without_assuming_scale() -> None:
    result = audit_shareholding_xbrl(
        _xml(promoter="60", public="40", mutual_fund="8"),
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    assert result["aggregate_scale_semantics"] == "PERCENTAGE_POINTS_0_TO_100"


def test_dimensional_context_cannot_impersonate_aggregate_promoter_context() -> None:
    result = audit_shareholding_xbrl(
        _xml(dimensional_promoter=True),
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    assert result["promoter_aggregate_ready"] is False
    assert result["public_aggregate_ready"] is True


def test_malformed_xml_fails_closed() -> None:
    with pytest.raises(GF001SchemaError, match="invalid shareholding XML"):
        audit_shareholding_xbrl(
            b"<xbrl>",
            symbol="TEST",
            report_date="2026-06-30",
            source_url="https://nsearchives.nseindia.com/test.xml",
        )
