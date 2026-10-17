"""L001 P006 cash component tests: reject malformed XBRL, never create buy ranks."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p006_cash_anomalies import _extract_original_cash_tags

XML = (
    b'<xbrl xmlns:t="http://source.test/taxonomy">'
    b'<t:CashFlowsFromUsedInOperatingActivities contextRef="FourD" unitRef="INR">'
    b'45929651000</t:CashFlowsFromUsedInOperatingActivities>'
    b'<t:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities '
    b'contextRef="FourD" unitRef="INR">3260076000'
    b'</t:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities>'
    b'<t:AdjustmentsForDecreaseIncreaseInTradeReceivablesNoncurrent '
    b'contextRef="FourD" unitRef="INR">41461024000'
    b'</t:AdjustmentsForDecreaseIncreaseInTradeReceivablesNoncurrent>'
    b'<t:AdjustmentsForDecreaseIncreaseInTradeReceivablesCurrent '
    b'contextRef="FourD" unitRef="INR">0'
    b'</t:AdjustmentsForDecreaseIncreaseInTradeReceivablesCurrent>'
    b'<t:CashFlowsFromUsedInInvestingActivities contextRef="FourD" unitRef="INR">'
    b'-665200000</t:CashFlowsFromUsedInInvestingActivities>'
    b'</xbrl>'
)


def test_extracts_exact_pnc_xbrl_numbers_not_owner_cash():
    data = _extract_original_cash_tags(ET.fromstring(XML))
    assert data["cfo_reported"] == 4592.9651
    assert data["ppe_cash_purchase"] == 326.0076
    assert data["trade_receivables_noncurrent_change"] == 4146.1024
    assert data["trade_receivables_current_change"] == 0.0
    assert data["pre_tax_operating_cash"] is None


def test_noncurrent_receivable_must_have_exact_four_d_context():
    mutated = XML.replace(b"contextRef=\"FourD\"", b"contextRef=\"OneD\"")
    data = _extract_original_cash_tags(ET.fromstring(mutated))
    assert data["cfo_reported"] is None
    assert data["trade_receivables_noncurrent_change"] is None


def test_non_inr_unit_is_not_treated_as_inr():
    mutated = XML.replace(b'unitRef="INR"', b'unitRef="USD"')
    data = _extract_original_cash_tags(ET.fromstring(mutated))
    assert all(amount is None for amount in data.values())


def test_conflicting_xbrl_cash_tags_are_rejected():
    mutated = XML.replace(
        b'</xbrl>',
        b'<t:CashFlowsFromUsedInOperatingActivities xmlns:t="http://source.test/taxonomy" '
        b'contextRef="FourD" unitRef="INR">10000'
        b'</t:CashFlowsFromUsedInOperatingActivities></xbrl>',
    )
    with pytest.raises(AlphaContractError, match="conflicting"):
        _extract_original_cash_tags(ET.fromstring(mutated))


def test_non_numeric_original_xbrl_rejected():
    mutated = XML.replace(b'45929651000', b'NO_NUMBER')
    with pytest.raises(AlphaContractError, match="not numeric"):
        _extract_original_cash_tags(ET.fromstring(mutated))
