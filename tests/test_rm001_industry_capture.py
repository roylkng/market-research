import csv
import gzip
import io
import json
from pathlib import Path

import pytest

from marketlab.alpha import digest
from marketlab.rm001_industry_capture import (
    append_industry_attempt,
    build_industry_snapshot,
    industry_readiness_summary,
    latest_eligible_sc001_target,
    mapping_change_diagnostics,
    new_industry_source_ledger,
    validate_industry_source_ledger,
)


DUMMY_ROWS = {
    20: ("DUMMYA", "DUMA00000001"),
    30: ("DUMMYB", "DUMB00000002"),
    40: ("DUMMYC", "DUMC00000003"),
}


def _parent_csv(*, ordinary_count=700):
    total = ordinary_count + len(DUMMY_ROWS) + 2
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
    ordinary_seen = 0
    index = 0
    while index < total:
        if index in DUMMY_ROWS:
            symbol, isin = DUMMY_ROWS[index]
            writer.writerow(
                {
                    "Company Name": f"Dummy {index}",
                    "Industry": "Capital Goods",
                    "Symbol": symbol,
                    "Series": "EQ",
                    "ISIN Code": isin,
                }
            )
            index += 1
            continue
        if ordinary_seen < ordinary_count:
            writer.writerow(
                {
                    "Company Name": f"Company {index}",
                    "Industry": (
                        "Financial Services"
                        if index % 2 == 0
                        else "Information Technology"
                    ),
                    "Symbol": f"S{index:04d}",
                    "Series": "EQ",
                    "ISIN Code": f"INE{index:09d}",
                }
            )
            ordinary_seen += 1
        else:
            writer.writerow(
                {
                    "Company Name": f"Non EQ {index}",
                    "Industry": "Realty",
                    "Symbol": f"N{index:04d}",
                    "Series": "BE",
                    "ISIN Code": f"INB{index:09d}",
                }
            )
        index += 1
    return text.getvalue().encode()


def _security_gzip(
    *,
    ordinary_count=700,
    omit_symbol=None,
    dummy_alt_series=None,
    deletion_symbol=None,
):
    total = ordinary_count + len(DUMMY_ROWS) + 2
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
    ordinary_seen = 0
    index = 0
    while index < total:
        if index in DUMMY_ROWS:
            if index == dummy_alt_series:
                symbol, isin = DUMMY_ROWS[index]
                writer.writerow(
                    {
                        "TckrSymb": symbol,
                        "SctySrs": "BE",
                        "ISIN": isin,
                        "FinInstrmNm": f"Dummy {index}",
                        "DelFlg": "N",
                    }
                )
            index += 1
            continue

        if ordinary_seen < ordinary_count:
            symbol = f"S{index:04d}"
            isin = f"INE{index:09d}"
            series = "EQ"
            ordinary_seen += 1
        else:
            symbol = f"N{index:04d}"
            isin = f"INB{index:09d}"
            series = "BE"

        if symbol == omit_symbol:
            index += 1
            continue

        writer.writerow(
            {
                "TckrSymb": symbol,
                "SctySrs": series,
                "ISIN": isin,
                "FinInstrmNm": f"Security {index}",
                "DelFlg": "Y" if symbol == deletion_symbol else "N",
            }
        )
        alternate = "BL" if series != "BL" else "BE"
        writer.writerow(
            {
                "TckrSymb": symbol,
                "SctySrs": alternate,
                "ISIN": isin,
                "FinInstrmNm": f"Security {index}",
                "DelFlg": "N",
            }
        )
        index += 1
    return gzip.compress(text.getvalue().encode(), mtime=0)


def _snapshot(**kwargs):
    return build_industry_snapshot(
        constituent_raw=kwargs.get("constituent_raw", _parent_csv()),
        security_raw=kwargs.get("security_raw", _security_gzip()),
        target_session_date="2026-10-02",
        captured_at_utc="2026-10-02T14:30:00+00:00",
        constituent_raw_path="raw/constituent.csv",
        security_raw_path="raw/security.csv.gz",
    )


def test_sc002_snapshot_passes_r3_variable_dummy_semantics():
    snapshot = _snapshot()
    assert snapshot["status"] == "READY"
    assert snapshot["semantics"]["mapped_eq_count"] == 700
    assert snapshot["semantics"]["dummy_count"] == 3
    assert snapshot["semantics"]["eq_missing_count"] == 0
    assert snapshot["projected_tradable_eq"]["row_count"] == 700
    assert snapshot["projected_tradable_eq"]["industry_coverage"] == pytest.approx(
        1.0
    )
    assert len(snapshot["mapping_rows"]) == 700
    assert all(snapshot["promotion_gates"].values())


def test_sc002_snapshot_rejects_ordinary_missing_eq():
    snapshot = _snapshot(
        security_raw=_security_gzip(omit_symbol="S0100")
    )
    assert snapshot["status"] == "SEMANTICS_INELIGIBLE"
    assert snapshot["semantics"]["eq_missing_count"] == 1
    assert snapshot["promotion_gates"][
        "ordinary_eq_missing_count_zero"
    ] is False


def test_sc002_snapshot_rejects_dummy_identity_under_alternate_series():
    snapshot = _snapshot(
        security_raw=_security_gzip(dummy_alt_series=20)
    )
    assert snapshot["status"] == "SEMANTICS_INELIGIBLE"
    assert snapshot["semantics"]["dummy_count"] == 2
    assert snapshot["semantics"]["eq_missing_count"] == 1


def test_sc002_snapshot_rejects_security_deletion_flag():
    snapshot = _snapshot(
        security_raw=_security_gzip(deletion_symbol="S0100")
    )
    assert snapshot["status"] == "SEMANTICS_INELIGIBLE"
    assert snapshot["semantics"]["deletion_flag_conflict_count"] == 1
    assert snapshot["promotion_gates"][
        "projected_deletion_flags_allowed"
    ] is False


def test_sc002_mapping_change_diagnostics_detects_industry_delta():
    first = _snapshot()
    second = json.loads(json.dumps(first))
    second["mapping_rows"][0]["industry"] = "Changed Industry"
    second["mapping_sha256"] = digest(second["mapping_rows"])
    second.pop("snapshot_sha256", None)
    second["snapshot_sha256"] = digest(second)

    delta = mapping_change_diagnostics(first, second)
    assert delta["added_identity_count"] == 0
    assert delta["removed_identity_count"] == 0
    assert delta["industry_changed_identity_count"] == 1
    assert delta["mapping_sha_changed"] is True


def _fake_ready_snapshot(index):
    rows = [
        {
            "symbol": "TEST",
            "isin": "INE000000001",
            "company_name": "Test Ltd",
            "industry": f"Industry {index}",
            "parent_series": "EQ",
            "security_series": "EQ",
            "security_name": "TEST LTD",
            "deletion_flag": "N",
        }
    ]
    snapshot = {
        "status": "READY",
        "mapping_rows": rows,
        "mapping_sha256": digest(rows),
        "semantics": {
            "mapped_eq_count": 1,
            "dummy_count": 0,
        },
    }
    snapshot["snapshot_sha256"] = digest(snapshot)
    return snapshot


def test_sc002_ledger_idempotence_and_readiness_gate():
    ledger = new_industry_source_ledger()
    target_sessions = [
        "2026-10-01",
        "2026-10-01",
        "2026-10-02",
        "2026-10-02",
        "2026-10-05",
    ]
    for index, target in enumerate(target_sessions):
        observation = f"2026-10-{index + 2:02d}"
        snapshot = _fake_ready_snapshot(index)
        ledger, attempt = append_industry_attempt(
            ledger,
            observation_date=observation,
            target_session_date=target,
            sc001_attempt_sha256=f"{index + 201:064x}",
            captured_at_utc=f"{observation}T14:30:00+00:00",
            constituent_status="READY",
            constituent_raw_sha256=f"{index + 1:064x}",
            constituent_raw_path=f"raw/c{index}.csv",
            security_status="READY",
            security_raw_sha256=f"{index + 101:064x}",
            security_raw_path=f"raw/s{index}.csv.gz",
            snapshot=snapshot,
            snapshot_path=f"snapshots/{index}.json.gz",
            change_diagnostics={},
        )
        assert attempt is not None

    validate_industry_source_ledger(ledger)
    summary = industry_readiness_summary(ledger)
    assert summary["distinct_ready_observation_date_count"] == 5
    assert summary["distinct_ready_target_session_count"] == 3
    assert summary["prospective_industry_source_capture_ready"] is True
    assert summary["factor_automatically_enabled"] is False

    duplicate, attempt = append_industry_attempt(
        ledger,
        observation_date="2026-10-06",
        target_session_date="2026-10-05",
        sc001_attempt_sha256=f"{205:064x}",
        captured_at_utc="2026-10-06T15:00:00+00:00",
        constituent_status="READY",
        constituent_raw_sha256=f"{5:064x}",
        constituent_raw_path="raw/duplicate.csv",
        security_status="READY",
        security_raw_sha256=f"{105:064x}",
        security_raw_path="raw/duplicate.gz",
        snapshot=_fake_ready_snapshot(99),
        snapshot_path="snapshots/duplicate.json.gz",
        change_diagnostics={},
    )
    assert attempt is None
    assert duplicate == ledger


def test_sc002_latest_sc001_target_allows_same_observation_date():
    sc001 = {
        "attempts": [
            {
                "seq": 1,
                "session_date": "2026-10-01",
                "captured_at_utc": "2026-10-01T12:30:00+00:00",
                "eligible_before_cutoff": True,
            },
            {
                "seq": 2,
                "session_date": "2026-10-02",
                "captured_at_utc": "2026-10-02T12:30:00+00:00",
                "eligible_before_cutoff": True,
            },
        ]
    }
    target = latest_eligible_sc001_target(
        sc001,
        observation_date="2026-10-02",
    )
    assert target["session_date"] == "2026-10-02"


def test_checked_in_empty_sc002_state_is_canonical():
    root = Path(__file__).resolve().parents[1]
    ledger = json.loads(
        (
            root
            / "research/prospective/rm001-sc002/source-ledger.json"
        ).read_text(encoding="utf-8")
    )
    summary = json.loads(
        (
            root
            / "research/prospective/rm001-sc002/readiness-summary.json"
        ).read_text(encoding="utf-8")
    )
    validate_industry_source_ledger(ledger)
    assert industry_readiness_summary(ledger) == summary
