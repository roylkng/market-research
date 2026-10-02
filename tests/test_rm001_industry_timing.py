import csv
import gzip
import io

from marketlab.events import sha256_bytes
from marketlab.rm001_industry_timing import (
    append_industry_source_probe,
    build_industry_snapshot,
    industry_readiness_summary,
    new_industry_source_ledger,
    validate_industry_source_ledger,
)


def _parent_csv():
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
    industries = [f"Industry {index}" for index in range(12)]
    for index in range(705):
        writer.writerow(
            {
                "Company Name": f"Company {index}",
                "Industry": industries[index % len(industries)],
                "Symbol": f"S{index:04d}",
                "Series": "EQ",
                "ISIN Code": f"INE{index:09d}",
            }
        )
    for index in range(2):
        writer.writerow(
            {
                "Company Name": f"Dummy {index}",
                "Industry": industries[index],
                "Symbol": f"DUMMYX{index}",
                "Series": "EQ",
                "ISIN Code": f"DUM{index:09d}",
            }
        )
    writer.writerow(
        {
            "Company Name": "Non EQ",
            "Industry": industries[0],
            "Symbol": "NONEQ",
            "Series": "BE",
            "ISIN Code": "INE999999999",
        }
    )
    return text.getvalue().encode()


def _security_gzip(*, omit_ordinary=None, add_dummy=None):
    text = io.StringIO()
    writer = csv.DictWriter(
        text,
        fieldnames=[
            "TckrSymb",
            "SctySrs",
            "ISIN",
            "FinInstrmNm",
            "DelFlg",
        ],
    )
    writer.writeheader()
    for index in range(705):
        if index == omit_ordinary:
            continue
        writer.writerow(
            {
                "TckrSymb": f"S{index:04d}",
                "SctySrs": "EQ",
                "ISIN": f"INE{index:09d}",
                "FinInstrmNm": f"Company {index}",
                "DelFlg": "",
            }
        )
    if add_dummy is not None:
        writer.writerow(
            {
                "TckrSymb": f"DUMMYX{add_dummy}",
                "SctySrs": "BE",
                "ISIN": f"DUM{add_dummy:09d}",
                "FinInstrmNm": f"Dummy {add_dummy}",
                "DelFlg": "",
            }
        )
    writer.writerow(
        {
            "TckrSymb": "NONEQ",
            "SctySrs": "BE",
            "ISIN": "INE999999999",
            "FinInstrmNm": "Non EQ",
            "DelFlg": "",
        }
    )
    return gzip.compress(text.getvalue().encode(), mtime=0)


def test_sc002_builds_clean_exact_industry_snapshot():
    parent = _parent_csv()
    security = _security_gzip()
    snapshot, diagnostics = build_industry_snapshot(
        session_date="2026-10-05",
        constituent_raw=parent,
        security_raw=security,
    )
    assert diagnostics["source_status"] == "READY"
    assert diagnostics["ordinary_eq_row_count"] == 705
    assert diagnostics["ordinary_eq_matched_count"] == 705
    assert diagnostics["dummy_eq_row_count"] == 2
    assert diagnostics["dummy_invalid_count"] == 0
    assert diagnostics["non_eq_matched_count"] == 1
    assert all(diagnostics["gates"].values())
    assert snapshot["row_count"] == 705
    assert snapshot["industry_label_count"] == 12
    assert len(snapshot["snapshot_sha256"]) == 64
    assert snapshot["return_labels_attached"] is False


def test_sc002_rejects_missing_ordinary_eq():
    _, diagnostics = build_industry_snapshot(
        session_date="2026-10-05",
        constituent_raw=_parent_csv(),
        security_raw=_security_gzip(omit_ordinary=100),
    )
    assert diagnostics["source_status"] == "SEMANTIC_QUALITY_REJECTED"
    assert diagnostics["ordinary_eq_missing_count"] == 1
    assert diagnostics["gates"]["ordinary_eq_missing_zero"] is False


def test_sc002_rejects_dummy_present_under_any_security_series():
    _, diagnostics = build_industry_snapshot(
        session_date="2026-10-05",
        constituent_raw=_parent_csv(),
        security_raw=_security_gzip(add_dummy=0),
    )
    assert diagnostics["source_status"] == "SEMANTIC_QUALITY_REJECTED"
    assert diagnostics["dummy_invalid_count"] == 1
    assert diagnostics["gates"]["dummy_semantics_all_valid"] is False


def test_sc002_ready_requires_capture_by_1830_ist():
    parent = _parent_csv()
    security = _security_gzip()
    ledger, attempt, snapshot = append_industry_source_probe(
        new_industry_source_ledger(),
        session_date="2026-10-05",
        captured_at_utc="2026-10-05T12:55:00+00:00",
        constituent_raw=parent,
        security_raw=security,
        security_source_url="https://nsearchives.nseindia.com/security.gz",
    )
    assert snapshot is not None
    assert attempt is not None
    assert attempt["source_status"] == "READY"
    assert attempt["captured_before_or_at_cutoff"] is True
    assert attempt["ready_before_cutoff"] is True
    assert attempt["constituent_raw_sha256"] == sha256_bytes(parent)
    assert attempt["security_raw_sha256"] == sha256_bytes(security)
    validate_industry_source_ledger(ledger)

    late, late_attempt, _ = append_industry_source_probe(
        new_industry_source_ledger(),
        session_date="2026-10-05",
        captured_at_utc="2026-10-05T13:00:01+00:00",
        constituent_raw=parent,
        security_raw=security,
        security_source_url="https://nsearchives.nseindia.com/security.gz",
    )
    assert late_attempt is not None
    assert late_attempt["source_status"] == "READY"
    assert late_attempt["captured_before_or_at_cutoff"] is False
    assert late_attempt["ready_before_cutoff"] is False
    validate_industry_source_ledger(late)


def test_sc002_three_clean_sessions_authorize_only_factor_design():
    ledger = new_industry_source_ledger()
    parent = _parent_csv()
    security = _security_gzip()
    for session in ("2026-10-05", "2026-10-06", "2026-10-07"):
        ledger, attempt, snapshot = append_industry_source_probe(
            ledger,
            session_date=session,
            captured_at_utc=f"{session}T12:50:00+00:00",
            constituent_raw=parent,
            security_raw=security,
            security_source_url="https://nsearchives.nseindia.com/security.gz",
        )
        assert attempt is not None and snapshot is not None

    summary = industry_readiness_summary(ledger)
    assert summary["ready_before_cutoff_session_count"] == 3
    assert summary["prospective_industry_source_ready"] is True
    assert summary["additional_ready_sessions_needed"] == 0
    assert summary["industry_factor_enabled"] is False
    assert summary["historical_backfill_allowed"] is False
