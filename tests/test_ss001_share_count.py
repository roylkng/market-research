from __future__ import annotations

import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_share_count import (
    ShareCountSourceError,
    build_share_count_panel,
    extract_share_counts,
)


def _xml(*, trust: bool, partly_paid: str = "false") -> bytes:
    if trust:
        public_count, public_pct = "300", "0.30"
        trust_context = '<xbrli:context id="EmployeeBenefitsTrusts_ContextI"/>'
        trust_facts = """
        <s:NumberOfShares contextRef="EmployeeBenefitsTrusts_ContextI">100</s:NumberOfShares>
        <s:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="EmployeeBenefitsTrusts_ContextI">0.10</s:ShareholdingAsAPercentageOfTotalNumberOfShares>
        """
    else:
        public_count, public_pct = "400", "0.40"
        trust_context, trust_facts = "", ""

    return f"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
             xmlns:s="http://nse.example/shareholding">
  <xbrli:context id="ShareholdingOfPromoterAndPromoterGroup_ContextI"/>
  <xbrli:context id="PublicShareholding_ContextI"/>
  {trust_context}
  <xbrli:context id="MainI"/>
  <s:NumberOfShares contextRef="ShareholdingOfPromoterAndPromoterGroup_ContextI">600</s:NumberOfShares>
  <s:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="ShareholdingOfPromoterAndPromoterGroup_ContextI">0.60</s:ShareholdingAsAPercentageOfTotalNumberOfShares>
  <s:NumberOfShares contextRef="PublicShareholding_ContextI">{public_count}</s:NumberOfShares>
  <s:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="PublicShareholding_ContextI">{public_pct}</s:ShareholdingAsAPercentageOfTotalNumberOfShares>
  {trust_facts}
  <s:WhetherTheListedEntityHasIssuedAnyPartlyPaidUpShares contextRef="MainI">{partly_paid}</s:WhetherTheListedEntityHasIssuedAnyPartlyPaidUpShares>
</xbrli:xbrl>""".encode()


def _parse(raw: bytes) -> dict:
    return extract_share_counts(raw, expected_sha256=hashlib.sha256(raw).hexdigest())


def test_basic_promoter_public_count_is_exact_and_capitalization_candidate() -> None:
    parsed = _parse(_xml(trust=False))
    assert parsed["reported_share_count"] == 1000
    assert parsed["capitalization_source_eligible"] is True
    assert parsed["employee_trust_category_state"] == "STRUCTURALLY_ABSENT"


def test_employee_trust_counted_once_and_partly_paid_blocks_market_cap() -> None:
    parsed = _parse(_xml(trust=True, partly_paid="true"))
    assert parsed["reported_share_count"] == 1000
    assert parsed["capitalization_source_eligible"] is False
    assert parsed["partly_paid_flag"] == "TRUE"
    assert parsed["employee_trust_category_state"] == "PRESENT"


def test_raw_sha_mismatch_fails_closed() -> None:
    with pytest.raises(ShareCountSourceError, match="SHA-256 mismatch"):
        extract_share_counts(_xml(trust=False), expected_sha256="0" * 64)


def test_inconsistent_count_vs_fraction_is_not_imputed() -> None:
    raw = _xml(trust=False).replace(b">0.40<", b">0.30<")
    with pytest.raises(ShareCountSourceError, match="sum-to-one"):
        _parse(raw)


def _gf001_source() -> dict:
    rows = []
    for index in range(2319):
        ready = index < 2050
        rows.append(
            {
                "symbol": f"S{index:04d}",
                "source_state": "READY" if ready else "NO_STANDARD_QUARTER",
                "latest": (
                    {
                        "raw_sha256": f"{index:064x}",
                        "report_date": "2026-06-30",
                        "source_url": f"https://nsearchives.nseindia.com/x/{index}.xml",
                    }
                    if ready
                    else None
                ),
            }
        )
    return {
        "panel_id": "GF001-D002-v1",
        "panel_sha256": (
            "dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7"
        ),
        "identity_count": 2319,
        "ready_latest_source_count": 2050,
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_full_panel_preserves_2319_source_and_research_only_flags() -> None:
    source = _gf001_source()
    extracted = [
        {
            "symbol": f"S{index:04d}",
            "status": "SHARE_COUNT_READY",
            "reported_share_count": 10_000 + index,
            "aggregate_fraction_sum": 1.0,
            "employee_trust_category_state": "STRUCTURALLY_ABSENT",
            "partly_paid_flag": "FALSE",
            "capitalization_source_eligible": True,
            "raw_sha256": f"{index:064x}",
            "error": None,
        }
        for index in range(2050)
    ]
    result = build_share_count_panel(
        gf001_panel=source,
        extracted_rows=extracted,
        captured_at_utc="2026-10-08T02:30:00Z",
    )
    assert result["share_count_ready_count"] == 2050
    assert result["capitalization_source_eligible_count"] == 2050
    assert result["feasibility_pass"] is True
    assert len(result["rows"]) == 2319
    assert result["model_fitted"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False


def test_missing_source_entry_fails_accounting() -> None:
    with pytest.raises(AlphaContractError, match="extracted/source"):
        build_share_count_panel(
            gf001_panel=_gf001_source(),
            extracted_rows=[],
            captured_at_utc="2026-10-08T02:30:00Z",
        )

def test_missing_latest_raw_is_explicit_not_implicitly_ready() -> None:
    source = _gf001_source()
    source["rows"][10]["latest"] = None
    extracted = []
    for index in range(2050):
        if index == 10:
            extracted.append({
                "symbol": f"S{index:04d}",
                "status": "RAW_UNAVAILABLE",
                "raw_sha256": None,
                "error": "LATEST_RAW_SOURCE_NOT_READY",
            })
        else:
            extracted.append({
                "symbol": f"S{index:04d}",
                "status": "SHARE_COUNT_READY",
                "reported_share_count": 100_000,
                "aggregate_fraction_sum": 1.0,
                "partly_paid_flag": "FALSE",
                "capitalization_source_eligible": True,
                "raw_sha256": f"{index:064x}",
                "error": None,
            })
    result = build_share_count_panel(
        gf001_panel=source,
        extracted_rows=extracted,
        captured_at_utc="2026-10-08T03:00:00Z",
    )
    assert result["share_count_ready_count"] == 2049
    assert result["status_counts"]["RAW_UNAVAILABLE"] == 1
    assert result["feasibility_pass"] is True
