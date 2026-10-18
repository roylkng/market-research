"""L001 P014: original source cash-intangibles and abstention safeguards."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from datetime import datetime

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p014_intangible_cash import (
    CUTOFF_UTC,
    ORIGINAL_CONCEPT,
    _utc,
    audit_original_intangibles,
    extract_original_intangible_cr,
)


def original_intangible_xml(
    value: str = "21303100000", *,
    context: str = "FourD", unit: str = "INR", duplicated: bool = False,
) -> bytes:
    start = (
        '<i:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities '
        f'contextRef="{context}" unitRef="{unit}">{value}'
        '</i:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities>'
    )
    repeated = start if duplicated else ""
    return (
        '<xbrl xmlns:i="urn:financial-original-test">'
        + start + repeated + "</xbrl>"
    ).encode()


def test_issuer_suntv_cash_intangible_tag_comes_from_exact_annual_context():
    assert len(original_intangible_xml()) >= 100
    assert extract_original_intangible_cr(original_intangible_xml()) == 2130.31
    assert extract_original_intangible_cr(original_intangible_xml("0")) == 0


def test_missing_future_wrong_unit_or_wrong_concept_do_not_impute_zero():
    for raw in (
        original_intangible_xml(context="PriorD"),
        original_intangible_xml(unit="USD"),
        original_intangible_xml().replace(
            ORIGINAL_CONCEPT.encode(), b"AcquisitionOfFinancialInstruments"
        ),
        b"<xbrl><bad>",
        b"",
    ):
        with pytest.raises(AlphaContractError):
            extract_original_intangible_cr(raw)


def test_ambiguous_and_nonfinite_source_facts_rejected():
    for raw in (
        original_intangible_xml(duplicated=True),
        original_intangible_xml("NaN"),
        original_intangible_xml("Infinity"),
        original_intangible_xml("-200"),
        original_intangible_xml("not-a-number"),
    ):
        with pytest.raises(AlphaContractError):
            extract_original_intangible_cr(raw)


def test_unauthenticated_full_company_source_does_not_yield_quality_rank():
    with pytest.raises(AlphaContractError, match="original P004"):
        audit_original_intangibles({}, {})
    with pytest.raises(AlphaContractError, match="original P004"):
        audit_original_intangibles({
            "report_sha256": digest({"company_count": 100}),
            "company_count": 100,
        }, {})


def test_original_exact_utc_cutoff_required():
    assert _utc(CUTOFF_UTC) == datetime.fromisoformat(
        "2026-10-15T13:00:00+00:00"
    )
    for invalid in ("2026-10-15T13:00:00", "bad", None):
        with pytest.raises(AlphaContractError, match="UTC"):
            _utc(invalid)


def test_test_fixture_cash_after_both_spend_types_is_not_owner_cash():
    cfo, ppe = 1801.64, 83.91
    intangibles = extract_original_intangible_cr(original_intangible_xml())
    assert math.isclose(cfo - ppe, 1717.73, abs_tol=1e-8)
    assert math.isclose(cfo - ppe - intangibles, -412.58, abs_tol=1e-8)
