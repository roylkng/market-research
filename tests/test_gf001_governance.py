from __future__ import annotations

import pytest

from marketlab.gf001_governance import (
    parse_current_governance_xbrl,
)


def _xbrl(*, include_mf: bool = True, pledge: str = "false") -> bytes:
    mf_context = """
    <xbrli:context id="MutualFundsOrUTI_ContextI">
      <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier>
        <xbrli:segment>
          <xbrldi:explicitMember dimension="in-capmkt:CategoryOfShareholdersAxis">
            in-capmkt:MutualFundsOrUTIMember
          </xbrldi:explicitMember>
        </xbrli:segment>
      </xbrli:entity>
      <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
    </xbrli:context>
    """ if include_mf else ""
    mf_fact = (
        '<in-capmkt:ShareholdingAsAPercentageOfTotalNumberOfShares '
        'contextRef="MutualFundsOrUTI_ContextI">0.12</in-capmkt:ShareholdingAsAPercentageOfTotalNumberOfShares>'
        if include_mf else ""
    )
    return f"""<?xml version="1.0"?>
    <xbrli:xbrl
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
      xmlns:in-capmkt="http://www.sebi.gov.in/xbrl">
      <xbrli:context id="ShareholdingOfPromoterAndPromoterGroup_ContextI">
        <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier>
          <xbrli:segment>
            <xbrldi:explicitMember dimension="in-capmkt:CategoryOfShareholdersAxis">
              in-capmkt:ShareholdingOfPromoterAndPromoterGroupMember
            </xbrldi:explicitMember>
          </xbrli:segment>
        </xbrli:entity>
        <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
      </xbrli:context>
      <xbrli:context id="PublicShareholding_ContextI">
        <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier>
          <xbrli:segment>
            <xbrldi:explicitMember dimension="in-capmkt:CategoryOfShareholdersAxis">
              in-capmkt:PublicShareholdingMember
            </xbrldi:explicitMember>
          </xbrli:segment>
        </xbrli:entity>
        <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
      </xbrli:context>
      {mf_context}
      <xbrli:context id="MainI">
        <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
      </xbrli:context>

      <in-capmkt:ShareholdingAsAPercentageOfTotalNumberOfShares
        contextRef="ShareholdingOfPromoterAndPromoterGroup_ContextI">0.55</in-capmkt:ShareholdingAsAPercentageOfTotalNumberOfShares>
      <in-capmkt:ShareholdingAsAPercentageOfTotalNumberOfShares
        contextRef="PublicShareholding_ContextI">0.45</in-capmkt:ShareholdingAsAPercentageOfTotalNumberOfShares>
      {mf_fact}
      <in-capmkt:WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup
        contextRef="MainI">{pledge}</in-capmkt:WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup>
      <in-capmkt:WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup
        contextRef="MainI">false</in-capmkt:WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup>
      <in-capmkt:WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup
        contextRef="MainI">false</in-capmkt:WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup>
    </xbrli:xbrl>
    """.encode()


def test_current_governance_parser_extracts_exact_core_semantics() -> None:
    result = parse_current_governance_xbrl(
        _xbrl(pledge="true"),
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    assert result["parser_status"] == "CORE_READY"
    assert result["promoter_percentage"] == pytest.approx(55.0)
    assert result["public_percentage"] == pytest.approx(45.0)
    assert result["mutual_fund_state"] == "READY"
    assert result["mutual_fund_percentage"] == pytest.approx(12.0)
    assert result["promoter_encumbrance"]["pledge"] is True
    assert result["promoter_encumbrance"]["non_disposal_undertaking"] is False
    assert result["promoter_encumbrance"]["other_encumbrance"] is False


def test_mutual_fund_structural_absence_is_not_zero_or_core_failure() -> None:
    result = parse_current_governance_xbrl(
        _xbrl(include_mf=False),
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    assert result["parser_status"] == "CORE_READY"
    assert result["mutual_fund_state"] == "CATEGORY_CONTEXT_ABSENT"
    assert result["mutual_fund_percentage"] is None


def test_percentage_point_scale_fails_closed() -> None:
    raw = _xbrl().replace(b">0.55<", b">55<").replace(b">0.45<", b">45<")
    result = parse_current_governance_xbrl(
        raw,
        symbol="TEST",
        report_date="2026-06-30",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    assert result["parser_status"] == "CORE_PARSE_FAILED"
    assert result["promoter_state"] == "AMBIGUOUS_OR_INVALID"
