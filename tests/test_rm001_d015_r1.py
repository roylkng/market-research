import csv
import gzip
import io

import pytest

import marketlab.rm001_d015_r1 as r1
from marketlab.alpha import AlphaContractError
from marketlab.events import sha256_bytes
from marketlab.rm001_d015_r1 import build_d015_r1_report, parse_security_master_all_series


def _parent_csv():
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
    for index in range(755):
        writer.writerow(
            {
                "Company Name": f"Company {index}",
                "Industry": industries[index % len(industries)],
                "Symbol": f"S{index:04d}",
                "Series": "EQ" if index < 745 else "BE",
                "ISIN Code": f"INE{index:09d}",
            }
        )
    return text.getvalue().encode()


def _security_gzip(*, conflict_index=None):
    text = io.StringIO()
    fields = [
        "TckrSymb",
        "SctySrs",
        "ISIN",
        "FinInstrmNm",
        "DelFlg",
    ]
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    for index in range(755):
        series = "EQ" if index < 745 else "BE"
        if conflict_index == index:
            series = "EQ" if series != "EQ" else "BE"
        writer.writerow(
            {
                "TckrSymb": f"S{index:04d}",
                "SctySrs": series,
                "ISIN": f"INE{index:09d}",
                "FinInstrmNm": f"Company {index}",
                "DelFlg": "",
            }
        )
    return gzip.compress(text.getvalue().encode(), mtime=0)


def test_r1_security_parser_keeps_all_series():
    rows, diagnostics = parse_security_master_all_series(_security_gzip())
    assert len(rows) == 755
    assert diagnostics["duplicate_identity_count"] == 0
    assert diagnostics["series_counts"] == {"BE": 10, "EQ": 745}


def test_r1_passes_exact_eq_projection_semantics(monkeypatch):
    parent = _parent_csv()
    monkeypatch.setattr(r1, "PARENT_RAW_SHA256", sha256_bytes(parent))
    report = build_d015_r1_report(
        parent_raw=parent,
        security_raw=_security_gzip(),
    )
    assert report["status"] == "PASS_EQ_PROJECTION_SEMANTICS"
    assert report["parent"]["status_changed_by_r1"] is False
    assert report["correspondence"]["identity_join_coverage"] == pytest.approx(1.0)
    assert report["correspondence"]["series_agreement_coverage"] == pytest.approx(1.0)
    assert report["correspondence"][
        "parent_non_eq_confirmed_non_eq_count"
    ] == 10
    assert report["projected_eq_subset"]["row_count"] == 745
    assert report["prospective_eq_capture_authorized"] is True
    assert all(report["promotion_gates"].values())


def test_r1_fails_one_series_conflict(monkeypatch):
    parent = _parent_csv()
    monkeypatch.setattr(r1, "PARENT_RAW_SHA256", sha256_bytes(parent))
    report = build_d015_r1_report(
        parent_raw=parent,
        security_raw=_security_gzip(conflict_index=750),
    )
    assert report["status"] == "FAIL_EQ_PROJECTION_SEMANTICS"
    assert report["correspondence"][
        "parent_non_eq_confirmed_non_eq_fraction"
    ] == pytest.approx(0.9)
    assert report["promotion_gates"][
        "parent_non_eq_confirmed_non_eq_fraction_100pct"
    ] is False


def test_r1_rejects_missing_security_schema():
    raw = gzip.compress(b"TckrSymb,SctySrs,ISIN\nA,EQ,INE1\n", mtime=0)
    with pytest.raises(AlphaContractError, match="required columns missing"):
        parse_security_master_all_series(raw)
