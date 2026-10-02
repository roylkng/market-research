import csv
import gzip
import io
from datetime import UTC, datetime, timedelta

import pytest

from marketlab.rm001_d010_r1 import parse_submission_timestamp
from marketlab.rm001_d013 import (
    IST,
    _nic_exposure,
    attach_historical_availability,
    attach_isin,
    audit_timeline,
    build_prior_security_sources,
    deterministic_public_time_sample,
    evaluate_public_time_semantics,
    match_public_announcement,
    select_filing_asof,
)


def _filing(
    *,
    year="FY2024-25",
    identity="CIN:L000000000000000001",
    app_id="APP1",
    symbol="TEST",
    submitted="31-Jul-2025 18:55:09",
    start="2024-04-01",
    end="2025-03-31",
    nic=None,
):
    return {
        "year": year,
        "stable_identity": identity,
        "app_id": app_id,
        "symbol": symbol,
        "cin": identity.removeprefix("CIN:"),
        "submission_timestamp_raw": submitted,
        "submission_timestamp_parsed": parse_submission_timestamp(submitted),
        "submission_timestamp_has_timezone": False,
        "reporting_period_start": start,
        "reporting_period_end": end,
        "nic": nic
        or {
            "status": "READY_SINGLE_NIC",
            "distinct_nic_count": 1,
            "weights": {"6201": 1.0},
            "explicit_rows": [],
        },
    }


def _announcement(
    *,
    seq_id="SEQ1",
    symbol="TEST",
    time_text="31-Jul-2025 18:55:10",
):
    return {
        "symbol": symbol,
        "seq_id": seq_id,
        "exchdisstime": time_text,
        "desc": "Updates",
        "attchmntText": (
            "Business Responsibility and Sustainability Reporting FY 2024-25"
        ),
        "attchmntFile": "test.pdf",
    }


def test_nic_exposure_single_and_turnover_weighted_multi():
    single = _nic_exposure(
        [
            {
                "niccodesoldbytheentity": "6201",
                "percentageoftotalturnovercontributedsoldbytheentity": "",
                "productservicesoldbytheentity": "Software",
            }
        ]
    )
    assert single["status"] == "READY_SINGLE_NIC"
    assert single["weights"] == {"6201": 1.0}

    multi = _nic_exposure(
        [
            {
                "niccodesoldbytheentity": "6201",
                "percentageoftotalturnovercontributedsoldbytheentity": "60",
                "productservicesoldbytheentity": "Software",
            },
            {
                "niccodesoldbytheentity": "6201",
                "percentageoftotalturnovercontributedsoldbytheentity": "10",
                "productservicesoldbytheentity": "Services",
            },
            {
                "niccodesoldbytheentity": "6311",
                "percentageoftotalturnovercontributedsoldbytheentity": "30",
                "productservicesoldbytheentity": "Hosting",
            },
        ]
    )
    assert multi["status"] == "READY_MULTI_NIC"
    assert multi["raw_turnover_total"] == pytest.approx(100.0)
    assert multi["weights"]["6201"] == pytest.approx(0.70)
    assert multi["weights"]["6311"] == pytest.approx(0.30)
    assert sum(multi["weights"].values()) == pytest.approx(1.0)


def test_multi_nic_missing_turnover_fails_closed():
    result = _nic_exposure(
        [
            {
                "niccodesoldbytheentity": "6201",
                "percentageoftotalturnovercontributedsoldbytheentity": "70",
                "productservicesoldbytheentity": "Software",
            },
            {
                "niccodesoldbytheentity": "6311",
                "percentageoftotalturnovercontributedsoldbytheentity": "",
                "productservicesoldbytheentity": "Hosting",
            },
        ]
    )
    assert result["status"] == "MULTI_NIC_INCOMPLETE_TURNOVER"
    assert result["weights"] == {}


def test_public_announcement_match_distinguishes_ist_from_utc():
    filing = _filing()
    match = match_public_announcement(
        filing=filing,
        payload=[_announcement()],
    )
    assert match["status"] == "MATCHED"
    observed = match["match"]
    assert observed["ist_signed_delta_seconds"] == pytest.approx(1.0)
    assert observed["ist_abs_delta_seconds"] == pytest.approx(1.0)
    assert observed["utc_abs_delta_seconds"] == pytest.approx(19_801.0)


def test_public_time_semantics_passes_tight_ist_sample_and_rejects_reuse():
    filings = []
    matches = {}
    for year_index, year in enumerate(("FY2023-24", "FY2024-25")):
        for index in range(4):
            filing = _filing(
                year=year,
                identity=f"CIN:{year_index}{index:017d}",
                app_id=f"APP-{year_index}-{index}",
                symbol=f"S{year_index}{index}",
            )
            filing["sample_score"] = f"{year_index}{index:063d}"
            filings.append(filing)
            matches[filing["sample_score"]] = {
                "status": "MATCHED",
                "candidate_count": 1,
                "match": {
                    "seq_id": f"SEQ-{year_index}-{index}",
                    "exchange_published_at_utc": (
                        "2025-07-31T13:25:10+00:00"
                    ),
                    "description": "Updates",
                    "attachment_text": "BRSR",
                    "ist_abs_delta_seconds": 1.0 + index,
                    "ist_signed_delta_seconds": 1.0 + index,
                    "utc_abs_delta_seconds": 19_801.0 + index,
                },
            }

    result = evaluate_public_time_semantics(
        sample=filings,
        matches=matches,
    )
    assert result["pass"] is True
    assert result["gates"]["utc_median_abs_delta_at_least_4h"] is True

    duplicate = dict(matches)
    second_key = filings[1]["sample_score"]
    duplicate[second_key] = {
        **duplicate[second_key],
        "match": {
            **duplicate[second_key]["match"],
            "seq_id": matches[filings[0]["sample_score"]]["match"]["seq_id"],
        },
    }
    result = evaluate_public_time_semantics(
        sample=filings,
        matches=duplicate,
    )
    assert result["gates"]["zero_reused_announcement_sequence_ids"] is False
    assert result["pass"] is False


def _security_master(day, *, symbol="TEST", isin="INE000000001"):
    fields = [
        "TckrSymb",
        "SctySrs",
        "FinInstrmNm",
        "ISIN",
        "IssdCptl",
        "ParVal",
        "DelFlg",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            "TckrSymb": symbol,
            "SctySrs": "EQ",
            "FinInstrmNm": "Test Limited",
            "ISIN": isin,
            "IssdCptl": "1000000",
            "ParVal": "10",
            "DelFlg": "N",
        }
    )
    return gzip.compress(text.getvalue().encode("utf-8"))


def test_prior_security_join_uses_strictly_previous_calendar_day():
    filing = _filing()
    available = attach_historical_availability([filing])[0]
    available_day = (
        datetime.fromisoformat(available["available_at_utc"])
        .astimezone(IST)
        .date()
    )

    requested = []

    def fetcher(url):
        requested.append(url)
        if available_day.strftime("%d%m%Y") in url:
            raise AssertionError("same-day Security File must never be requested")
        previous = available_day - timedelta(days=1)
        if previous.strftime("%d%m%Y") in url:
            return _security_master(previous.isoformat())
        return None

    sources = build_prior_security_sources(
        filings=[available],
        fetcher=fetcher,
    )
    joined, metrics = attach_isin([available], sources)
    assert metrics["exact_join_coverage"] == pytest.approx(1.0)
    assert metrics["ambiguous_join_count"] == 0
    assert joined[0]["isin"] == "INE000000001"
    assert joined[0]["isin_security_master_session"] == (
        available_day - timedelta(days=1)
    ).isoformat()


def test_asof_selector_newer_period_beats_late_old_period_amendment():
    base = datetime(2025, 7, 1, 12, tzinfo=UTC)
    old = {
        **_filing(
            app_id="OLD1",
            start="2023-04-01",
            end="2024-03-31",
        ),
        "available_at_utc": base.isoformat(),
        "availability_status": "READY",
        "isin": "INE000000001",
        "isin_status": "READY",
    }
    newer = {
        **_filing(
            app_id="NEW1",
            start="2024-04-01",
            end="2025-03-31",
        ),
        "available_at_utc": (base + timedelta(days=10)).isoformat(),
        "availability_status": "READY",
        "isin": "INE000000001",
        "isin_status": "READY",
    }
    late_old = {
        **_filing(
            app_id="OLD2",
            start="2023-04-01",
            end="2024-03-31",
        ),
        "available_at_utc": (base + timedelta(days=20)).isoformat(),
        "availability_status": "READY",
        "isin": "INE000000001",
        "isin_status": "READY",
    }
    selected = select_filing_asof(
        [old, newer, late_old],
        as_of_utc=base + timedelta(days=21),
    )
    assert selected is not None
    assert selected["app_id"] == "NEW1"


def test_timeline_audit_rejects_no_future_or_expired_selection():
    base = datetime(2025, 7, 1, 12, tzinfo=UTC)
    filing = {
        **_filing(),
        "available_at_utc": base.isoformat(),
        "availability_status": "READY",
        "isin": "INE000000001",
        "isin_status": "READY",
    }
    report = audit_timeline([filing])
    assert report["pass"] is True
    assert report["future_selection_count"] == 0
    assert report["expired_selection_count"] == 0


def test_deterministic_sample_is_hash_ordered_not_input_order():
    filings = [
        _filing(
            year="FY2023-24",
            identity=f"CIN:{index:018d}",
            app_id=f"APP{index}",
            symbol=f"S{index}",
        )
        for index in range(60)
    ]
    forward = deterministic_public_time_sample(filings, per_year=10)
    reverse = deterministic_public_time_sample(
        list(reversed(filings)),
        per_year=10,
    )
    assert [row["sample_score"] for row in forward] == [
        row["sample_score"] for row in reverse
    ]
    assert len(forward) == 10
