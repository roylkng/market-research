"""P007 fiscal Q1 earnings component admission and tampering tests."""

from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p007_earnings_components import original_income_values


def source_xml(income: str = "1744200000", pbt: str = "3261300000") -> bytes:
    return (
        '<xbrl xmlns:x="https://nse.example/taxonomy">'
        '<x:OtherIncome contextRef="OneD" unitRef="INR">'+income+'</x:OtherIncome>'
        '<x:ProfitBeforeTax contextRef="OneD" unitRef="INR">'+pbt+'</x:ProfitBeforeTax>'
        '<x:RevenueFromOperations contextRef="OneD" unitRef="INR">'
        '10912000000</x:RevenueFromOperations>'
        '<x:ProfitLossForPeriod contextRef="OneD" unitRef="INR">'
        '2664000000</x:ProfitLossForPeriod>'
        '</xbrl>'
    ).encode()


def test_original_maharashtra_seamless_other_income_ratio_is_explicit():
    facts = original_income_values(source_xml())
    assert facts["other_income"] == 174.42
    assert facts["profit_before_tax"] == 326.13
    assert round(100 * facts["other_income"] / facts["profit_before_tax"], 1) == 53.5
    assert facts["exceptional_items_before_tax"] is None


def test_wrong_context_and_unit_rejected_as_missing_not_zero():
    changed = source_xml().replace(b'contextRef="OneD"', b'contextRef="TwoD"')
    facts = original_income_values(changed)
    assert facts["other_income"] is None
    assert facts["profit_before_tax"] is None
    changed = source_xml().replace(b'unitRef="INR"', b'unitRef="USD"')
    assert original_income_values(changed)["revenue_operations"] is None


def test_conflicting_original_fiscal_quarter_fact_fails():
    raw = source_xml().replace(
        b"</xbrl>",
        b'<x:OtherIncome xmlns:x="https://nse.example/taxonomy" '
        b'contextRef="OneD" unitRef="INR">10000000</x:OtherIncome></xbrl>',
    )
    with pytest.raises(AlphaContractError, match="conflicting"):
        original_income_values(raw)


def test_nonfinite_original_number_rejected():
    with pytest.raises(AlphaContractError, match="nonfinite"):
        original_income_values(source_xml(income="NaN"))


def test_invalid_xbrl_document_rejected():
    with pytest.raises(AlphaContractError, match="XBRL is invalid"):
        original_income_values(b"<no-document")
