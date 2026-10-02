import csv
import gzip
import io

import pytest

import marketlab.rm001_d015_r2 as r2
from marketlab.events import sha256_bytes
from marketlab.rm001_d015_r2 import build_d015_r2_report


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


def _security_gzip(*, omit_index=None, duplicate_triplet_index=None):
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
        if index == omit_index:
            continue
        series = "EQ" if index < 745 else "BE"
        row = {
            "TckrSymb": f"S{index:04d}",
            "SctySrs": series,
            "ISIN": f"INE{index:09d}",
            "FinInstrmNm": f"Company {index}",
            "DelFlg": "",
        }
        writer.writerow(row)
        # Add another series for every identity to prove Symbol+ISIN alone is
        # ambiguous while the exact triplet remains unique.
        alternate = dict(row)
        alternate["SctySrs"] = "BL" if series != "BL" else "BE"
        writer.writerow(alternate)
        if index == duplicate_triplet_index:
            writer.writerow(row)
    return gzip.compress(text.getvalue().encode(), mtime=0)


def _run(monkeypatch, *, security_raw):
    parent = _parent_csv()
    monkeypatch.setattr(r2, "PARENT_RAW_SHA256", sha256_bytes(parent))
    monkeypatch.setattr(r2, "SECURITY_RAW_SHA256", sha256_bytes(security_raw))
    return build_d015_r2_report(
        parent_raw=parent,
        security_raw=security_raw,
    )


def test_r2_passes_exact_triplet_correspondence(monkeypatch):
    report = _run(
        monkeypatch,
        security_raw=_security_gzip(),
    )
    assert report["status"] == "PASS_TRIPLET_EQ_PROJECTION_SEMANTICS"
    assert report["triplet_correspondence"]["join_coverage"] == pytest.approx(1.0)
    assert report["triplet_correspondence"]["eq_confirmed_count"] == 745
    assert report["triplet_correspondence"]["non_eq_confirmed_count"] == 10
    assert report["security_source"]["symbol_isin_duplicate_count"] == 755
    assert report["projected_eq_subset"]["row_count"] == 745
    assert report["prospective_eq_capture_authorized"] is True
    assert all(report["promotion_gates"].values())


def test_r2_fails_missing_exact_triplet(monkeypatch):
    report = _run(
        monkeypatch,
        security_raw=_security_gzip(omit_index=750),
    )
    assert report["status"] == "FAIL_TRIPLET_EQ_PROJECTION_SEMANTICS"
    assert report["triplet_correspondence"]["missing_count"] == 1
    assert report["promotion_gates"]["triplet_join_coverage_100pct"] is False


def test_r2_fails_ambiguous_exact_triplet(monkeypatch):
    report = _run(
        monkeypatch,
        security_raw=_security_gzip(duplicate_triplet_index=750),
    )
    assert report["status"] == "FAIL_TRIPLET_EQ_PROJECTION_SEMANTICS"
    assert report["triplet_correspondence"]["ambiguous_count"] == 1
    assert report["promotion_gates"][
        "ambiguous_triplet_match_count_zero"
    ] is False
