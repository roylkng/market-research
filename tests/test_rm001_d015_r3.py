import csv
import gzip
import io

import pytest

import marketlab.rm001_d015_r3 as r3
from marketlab.events import sha256_bytes
from marketlab.rm001_d015_r3 import build_d015_r3_report


DUMMIES = {
    10: ("DUMMYHEG", "DUM545A01024"),
    20: ("DUMMYINGL1", "DU1560A01023"),
    30: ("DUMMYINGL2", "DU2560A01023"),
    40: ("DUMMYINXGN", "DUM510W01014"),
    50: ("DUMMYTRVN", "DUM256C01024"),
}


def _parent_csv(*, mutate_dummy_symbol=None):
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
        if index in DUMMIES:
            symbol, isin = DUMMIES[index]
            if mutate_dummy_symbol == index:
                symbol = "SYNTHETICX"
            writer.writerow(
                {
                    "Company Name": f"Dummy Company {index}",
                    "Industry": industries[index % len(industries)],
                    "Symbol": symbol,
                    "Series": "EQ",
                    "ISIN Code": isin,
                }
            )
            continue
        # Keep exactly 745 EQ rows in total. Five are dummies, so ordinary EQ
        # identities occupy the remaining 740 slots among indices < 745.
        series = "EQ" if index < 745 else "BE"
        writer.writerow(
            {
                "Company Name": f"Company {index}",
                "Industry": industries[index % len(industries)],
                "Symbol": f"S{index:04d}",
                "Series": series,
                "ISIN Code": f"INE{index:09d}",
            }
        )
    return text.getvalue().encode()


def _security_gzip(
    *,
    omit_ordinary_index=None,
    add_dummy_alt_series_index=None,
):
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
        if index in DUMMIES:
            if index == add_dummy_alt_series_index:
                symbol, isin = DUMMIES[index]
                writer.writerow(
                    {
                        "TckrSymb": symbol,
                        "SctySrs": "BE",
                        "ISIN": isin,
                        "FinInstrmNm": f"Dummy Company {index}",
                        "DelFlg": "",
                    }
                )
            continue
        if index == omit_ordinary_index:
            continue
        series = "EQ" if index < 745 else "BE"
        writer.writerow(
            {
                "TckrSymb": f"S{index:04d}",
                "SctySrs": series,
                "ISIN": f"INE{index:09d}",
                "FinInstrmNm": f"Company {index}",
                "DelFlg": "",
            }
        )
        # Prove Symbol+ISIN alone may remain multi-series while exact triplet
        # correspondence remains unique.
        writer.writerow(
            {
                "TckrSymb": f"S{index:04d}",
                "SctySrs": "BL" if series != "BL" else "BE",
                "ISIN": f"INE{index:09d}",
                "FinInstrmNm": f"Company {index}",
                "DelFlg": "",
            }
        )
    return gzip.compress(text.getvalue().encode(), mtime=0)


def _run(monkeypatch, *, parent=None, security=None):
    parent_raw = parent or _parent_csv()
    security_raw = security or _security_gzip()
    monkeypatch.setattr(
        r3,
        "PARENT_RAW_SHA256",
        sha256_bytes(parent_raw),
    )
    monkeypatch.setattr(
        r3,
        "SECURITY_RAW_SHA256",
        sha256_bytes(security_raw),
    )
    return build_d015_r3_report(
        parent_raw=parent_raw,
        security_raw=security_raw,
    )


def test_r3_passes_documented_dummy_separation(monkeypatch):
    report = _run(monkeypatch)
    assert report["status"] == "PASS_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS"
    assert report["ordinary_eq_correspondence"]["row_count"] == 740
    assert report["ordinary_eq_correspondence"]["matched_count"] == 740
    assert report["dummy_placeholders"]["row_count"] == 5
    assert (
        report["dummy_placeholders"][
            "same_identity_any_series_match_count_total"
        ]
        == 0
    )
    assert report["non_eq_correspondence"]["matched_count"] == 10
    assert report["projected_tradable_eq_subset"]["row_count"] == 740
    assert report["prospective_industry_capture_design_authorized"] is True
    assert all(report["promotion_gates"].values())


def test_r3_rejects_missing_ordinary_eq(monkeypatch):
    report = _run(
        monkeypatch,
        security=_security_gzip(omit_ordinary_index=100),
    )
    assert report["status"] == "FAIL_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS"
    assert report["ordinary_eq_correspondence"]["missing_count"] == 1
    assert report["promotion_gates"][
        "ordinary_eq_exact_match_fraction_100pct"
    ] is False


def test_r3_rejects_dummy_that_exists_under_alternate_series(monkeypatch):
    report = _run(
        monkeypatch,
        security=_security_gzip(add_dummy_alt_series_index=10),
    )
    assert report["status"] == "FAIL_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS"
    assert (
        report["dummy_placeholders"][
            "same_identity_any_series_match_count_total"
        ]
        == 1
    )
    assert report["promotion_gates"][
        "dummy_same_identity_any_series_match_count_total_zero"
    ] is False


def test_r3_rejects_non_literal_dummy_identity(monkeypatch):
    parent = _parent_csv(mutate_dummy_symbol=10)
    report = _run(monkeypatch, parent=parent)
    assert report["status"] == "FAIL_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS"
    assert report["dummy_placeholders"]["row_count"] == 4
    assert report["promotion_gates"]["dummy_eq_row_count_exact"] is False
    assert report["ordinary_eq_correspondence"]["missing_count"] == 1
