import csv
import gzip
import io
from datetime import UTC, date, datetime

import pytest

from marketlab.alpha import digest
from marketlab.rm001_size_source import (
    audit_security_master_session,
    parse_security_master_eq,
    run_d007_security_master_audit,
)


def _gzip(rows):
    fields = [
        "TckrSymb",
        "SctySrs",
        "FinInstrmNm",
        "ISIN",
        "IssdCptl",
        "ParVal",
        "DelFlg",
        "FreeFltCptl",
        "AsstClss",
        "ClssfctnTp",
        "FinInstrmClssfctn",
        "Indx",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return gzip.compress(text.getvalue().encode("utf-8"), mtime=0)


def _market_session(day="2026-09-25"):
    return {
        "session_date": day,
        "equities": [
            {
                "session_date": day,
                "symbol": "AAA",
                "isin": "INE000000001",
                "open_price": 99.0,
                "high_price": 102.0,
                "low_price": 98.0,
                "close_price": 100.0,
                "previous_close": 99.0,
                "volume": 100_000.0,
                "turnover_inr": 10_000_000.0,
                "trade_count": 1_000.0,
            },
            {
                "session_date": day,
                "symbol": "BBB",
                "isin": "INE000000002",
                "open_price": 49.0,
                "high_price": 52.0,
                "low_price": 48.0,
                "close_price": 50.0,
                "previous_close": 49.0,
                "volume": 100_000.0,
                "turnover_inr": 10_000_000.0,
                "trade_count": 1_000.0,
            },
        ],
    }


def _rows():
    return [
        {
            "TckrSymb": "AAA",
            "SctySrs": "EQ",
            "FinInstrmNm": "AAA LTD",
            "ISIN": "INE000000001",
            "IssdCptl": "1000000",
            "ParVal": "100",
            "DelFlg": "N",
            "FreeFltCptl": "",
            "AsstClss": "",
            "ClssfctnTp": "",
            "FinInstrmClssfctn": "",
            "Indx": "",
        },
        {
            "TckrSymb": "BBB",
            "SctySrs": "EQ",
            "FinInstrmNm": "BBB LTD",
            "ISIN": "INE000000002",
            "IssdCptl": "2000000",
            "ParVal": "1000",
            "DelFlg": "N",
            "FreeFltCptl": "",
            "AsstClss": "",
            "ClssfctnTp": "",
            "FinInstrmClssfctn": "",
            "Indx": "",
        },
    ]


def test_security_master_parser_keeps_exact_real_eq_identity():
    rows, diagnostics = parse_security_master_eq(
        _gzip(
            [
                *_rows(),
                {
                    **_rows()[0],
                    "TckrSymb": "DUMMY",
                    "ISIN": "DUMMYSAN001",
                },
                {
                    **_rows()[0],
                    "TckrSymb": "BEONLY",
                    "SctySrs": "BE",
                    "ISIN": "INE000000003",
                },
            ]
        ),
        session_date=date(2026, 9, 25),
    )
    assert [(row.symbol, row.isin) for row in rows] == [
        ("AAA", "INE000000001"),
        ("BBB", "INE000000002"),
    ]
    assert rows[0].issued_size == 1_000_000
    assert rows[1].par_value_raw == 1000
    assert diagnostics["dummy_eq_row_count"] == 1
    assert diagnostics["duplicate_real_eq_identity_count"] == 0


def test_session_audit_computes_total_market_cap_from_close_times_issued_size():
    rows, diagnostics = parse_security_master_eq(
        _gzip(_rows()),
        session_date=date(2026, 9, 25),
    )
    result = audit_security_master_session(
        market_session=_market_session(),
        security_rows=rows,
        parser_diagnostics=diagnostics,
        source_url="https://nsearchives.nseindia.com/x",
        raw_sha256="a" * 64,
    )
    assert result["exact_join_coverage"] == pytest.approx(1.0)
    assert result["positive_issued_size_coverage"] == pytest.approx(1.0)
    assert result["positive_market_cap_coverage"] == pytest.approx(1.0)
    assert result["market_cap_min_inr"] == pytest.approx(100_000_000.0)
    assert result["market_cap_max_inr"] == pytest.approx(100_000_000.0)
    assert result["positive_free_float_capital_coverage"] == pytest.approx(0.0)
    assert result["total_size_session_pass"] is True


def test_d007_fails_closed_when_exact_identity_coverage_below_gate():
    raw = _gzip(_rows()[:1])
    market = {
        "schema_version": 1,
        "panel_id": "TEST",
        "sessions": [_market_session()],
        "live_capital_allowed": False,
    }
    market["panel_sha256"] = digest(market)
    result = run_d007_security_master_audit(
        market_panel=market,
        fetcher=lambda url: raw,
        captured_at_utc=datetime(2026, 10, 1, tzinfo=UTC),
    )
    assert result["ready_session_count"] == 1
    assert result["minimum_exact_join_coverage"] == pytest.approx(0.5)
    assert result["total_market_cap_source_passed"] is False
    assert result["free_float_market_cap_source_passed"] is False
    assert result["future_return_labels_opened"] is False
    assert result["model_fit_performed"] is False


def test_d007_passes_total_size_and_does_not_promote_sector_or_free_float():
    raw = _gzip(_rows())
    market = {
        "schema_version": 1,
        "panel_id": "TEST",
        "sessions": [_market_session()],
        "live_capital_allowed": False,
    }
    market["panel_sha256"] = digest(market)
    result = run_d007_security_master_audit(
        market_panel=market,
        fetcher=lambda url: raw,
        captured_at_utc=datetime(2026, 10, 1, tzinfo=UTC),
    )
    assert result["total_market_cap_source_passed"] is True
    assert result["free_float_market_cap_source_passed"] is False
    assert result["sector_source_passed"] is False
    assert result["par_value_used_in_size_formula"] is False
