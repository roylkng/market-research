"""L001 P015: all source tags are evidence, not automatically owner cash."""

from __future__ import annotations

import math

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p015_investing_taxonomy import (
    NET_INVESTING_CONCEPT,
    ORIGINAL_CONCEPT,
    PPE_CONCEPT,
    _type,
    audit_investing_taxonomy,
    source_investing_facts,
)


def _xml(
    facts: list[tuple[str, str, str, str]],
) -> bytes:
    body = "".join(
        f'<i:{name} contextRef="{context}" unitRef="{unit}">'
        f"{amount}</i:{name}>"
        for name, context, unit, amount in facts
    )
    return (
        '<xbrl xmlns:i="urn:official-original-fixture">'
        + "<note>Fixture only, never a real company</note>" + body + "</xbrl>"
    ).encode()


def test_extract_original_fy26_purchase_and_net_tags_but_never_sum_them():
    data = _xml([
        (PPE_CONCEPT, "FourD", "INR", "839100000"),
        (ORIGINAL_CONCEPT, "FourD", "INR", "21303100000"),
        (NET_INVESTING_CONCEPT, "FourD", "INR", "-19000000000"),
        (
            "ProceedsFromSalesOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
            "FourD", "INR", "1000000000",
        ),
        (
            "PurchaseOfInvestmentsClassifiedAsInvestingActivities",
            "FourD", "INR", "12000000000",
        ),
        ("RevenueFromOperations", "FourD", "INR", "40000000000"),
        ("PurchaseOfInvestmentsClassifiedAsInvestingActivities", "PriorD", "INR", "900"),
    ])
    rows = source_investing_facts(data)
    data = {row["source_concept"]: row for row in rows}
    assert len(data) == 5
    assert data[ORIGINAL_CONCEPT]["fy26_inr_crore"] == 2130.31
    assert data[PPE_CONCEPT]["fy26_inr_crore"] == 83.91
    assert data[NET_INVESTING_CONCEPT]["fy26_inr_crore"] == -1900.0
    assert data["PurchaseOfInvestmentsClassifiedAsInvestingActivities"][
        "fy26_inr_crore"
    ] == 1200.0
    for row in data.values():
        assert row["sum_all_tag_values_as_capex_allowed"] is False
        assert row["may_overlap_or_net_with_other_cash_flow_concepts"] is True
        assert row["unit_ref"] == "INR"
        assert row["context_ref"] == "FourD"


def test_source_cash_taxonomy_does_not_claim_all_investment_outflows():
    rows = source_investing_facts(_xml([
        (PPE_CONCEPT, "FourD", "INR", "10000000"),
        (ORIGINAL_CONCEPT, "FourD", "INR", "0"),
    ]))
    assert len(rows) == 2
    assert not any(r["source_concept"] == NET_INVESTING_CONCEPT for r in rows)
    assert not any(
        "PurchaseOfInvestmentsClassifiedAsInvestingActivities"
        == r["source_concept"]
        for r in rows
    )
    assert rows[0]["classification_for_manual_review"] in {
        "FIXED_ASSET_CASH_PURCHASE",
        "INTANGIBLE_ASSET_CASH_PURCHASE",
    }
    assert _type("AcquisitionOfSubsidiariesClassifiedAsInvestingActivities") == (
        "BUSINESS_OR_INVESTMENT_ACQUISITION_NEEDS_NOTES"
    )
    assert _type("ProceedsFromSalesOfInvestmentsClassifiedAsInvestingActivities") == (
        "INVESTING_PROCEEDS_OR_INFLOW_NOT_NEGATIVE_CAPEX"
    )


def test_missing_different_period_and_non_inr_facts_do_not_fill_zero():
    source = _xml([
        (PPE_CONCEPT, "PriorD", "INR", "450000000"),
        (ORIGINAL_CONCEPT, "FourD", "USD", "1200"),
        ("RevenueFromOperations", "FourD", "INR", "5000000000"),
    ])
    assert source_investing_facts(source) == []


def test_duplicate_identical_originals_are_reported_and_conflicts_abstain():
    same = _xml([
        (PPE_CONCEPT, "FourD", "INR", "450000000"),
        (PPE_CONCEPT, "FourD", "INR", "450000000"),
    ])
    rows = source_investing_facts(same)
    assert rows[0]["raw_source_occurrences_same_value"] == 2
    bad = _xml([
        (PPE_CONCEPT, "FourD", "INR", "450000000"),
        (PPE_CONCEPT, "FourD", "INR", "460000000"),
    ])
    with pytest.raises(AlphaContractError, match="conflicting original"):
        source_investing_facts(bad)


def test_nonfinite_non_numeric_malformed_investing_xml_abstains():
    for value in ("nan", "NaN", "Infinity", "invalid-money"):
        bad = _xml([(PPE_CONCEPT, "FourD", "INR", value)])
        with pytest.raises(AlphaContractError, match="nonfinite|nonnumeric"):
            source_investing_facts(bad)
    for broken in (b"", b"<not-xml", b"test"):
        with pytest.raises(AlphaContractError):
            source_investing_facts(broken)


def test_never_accept_partial_fake_hundred_original_source_as_an_audit():
    with pytest.raises(AlphaContractError, match="original P004"):
        audit_investing_taxonomy({}, {})


def test_suntv_source_falsification_math_is_not_owner_earnings():
    cfo = 1801.64
    ppe = 83.91
    intangible = 2130.31
    assert math.isclose(cfo - ppe, 1717.73, abs_tol=1e-9)
    assert math.isclose(cfo - ppe - intangible, -412.58, abs_tol=1e-9)
