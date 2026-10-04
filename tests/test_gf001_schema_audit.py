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
    mutual_fund: str | None = "0.08",
    wrong_promoter_member: bool = False,
    pledged: str = "false",
) -> bytes:
    promoter_member = (
        "WrongPromoterMember"
        if wrong_promoter_member
        else "ShareholdingOfPromoterAndPromoterGroupMember"
    )
    mutual_context = ""
    mutual_fact = ""
    if mutual_fund is not None:
        mutual_context = """
 <xbrli:context id="MutualFundsOrUTI_ContextI">
  <xbrli:entity>
   <xbrli:identifier scheme="test">1</xbrli:identifier>
   <xbrli:segment>
    <xbrldi:explicitMember dimension="in-shp:CategoryOfShareholdersAxis">in-shp:MutualFundsOrUTIMember</xbrldi:explicitMember>
   </xbrli:segment>
  </xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
 </xbrli:context>
"""
        mutual_fact = f"""
 <in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares
  contextRef="MutualFundsOrUTI_ContextI" unitRef="pure">{mutual_fund}</in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
"""

    return f"""<?xml version="1.0"?>
<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:in-shp="http://www.sebi.gov.in/xbrl/shareholding">
 <xbrli:context id="MainI">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
 </xbrli:context>
 <xbrli:context id="ShareholdingOfPromoterAndPromoterGroup_ContextI">
  <xbrli:entity>
   <xbrli:identifier scheme="test">1</xbrli:identifier>
   <xbrli:segment>
    <xbrldi:explicitMember dimension="in-shp:CategoryOfShareholdersAxis">in-shp:{promoter_member}</xbrldi:explicitMember>
   </xbrli:segment>
  </xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
 </xbrli:context>
 <xbrli:context id="PublicShareholding_ContextI">
  <xbrli:entity>
   <xbrli:identifier scheme="test">1</xbrli:identifier>
   <xbrli:segment>
    <xbrldi:explicitMember dimension="in-shp:CategoryOfShareholdersAxis">in-shp:PublicShareholdingMember</xbrldi:explicitMember>
   </xbrli:segment>
  </xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
 </xbrli:context>
{mutual_context}
 <in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares
  contextRef="ShareholdingOfPromoterAndPromoterGroup_ContextI" unitRef="pure">{promoter}</in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
 <in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares
  contextRef="PublicShareholding_ContextI" unitRef="pure">{public}</in-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
{mutual_fact}
 <in-shp:WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup
  contextRef="MainI">{pledged}</in-shp:WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup>
 <in-shp:WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup
  contextRef="MainI">false</in-shp:WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup>
 <in-shp:WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup
  contextRef="MainI">false</in-shp:WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup>
</xbrli:xbrl>
""".encode()


def test_current_fraction_schema_finds_exact_dimensional_aggregates() -> None:
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
    assert result["promoter_encumbrance_ready"] is True
    assert all(
        value is False
        for value in result["promoter_encumbrance_flags"].values()
    )


def test_percentage_point_schema_is_detected_without_assuming_scale() -> None:
    result = audit_shareholding_xbrl(
        _xml(promoter="60", public="40", mutual_fund="8"),
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    assert result["aggregate_scale_semantics"] == "PERCENTAGE_POINTS_0_TO_100"


def test_wrong_dimension_member_cannot_impersonate_promoter_aggregate() -> None:
    result = audit_shareholding_xbrl(
        _xml(wrong_promoter_member=True),
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    assert result["promoter_aggregate_ready"] is False
    assert result["public_aggregate_ready"] is True
    assert result["aggregate_scale_semantics"] == "UNRESOLVED"


def test_absent_mutual_fund_context_is_not_imputed_to_zero() -> None:
    result = audit_shareholding_xbrl(
        _xml(mutual_fund=None),
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    assert result["mutual_fund_aggregate_ready"] is False
    assert result["mutual_fund_aggregate_state"] == "CATEGORY_CONTEXT_ABSENT"
    assert result["aggregate_families"]["MUTUAL_FUND_UTI"] is None


def test_promoter_pledge_boolean_is_retained_as_source_fact() -> None:
    result = audit_shareholding_xbrl(
        _xml(pledged="true"),
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    assert result["promoter_encumbrance_ready"] is True
    assert result["promoter_encumbrance_flags"][
        "WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup"
    ] is True


def test_malformed_xml_fails_closed() -> None:
    with pytest.raises(GF001SchemaError, match="invalid shareholding XML"):
        audit_shareholding_xbrl(
            b"<xbrl>",
            symbol="TEST",
            report_date="2026-06-30",
            source_url="https://nsearchives.nseindia.com/test.xml",
        )
