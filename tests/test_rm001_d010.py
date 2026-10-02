import io
import zipfile

from marketlab.rm001_d010 import (
    SourceBytes,
    annual_link_selection,
    build_d010_phase_ab_report,
    phase_a_taxonomy_report,
)


def _zip(members):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return raw.getvalue()


def test_phase_a_passes_structured_nic_identity_and_year_concepts():
    utility = SourceBytes(
        "utility",
        "https://nsearchives.nseindia.com/u.zip",
        _zip(
            {
                "xl/sharedStrings.xml": (
                    "<sst><si>Corporate Identity Number CIN</si>"
                    "<si>Financial Year</si><si>NIC Code</si>"
                    "<si>Percentage of Turnover</si></sst>"
                )
            }
        ),
    )
    taxonomy = SourceBytes(
        "taxonomy",
        "https://nsearchives.nseindia.com/t.zip",
        _zip(
            {
                "brsr.xsd": (
                    '<schema><element name="CorporateIdentityNumber"/>'
                    '<element name="FinancialYear"/>'
                    '<element name="NICCode"/>'
                    '<element name="ProductService"/>'
                    '<element name="PercentageTurnover"/></schema>'
                )
            }
        ),
    )
    archive = SourceBytes(
        "archive",
        "https://nsearchives.nseindia.com/a.zip",
        _zip({"old/brsr.xsd": '<element name="NICCode"/>'}),
    )
    report = phase_a_taxonomy_report(
        utility=utility,
        taxonomy=taxonomy,
        taxonomy_archive=archive,
    )
    assert report["status"] == "PASS"
    assert report["explicit_nic_concept_found"] is True
    assert report["stable_identity_concept_found"] is True
    assert report["reporting_year_concept_found"] is True
    assert report["turnover_share_concept_found"] is True


def test_annual_selection_requires_explicit_year_evidence():
    discovery = {
        "direct_brsr_links": [
            {
                "url": "https://nsearchives.nseindia.com/brsr_fy23-24.zip",
                "context": "Business Responsibility FY 23-24",
            },
            {
                "url": "https://nsearchives.nseindia.com/brsr_fy24-25.zip",
                "context": "Business Responsibility FY 24-25",
            },
        ],
        "script_brsr_links": [],
    }
    selected = annual_link_selection(discovery)
    assert len(selected["FY2023-24"]) == 1
    assert len(selected["FY2024-25"]) == 1


def test_phase_ab_does_not_authorize_phase_c_without_bulk_urls():
    source = SourceBytes(
        "utility",
        "https://nsearchives.nseindia.com/u.zip",
        _zip(
            {
                "schema.xsd": (
                    "NICCode CorporateIdentityNumber FinancialYear Turnover"
                )
            }
        ),
    )
    compliance = SourceBytes(
        "compliance",
        "https://www.nseindia.com/regulations/listing-compliance",
        b"<html><script src='/assets/app.js'></script></html>",
    )
    filings = SourceBytes(
        "filings",
        "https://www.nseindia.com/companies-listing/"
        "corporate-filings-bussiness-sustainabilitiy-reports",
        b"<html></html>",
    )
    report = build_d010_phase_ab_report(
        utility=source,
        taxonomy=source,
        taxonomy_archive=source,
        compliance_html=compliance,
        filings_html=filings,
        script_sources=[],
    )
    assert report["phase_a"]["status"] == "PASS"
    assert report["phase_b"]["status"] == "FAIL_URL_DISCOVERY"
    assert report["phase_c_authorized"] is False
    assert report["return_labels_opened"] is False
