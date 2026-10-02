import io
import zipfile

from marketlab.rm001_d008 import (
    analyze_monthly_workbook,
    summarize_d008,
)


def _xlsx(
    *,
    headers,
    rows,
    sheet_name="Security Classification",
):
    strings = []
    string_index = {}

    def shared(value):
        value = str(value)
        if value not in string_index:
            string_index[value] = len(strings)
            strings.append(value)
        return string_index[value]

    def col_name(index):
        result = ""
        value = index + 1
        while value:
            value, remainder = divmod(value - 1, 26)
            result = chr(ord("A") + remainder) + result
        return result

    all_rows = [headers, *rows]
    xml_rows = []
    for row_number, values in enumerate(all_rows, start=1):
        cells = []
        for column, value in enumerate(values):
            if value is None or value == "":
                continue
            index = shared(value)
            ref = f"{col_name(column)}{row_number}"
            cells.append(
                f'<c r="{ref}" t="s"><v>{index}</v></c>'
            )
        xml_rows.append(
            f'<row r="{row_number}">{"".join(cells)}</row>'
        )

    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(strings)}" uniqueCount="{len(strings)}">'
        + "".join(f"<si><t>{value}</t></si>" for value in strings)
        + "</sst>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        + "".join(xml_rows)
        + "</sheetData></worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>'
        f'<sheet name="{sheet_name}" sheetId="1" r:id="rId1"/>'
        '</sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )

    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        archive.writestr("xl/sharedStrings.xml", shared_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return raw.getvalue()


def _passing_workbook(month="2026-08"):
    rows = [
        [f"SYM{index:04d}", f"INE{index:09d}", f"Company {index}", "Banks"]
        for index in range(600)
    ]
    return analyze_monthly_workbook(
        _xlsx(
            headers=["Symbol", "ISIN", "Company Name", "Basic Industry"],
            rows=rows,
        ),
        month=month,
        source_url=f"https://example.test/{month}.xlsx",
    )


def test_d008_explicit_isin_basic_industry_mapping_passes():
    report = _passing_workbook()
    assert report["source_candidate_pass"] is True
    assert report["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["data_row_count"] == 600
    assert candidate["classification_coverage"] == 1.0
    assert candidate["duplicate_identity_count"] == 0
    assert candidate["identity_semantics"] == "ISIN"
    assert candidate["classification_headers"]["3"] == "BASIC INDUSTRY"


def test_d008_free_text_description_without_explicit_classification_fails():
    report = analyze_monthly_workbook(
        _xlsx(
            headers=["Symbol", "ISIN", "Company Name", "Business Description"],
            rows=[
                ["TEST", "INE000000001", "Test Ltd", "Makes banking software"]
            ]
            * 600,
        ),
        month="2026-08",
        source_url="https://example.test/no-sector.xlsx",
    )
    assert report["source_candidate_pass"] is False
    assert report["candidate_count"] == 0


def test_d008_duplicate_direct_identities_block_candidate_promotion():
    rows = [
        [f"SYM{index:04d}", f"INE{index:09d}", f"Company {index}", "Banks"]
        for index in range(599)
    ]
    rows.append(["DUP", "INE000000000", "Duplicate", "Banks"])
    report = analyze_monthly_workbook(
        _xlsx(
            headers=["Symbol", "ISIN", "Company Name", "Sector"],
            rows=rows,
        ),
        month="2026-08",
        source_url="https://example.test/dup.xlsx",
    )
    assert report["candidate_count"] == 1
    assert report["candidates"][0]["duplicate_identity_count"] == 1
    assert report["source_candidate_pass"] is False


def test_d008_summary_direct_promotion_requires_all_four_stable_isin_samples():
    reports = [
        _passing_workbook(month)
        for month in ("2025-09", "2025-12", "2026-01", "2026-08")
    ]
    summary = summarize_d008(reports)
    assert summary["status"] == "PASS_DIRECT_POINT_IN_TIME_SOURCE_CANDIDATE"
    assert summary["all_four_have_passing_candidate"] is True
    assert summary["classification_semantics_stable"] is True
    assert summary["all_four_direct_isin"] is True
    assert summary["direct_point_in_time_sector_promotion_authorized"] is True


def test_d008_summary_fails_if_one_sample_has_no_classification_mapping():
    reports = [
        _passing_workbook("2025-09"),
        _passing_workbook("2025-12"),
        _passing_workbook("2026-01"),
        analyze_monthly_workbook(
            _xlsx(
                headers=["Symbol", "ISIN", "Company Name", "Description"],
                rows=[
                    [f"S{index}", f"INE{index:09d}", f"Company {index}", "Text"]
                    for index in range(600)
                ],
            ),
            month="2026-08",
            source_url="https://example.test/fail.xlsx",
        ),
    ]
    summary = summarize_d008(reports)
    assert summary["status"] == "FAIL_SOURCE_FEASIBILITY"
    assert summary["full_historical_scan_authorized"] is False
    assert summary["direct_point_in_time_sector_promotion_authorized"] is False
