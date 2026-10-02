import io
import zipfile
from xml.sax.saxutils import escape

from marketlab.rm001_d010 import (
    SourceBytes,
    annual_link_selection,
    build_d010_phase_ab_report,
    build_d010_phase_c_report,
    parse_d010_annual_archive,
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



def _column_name(index):
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _xlsx(headers, rows):
    def row_xml(row_index, values):
        cells = []
        for index, value in enumerate(values):
            if value is None:
                continue
            ref = f"{_column_name(index)}{row_index}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
            )
        return f'<row r="{row_index}">{"".join(cells)}</row>'

    sheet_rows = [row_xml(1, headers)]
    sheet_rows.extend(
        row_xml(index + 2, row)
        for index, row in enumerate(rows)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Export Worksheet" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        '</worksheet>'
    )
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return raw.getvalue()


_GENERAL_HEADERS = [
    "APP_ID",
    "TLA_SUBMITTED_DT",
    "SYMB_SYMBOL",
    "Name of The Company",
    "Corporate Identity Number (CIN) of the Listed Entity",
    "Current Financial Year start date",
    "Current Financial Year end date",
]
_PRODUCT_HEADERS = [
    "APP_ID",
    "SYMB_SYMBOL",
    "Product/Service sold by the entity",
    "NIC Code sold by the entity",
    "Percentage(%) of total Turnover contributed sold by the entity",
]


def _annual_dump(count, *, include_nic=True, suffix=""):
    general_rows = []
    product_rows = []
    for index in range(count):
        app_id = str(1000 + index)
        symbol = f"S{index:04d}{suffix}"
        cin = f"L{index:020d}"
        general_rows.append(
            [
                app_id,
                "01-APR-2025 12:00:00",
                symbol,
                f"Company {index}",
                cin,
                "2024-04-01",
                "2025-03-31",
            ]
        )
        if include_nic:
            product_rows.append(
                [
                    app_id,
                    symbol,
                    "Product",
                    str(10000 + (index % 50)),
                    "100",
                ]
            )
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr(
            "BRSR_general/brsr_general.xlsx",
            _xlsx(_GENERAL_HEADERS, general_rows),
        )
        archive.writestr(
            "BRSR_general/BRSR_GENERAL_PRODUCT_SERVICES_SOLD.xlsx",
            _xlsx(_PRODUCT_HEADERS, product_rows),
        )
    return raw.getvalue()


def test_phase_c_parser_joins_app_id_and_reports_explicit_nic():
    report = parse_d010_annual_archive(
        year="TEST",
        raw=_annual_dump(3),
    )
    assert report["general_data_row_count"] == 3
    assert report["product_data_row_count"] == 3
    assert report["unique_entity_count"] == 3
    assert report["stable_identity_coverage"] == 1.0
    assert report["reporting_year_coverage"] == 1.0
    assert report["explicit_nic_coverage"] == 1.0
    assert report["orphan_product_row_count"] == 0


def test_phase_c_pass_requires_both_years_and_no_equal_count_cap_pattern():
    report = build_d010_phase_c_report(
        fy2023_24_raw=_annual_dump(500, suffix="A"),
        fy2024_25_raw=_annual_dump(501, suffix="B"),
    )
    assert report["coverage_gates_pass"] is True
    assert report["equal_required_year_entity_counts"] is False
    assert report["status"] == "PASS_SOURCE_FEASIBILITY"
    assert report["d011_authorized"] is True


def test_phase_c_fails_when_one_required_year_has_no_nic_rows():
    report = build_d010_phase_c_report(
        fy2023_24_raw=_annual_dump(500, suffix="A"),
        fy2024_25_raw=_annual_dump(
            501,
            include_nic=False,
            suffix="B",
        ),
    )
    assert report["coverage_gates_pass"] is False
    assert report["status"] == "FAIL_SOURCE_FEASIBILITY"
    assert "FY2024-25:minimum_nic_coverage_90pct" in report[
        "failure_reasons"
    ]
    assert report["d011_authorized"] is False
