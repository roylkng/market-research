from marketlab.rm001_d010_r1 import (
    analyze_duplicate_rows,
    parse_submission_timestamp,
)


def _general(
    *,
    app_id,
    timestamp,
    symbol="TEST",
    cin="L00000000000000000001",
    start="2023-04-01",
    end="2024-03-31",
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


def test_submission_timestamp_parser_supports_frozen_formats():
    assert parse_submission_timestamp(
        "01-APR-2024 12:30:45"
    ) == "2024-04-01T12:30:45"
    assert parse_submission_timestamp(
        "2024-04-01T12:30:45"
    ) == "2024-04-01T12:30:45"
    assert parse_submission_timestamp("45383.5") is not None
    assert parse_submission_timestamp("n/a") is None


def test_duplicate_revision_chain_passes_when_fully_orderable():
    report = analyze_duplicate_rows(
        year="TEST",
        general_rows=[
            _general(app_id="1", timestamp="01-APR-2024 10:00:00"),
            _general(app_id="2", timestamp="02-APR-2024 11:00:00"),
            _general(
                app_id="3",
                timestamp="03-APR-2024 12:00:00",
                cin="L00000000000000000002",
                symbol="OTHER",
            ),
        ],
        product_rows=[
            _product("1", "10001"),
            _product("2", "10002"),
            {
                **_product("3", "20001"),
                "symbsymbol": "OTHER",
            },
        ],
    )
    assert report["duplicate_group_count"] == 1
    assert report["duplicate_filing_record_count"] == 2
    assert report["deterministic_amendment_group_fraction"] == 1.0
    assert report["duplicate_filing_explicit_nic_fraction"] == 1.0
    assert report["year_pass"] is True
    group = report["duplicate_groups"][0]
    assert group["nic_changed_across_filings"] is True


def test_duplicate_timestamp_collision_fails_closed():
    report = analyze_duplicate_rows(
        year="TEST",
        general_rows=[
            _general(app_id="1", timestamp="01-APR-2024 10:00:00"),
            _general(app_id="2", timestamp="01-APR-2024 10:00:00"),
        ],
        product_rows=[
            _product("1"),
            _product("2"),
        ],
    )
    assert report["timestamp_collision_group_count"] == 1
    assert report["year_pass"] is False
    assert (
        report["gates"]["zero_timestamp_collisions"]
        is False
    )


def test_duplicate_missing_nic_fails_closed():
    report = analyze_duplicate_rows(
        year="TEST",
        general_rows=[
            _general(app_id="1", timestamp="01-APR-2024 10:00:00"),
            _general(app_id="2", timestamp="02-APR-2024 10:00:00"),
        ],
        product_rows=[_product("1")],
    )
    assert report["duplicate_filing_explicit_nic_fraction"] == 0.5
    assert report["year_pass"] is False


def test_symbol_change_same_cin_is_reported_not_automatically_failed():
    report = analyze_duplicate_rows(
        year="TEST",
        general_rows=[
            _general(
                app_id="1",
                timestamp="01-APR-2024 10:00:00",
                symbol="OLD",
            ),
            _general(
                app_id="2",
                timestamp="02-APR-2024 10:00:00",
                symbol="NEW",
            ),
        ],
        product_rows=[
            {
                **_product("1"),
                "symbsymbol": "OLD",
            },
            {
                **_product("2"),
                "symbsymbol": "NEW",
            },
        ],
    )
    assert report["symbol_change_group_count"] == 1
    assert report["year_pass"] is True
