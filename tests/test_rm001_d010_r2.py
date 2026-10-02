from marketlab.rm001_d010_r2 import (
    analyze_cross_period_groups,
    parse_reporting_date,
)


def _general(
    *,
    app_id,
    timestamp,
    start,
    end,
    symbol="TEST",
    cin="L00000000000000000001",
):
    return {
        "appid": app_id,
        "tlasubmitteddt": timestamp,
        "symbsymbol": symbol,
        "corporateidentitynumbercinofthelistedentity": cin,
        "currentfinancialyearstartdate": start,
        "currentfinancialyearenddate": end,
    }


def _product(app_id, nic="12345"):
    return {
        "appid": app_id,
        "symbsymbol": "TEST",
        "niccodesoldbytheentity": nic,
    }


def test_reporting_date_parser_supports_frozen_formats():
    assert parse_reporting_date("2024-04-01") == "2024-04-01"
    assert parse_reporting_date("01-04-2024") == "2024-04-01"
    assert parse_reporting_date("01-Apr-2024") == "2024-04-01"
    assert parse_reporting_date("2024-04-01T12:00:00") == "2024-04-01"
    assert parse_reporting_date("bad") is None


def test_distinct_nonoverlapping_periods_pass():
    report = analyze_cross_period_groups(
        year="TEST",
        general_rows=[
            _general(
                app_id="1",
                timestamp="01-JUL-2024 10:00:00",
                start="2023-04-01",
                end="2024-03-31",
            ),
            _general(
                app_id="2",
                timestamp="01-JUL-2025 10:00:00",
                start="2024-04-01",
                end="2025-03-31",
            ),
        ],
        product_rows=[
            _product("1", "10001"),
            _product("2", "10001"),
        ],
        target_start="2024-04-01",
        target_end="2025-03-31",
    )
    assert report["cross_period_conflict_group_count"] == 1
    assert report["overlapping_period_pair_count"] == 0
    assert report["deterministic_period_partition_group_fraction"] == 1.0
    assert report["target_period_group_count"] == 1
    assert report["target_period_record_count"] == 1
    assert report["pass"] is True


def test_overlapping_reporting_periods_fail_closed():
    report = analyze_cross_period_groups(
        year="TEST",
        general_rows=[
            _general(
                app_id="1",
                timestamp="01-JUL-2024 10:00:00",
                start="2023-04-01",
                end="2024-06-30",
            ),
            _general(
                app_id="2",
                timestamp="01-JUL-2025 10:00:00",
                start="2024-04-01",
                end="2025-03-31",
            ),
        ],
        product_rows=[_product("1"), _product("2")],
        target_start="2024-04-01",
        target_end="2025-03-31",
    )
    assert report["overlapping_period_pair_count"] == 1
    assert report["pass"] is False


def test_amendments_inside_each_period_are_allowed_when_deterministic():
    report = analyze_cross_period_groups(
        year="TEST",
        general_rows=[
            _general(
                app_id="1",
                timestamp="01-JUL-2024 10:00:00",
                start="2023-04-01",
                end="2024-03-31",
            ),
            _general(
                app_id="2",
                timestamp="02-JUL-2024 10:00:00",
                start="2023-04-01",
                end="2024-03-31",
            ),
            _general(
                app_id="3",
                timestamp="01-JUL-2025 10:00:00",
                start="2024-04-01",
                end="2025-03-31",
            ),
        ],
        product_rows=[
            _product("1"),
            _product("2"),
            _product("3"),
        ],
        target_start="2024-04-01",
        target_end="2025-03-31",
    )
    assert report["cross_period_conflict_group_count"] == 1
    assert report["target_period_record_count"] == 1
    assert report["pass"] is True


def test_unparseable_period_fails_closed():
    report = analyze_cross_period_groups(
        year="TEST",
        general_rows=[
            _general(
                app_id="1",
                timestamp="01-JUL-2024 10:00:00",
                start="unknown",
                end="2024-03-31",
            ),
            _general(
                app_id="2",
                timestamp="01-JUL-2025 10:00:00",
                start="2024-04-01",
                end="2025-03-31",
            ),
        ],
        product_rows=[_product("1"), _product("2")],
        target_start="2024-04-01",
        target_end="2025-03-31",
    )
    assert report["parseable_period_record_fraction"] == 0.5
    assert report["pass"] is False
