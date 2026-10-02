from marketlab.rm001_d010_r2 import (
    analyze_cross_period_group,
    parse_reporting_date,
)


def _record(
    *,
    app_id,
    submitted,
    start,
    end,
    symbol="TEST",
    nic="12345",
):
    return {
        "app_id": app_id,
        "submission_timestamp_raw": submitted,
        "submission_timestamp": submitted,
        "symbol": symbol,
        "cin": "L00000000000000000001",
        "financial_year_start": start,
        "financial_year_end": end,
        "nic_codes": [nic],
        "nic_count": 1,
        "product_row_count": 1,
    }


def _group(records):
    return {
        "stable_identity": "CIN:L00000000000000000001",
        "records": records,
    }


def test_reporting_date_parser_supports_frozen_formats():
    assert parse_reporting_date("2024-04-01") == "2024-04-01"
    assert parse_reporting_date("01-APR-2024") == "2024-04-01"
    assert parse_reporting_date("01-04-2024") == "2024-04-01"
    assert parse_reporting_date("45383") is not None
    assert parse_reporting_date("n/a") is None


def test_distinct_nonoverlapping_annual_periods_pass():
    report = analyze_cross_period_group(
        _group(
            [
                _record(
                    app_id="1",
                    submitted="2024-07-01T10:00:00",
                    start="2023-04-01",
                    end="2024-03-31",
                ),
                _record(
                    app_id="2",
                    submitted="2025-07-01T10:00:00",
                    start="2024-04-01",
                    end="2025-03-31",
                ),
            ]
        )
    )
    assert report["distinct_period_count"] == 2
    assert report["gates"]["periods_non_overlapping"] is True
    assert report["candidate_pass"] is True


def test_overlapping_periods_fail_closed():
    report = analyze_cross_period_group(
        _group(
            [
                _record(
                    app_id="1",
                    submitted="2024-07-01T10:00:00",
                    start="2023-04-01",
                    end="2024-03-31",
                ),
                _record(
                    app_id="2",
                    submitted="2025-07-01T10:00:00",
                    start="2024-03-01",
                    end="2025-02-28",
                ),
            ]
        )
    )
    assert report["gates"]["periods_non_overlapping"] is False
    assert report["candidate_pass"] is False


def test_submission_before_period_end_fails_closed():
    report = analyze_cross_period_group(
        _group(
            [
                _record(
                    app_id="1",
                    submitted="2024-02-01T10:00:00",
                    start="2023-04-01",
                    end="2024-03-31",
                ),
                _record(
                    app_id="2",
                    submitted="2025-07-01T10:00:00",
                    start="2024-04-01",
                    end="2025-03-31",
                ),
            ]
        )
    )
    assert report["gates"]["all_filings_on_or_after_period_end"] is False
    assert report["candidate_pass"] is False


def test_same_period_amendments_do_not_resolve_cross_period_conflict():
    report = analyze_cross_period_group(
        _group(
            [
                _record(
                    app_id="1",
                    submitted="2024-07-01T10:00:00",
                    start="2023-04-01",
                    end="2024-03-31",
                ),
                _record(
                    app_id="2",
                    submitted="2024-07-02T10:00:00",
                    start="2023-04-01",
                    end="2024-03-31",
                ),
            ]
        )
    )
    assert report["distinct_period_count"] == 1
    assert report["gates"]["at_least_two_distinct_periods"] is False
    assert report["candidate_pass"] is False
