import csv
import io

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.rm001_d015 import build_d015_report, parse_constituent_csv


def _csv(rows):
    text = io.StringIO()
    writer = csv.DictWriter(
        text,
        fieldnames=[
            "Company Name",
            "Industry",
            "Symbol",
            "Series",
            "ISIN Code",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    return text.getvalue().encode()


def _rows(count=705):
    industries = [
        "Financial Services",
        "Capital Goods",
        "Healthcare",
        "Information Technology",
        "Chemicals",
        "Consumer Services",
        "Consumer Durables",
        "Metals & Mining",
        "Construction",
        "Power",
        "Automobile and Auto Components",
        "Fast Moving Consumer Goods",
    ]
    return [
        {
            "Company Name": f"Company {index}",
            "Industry": industries[index % len(industries)],
            "Symbol": f"S{index:04d}",
            "Series": "EQ",
            "ISIN Code": f"INE{index:09d}",
        }
        for index in range(count)
    ]


def test_d015_parser_requires_frozen_schema():
    raw = b"Company Name,Symbol,Series,ISIN Code\nA,A,EQ,INE000000001\n"
    with pytest.raises(AlphaContractError, match="required columns missing"):
        parse_constituent_csv(raw)


def test_d015_passes_clean_broad_constituent_source():
    report = build_d015_report(raw=_csv(_rows()))
    assert report["status"] == "PASS_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY"
    assert report["prospective_capture_design_authorized"] is True
    assert report["historical_backfill_authorized"] is False
    assert report["row_count"] == 705
    assert report["unique_identity_count"] == 705
    assert report["industry_label_count"] == 12
    assert all(report["promotion_gates"].values())


def test_d015_fails_duplicate_identity_without_deduplication():
    rows = _rows()
    rows.append(dict(rows[0]))
    report = build_d015_report(raw=_csv(rows))
    assert report["status"] == "FAIL_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY"
    assert report["duplicate_identity_count"] == 1
    assert report["promotion_gates"]["zero_duplicate_identities"] is False


def test_d015_fails_symbol_to_multiple_isin_conflict():
    rows = _rows()
    extra = dict(rows[0])
    extra["ISIN Code"] = "INE999999999"
    rows.append(extra)
    report = build_d015_report(raw=_csv(rows))
    assert report["symbol_to_multiple_isin_conflict_count"] == 1
    assert report["promotion_gates"][
        "zero_symbol_to_multiple_isin_conflicts"
    ] is False


def test_d015_fails_low_industry_coverage():
    rows = _rows()
    for row in rows[:20]:
        row["Industry"] = ""
    report = build_d015_report(raw=_csv(rows))
    assert report["industry_coverage"] < 0.99
    assert report["promotion_gates"]["minimum_industry_coverage"] is False
