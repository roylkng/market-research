from __future__ import annotations

from scripts import h019_numeric_extraction_audit as v2
from scripts import h019_numeric_extraction_audit_v3 as v3


def test_merged_profit_and_loss_heading_beats_note_page() -> None:
    statement = """
    STATEMENTOF PROFITAND LOSSFORTHEYEARENDED 31 MARCH 2018
    All amounts in Rs. (lakhs)
    Revenue From Operations 21 14,033.25 13,571.34
    Profit/(loss) for the period 1,200.00 900.00
    """
    note = """
    NOTES TO IND-AS FINANCIAL STATEMENTS FOR THE YEAR ENDED 31 MARCH 2018
    Revenue is recognised under the statement of profit and loss.
    Profit is measured under the following policy.
    """
    statement_score, _ = v3.statement_evidence(statement, "profit_loss", 10)
    note_score, _ = v3.statement_evidence(note, "profit_loss", 11)
    assert statement_score >= 5
    assert statement_score > note_score


def test_explicit_lakh_wording_variants_are_normalized() -> None:
    variants = (
        "All amounts in Rs. (lakhs), except otherwise stated",
        "All amounts in INR Lakhs unless otherwise stated",
        "All amounts are in rupees lakhs, unless otherwise stated",
        "Balance Sheet (` in Lacs)",
    )
    for text in variants:
        unit = v3.unit_scale(text)
        assert unit is not None
        assert unit["label"] == "LAKH"
        assert unit["scale_to_inr"] == 100000.0
        assert unit["source_evidence"]


def test_explicit_generic_balance_totals_are_section_scoped() -> None:
    page = """
    Balance Sheet as at March 31, 2017 (in Lacs)
    Equity and Liabilities
    Share Capital 2,203.76 2,203.76
    Reserves and Surplus 32,953.69 37,029.74
    Total 53,985.36 57,551.47
    Assets
    Non-Current Assets
    Total 22,194.36 25,834.62
    Current Assets
    Total 31,791.00 31,716.85
    Total 53,985.36 57,551.47
    """
    assets = v3.extract_line_fact(page, v2.FACT_PATTERNS["assets"])
    liabilities = v3.extract_line_fact(page, v2.FACT_PATTERNS["equity_and_liabilities"])
    assert assets is not None
    assert liabilities is not None
    assert assets["current"] == 53985.36
    assert liabilities["current"] == 53985.36
    assert assets["derivation"] == "EXPLICIT_FINAL_TOTAL_IN_ASSETS_SECTION"
    assert liabilities["derivation"] == "EXPLICIT_FINAL_TOTAL_BEFORE_ASSETS_SECTION"


def _xbrl(*, full_year: bool) -> bytes:
    full_start = "2017-04-01" if full_year else "2018-01-01"
    return f"""<?xml version='1.0' encoding='UTF-8'?>
    <xbrl xmlns:f='urn:test'>
      <f:DateOfStartOfFinancialYear contextRef='OneD'>2017-04-01</f:DateOfStartOfFinancialYear>
      <f:DateOfEndOfFinancialYear contextRef='OneD'>2018-03-31</f:DateOfEndOfFinancialYear>
      <f:DateOfStartOfReportingPeriod contextRef='FourD'>{full_start}</f:DateOfStartOfReportingPeriod>
      <f:DateOfEndOfReportingPeriod contextRef='FourD'>2018-03-31</f:DateOfEndOfReportingPeriod>
      <f:WhetherResultsAreAuditedOrUnaudited contextRef='FourD'>Audited</f:WhetherResultsAreAuditedOrUnaudited>
      <f:NatureOfReportStandaloneConsolidated contextRef='FourD'>Standalone</f:NatureOfReportStandaloneConsolidated>
      <f:RevenueFromOperations contextRef='FourD' unitRef='INR'>1000000</f:RevenueFromOperations>
      <f:ProfitLossForPeriodFromContinuingOperations contextRef='FourD' unitRef='INR'>100000</f:ProfitLossForPeriodFromContinuingOperations>
      <f:BasicEarningsLossPerShareFromContinuingOperations contextRef='FourD' unitRef='INRPerShare'>5</f:BasicEarningsLossPerShareFromContinuingOperations>
    </xbrl>""".encode()


def test_structured_facts_require_true_full_year_context() -> None:
    raw = _xbrl(full_year=True)
    facts = v3.structured_facts(raw)
    assert len(facts["revenue"]) == 1
    assert facts["revenue"][0]["context_ref"] == "FourD"
    diagnostics = v3._STRUCTURED_DIAGNOSTICS[v2.sha256(raw)]
    assert diagnostics["eligible_full_year_contexts"] == ["FourD"]


def test_quarter_only_context_is_not_compared_as_annual() -> None:
    raw = _xbrl(full_year=False)
    facts = v3.structured_facts(raw)
    assert facts["revenue"] == []
    assert facts["pat"] == []
    diagnostics = v3._STRUCTURED_DIAGNOSTICS[v2.sha256(raw)]
    assert diagnostics["eligible_full_year_contexts"] == []
    assert diagnostics["fact_status"]["revenue"] == "NO_COMPARABLE_FULL_YEAR_CONTEXT"


def test_compare_fact_does_not_choose_by_closeness() -> None:
    pdf = {"current_inr": 100.0}
    assert v3.compare_fact(pdf, [], eps=False) is None
    candidate = {
        "concept": "revenuefromoperations",
        "context_ref": "FourD",
        "value": 100.0,
        "concept_priority": 0,
    }
    comparison = v3.compare_fact(pdf, [candidate], eps=False)
    assert comparison is not None
    assert comparison["pass"] is True
    assert comparison["selection_method"] == "FULL_YEAR_CONTEXT_THEN_CONCEPT_PRIORITY"
