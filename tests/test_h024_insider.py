from __future__ import annotations

import pytest

from marketlab.h024_insider import H024InsiderError, parse_pit_xml, parser_contract


def _xml(
    *,
    category: str = "Promoter",
    mode: str = "Market Purchase",
    transaction_type: str = "Buy",
    instrument: str = "Equity",
    value: str = "122655032",
    value_unit: str = "INR",
    prior_fraction: str = "0.4421",
    post_fraction: str = "0.4422",
    extra_axis: bool = False,
) -> bytes:
    extra = (
        '<xbrldi:typedMember dimension="co:UnexpectedAxis">'
        '<co:UnexpectedDomain>X</co:UnexpectedDomain>'
        "</xbrldi:typedMember>"
        if extra_axis
        else ""
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:co="http://example.test/co">
 <xbrli:context id="MainI"><xbrli:entity><xbrli:identifier scheme="test">AAA</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-09-01</xbrli:instant></xbrli:period></xbrli:context>
 <xbrli:context id="Disclosure1"><xbrli:entity><xbrli:identifier scheme="test">AAA</xbrli:identifier><xbrli:segment><xbrldi:typedMember dimension="co:ChangeInHoldingOfSecuritiesOfPromotersAxis"><co:DisclosureDomain>Disclosure1</co:DisclosureDomain></xbrldi:typedMember>{extra}</xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-09-01</xbrli:instant></xbrli:period></xbrli:context>
 <co:Symbol contextRef="MainI">AAA</co:Symbol>
 <co:DisclosureUnderRegulation contextRef="MainI">Regulation 7 (2)</co:DisclosureUnderRegulation>
 <co:RevisedFilling contextRef="MainI">false</co:RevisedFilling>
 <co:DateOfFiling contextRef="MainI">2026-09-01</co:DateOfFiling>
 <co:CategoryOfPerson contextRef="Disclosure1">{category}</co:CategoryOfPerson>
 <co:NameOfThePerson contextRef="Disclosure1">Example Insider</co:NameOfThePerson>
 <co:TypeOfInstrument contextRef="Disclosure1">{instrument}</co:TypeOfInstrument>
 <co:SecuritiesHeldPriorToAcquisitionOrDisposalNumberOfSecurity contextRef="Disclosure1" unitRef="shares">1000000</co:SecuritiesHeldPriorToAcquisitionOrDisposalNumberOfSecurity>
 <co:SecuritiesHeldPriorToAcquisitionOrDisposalPercentageOfShareholding contextRef="Disclosure1" unitRef="pure">{prior_fraction}</co:SecuritiesHeldPriorToAcquisitionOrDisposalPercentageOfShareholding>
 <co:SecuritiesAcquiredOrDisposedNumberOfSecurity contextRef="Disclosure1" unitRef="shares">10000</co:SecuritiesAcquiredOrDisposedNumberOfSecurity>
 <co:SecuritiesAcquiredOrDisposedValueOfSecurity contextRef="Disclosure1" unitRef="{value_unit}">{value}</co:SecuritiesAcquiredOrDisposedValueOfSecurity>
 <co:SecuritiesAcquiredOrDisposedTransactionType contextRef="Disclosure1">{transaction_type}</co:SecuritiesAcquiredOrDisposedTransactionType>
 <co:SecuritiesHeldPostAcquistionOrDisposalNumberOfSecurity contextRef="Disclosure1" unitRef="shares">1010000</co:SecuritiesHeldPostAcquistionOrDisposalNumberOfSecurity>
 <co:SecuritiesHeldPostAcquistionOrDisposalPercentageOfShareholding contextRef="Disclosure1" unitRef="pure">{post_fraction}</co:SecuritiesHeldPostAcquistionOrDisposalPercentageOfShareholding>
 <co:DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyFromDate contextRef="Disclosure1">2026-08-31</co:DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyFromDate>
 <co:DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyToDate contextRef="Disclosure1">2026-08-31</co:DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyToDate>
 <co:ModeOfAcquisitionOrDisposal contextRef="Disclosure1">{mode}</co:ModeOfAcquisitionOrDisposal>
 <co:ExchangeOnWhichTheTradeWasExecuted contextRef="Disclosure1">NSE</co:ExchangeOnWhichTheTradeWasExecuted>
 <co:DateOfIntimationToCompany contextRef="Disclosure1">2026-09-01</co:DateOfIntimationToCompany>
</xbrli:xbrl>'''.encode()


def test_strict_parser_recovers_direct_market_purchase_semantics() -> None:
    parsed = parse_pit_xml(_xml(), expected_symbol="AAA")
    assert parsed.symbol == "AAA"
    assert parsed.regulation == "Regulation 7 (2)"
    assert parsed.revised_filing is False
    assert parsed.date_of_filing == "2026-09-01"
    assert len(parsed.transactions) == 1
    transaction = parsed.transactions[0]
    assert transaction.category == "Promoter"
    assert transaction.person_name == "Example Insider"
    assert transaction.instrument == "Equity"
    assert transaction.transaction_type == "Buy"
    assert transaction.acquisition_mode == "Market Purchase"
    assert transaction.transaction_quantity == 10_000
    assert transaction.transaction_value_inr == pytest.approx(122_655_032.0)
    assert transaction.prior_ownership_fraction == pytest.approx(0.4421)
    assert transaction.post_ownership_fraction == pytest.approx(0.4422)
    assert transaction.prior_ownership_percentage == pytest.approx(44.21)
    assert transaction.post_ownership_percentage == pytest.approx(44.22)
    assert transaction.ownership_delta_pp == pytest.approx(0.01)
    assert transaction.is_direct_market_purchase
    assert parsed.direct_market_purchase_value_inr == pytest.approx(122_655_032.0)


def test_non_discretionary_modes_and_non_direct_categories_do_not_qualify() -> None:
    assert not parse_pit_xml(_xml(mode="ESOP")).transactions[0].is_direct_market_purchase
    assert not parse_pit_xml(_xml(category="Designated Person")).transactions[0].is_direct_market_purchase
    assert not parse_pit_xml(_xml(transaction_type="Sell")).transactions[0].is_direct_market_purchase
    assert not parse_pit_xml(_xml(instrument="Warrants")).transactions[0].is_direct_market_purchase


def test_parser_rejects_unit_and_fraction_semantic_drift() -> None:
    with pytest.raises(H024InsiderError, match="unit changed"):
        parse_pit_xml(_xml(value_unit="shares"))
    with pytest.raises(H024InsiderError, match="fraction out of range"):
        parse_pit_xml(_xml(post_fraction="1.1"))


def test_parser_rejects_wrong_symbol_and_extra_disclosure_axis() -> None:
    with pytest.raises(H024InsiderError, match="symbol mismatch"):
        parse_pit_xml(_xml(), expected_symbol="BBB")
    with pytest.raises(H024InsiderError, match="unexpected additional typed axes"):
        parse_pit_xml(_xml(extra_axis=True))


def test_parser_rejects_missing_required_transaction_fact() -> None:
    raw = _xml().replace(
        b'<co:ModeOfAcquisitionOrDisposal contextRef="Disclosure1">Market Purchase</co:ModeOfAcquisitionOrDisposal>',
        b"",
    )
    with pytest.raises(H024InsiderError, match="missing concepts"):
        parse_pit_xml(raw)


def test_parser_contract_freezes_units_and_candidate_semantics() -> None:
    contract = parser_contract()
    assert contract["regulation"] == "Regulation 7 (2)"
    assert contract["transaction_axis"] == "ChangeInHoldingOfSecuritiesOfPromotersAxis"
    assert contract["quantity_unit"] == "shares"
    assert contract["transaction_value_unit"] == "INR"
    assert contract["ownership_unit"] == "pure"
    assert contract["primary_candidate_instrument"] == "Equity"
    assert contract["primary_candidate_transaction_type"] == "Buy"
    assert contract["primary_candidate_acquisition_mode"] == "Market Purchase"
    assert contract["primary_candidate_actor_categories"] == [
        "Director",
        "KMP",
        "Promoter",
        "Promoter Group",
        "Promoter and Director",
    ]
