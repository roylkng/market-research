import csv
import gzip
import io
from datetime import UTC, datetime

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_size_panel import build_rm001_v2_size_panel


def _security_file(rows):
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
    return gzip.compress(text.getvalue().encode(), mtime=0)


def _market():
    session = "2026-09-25"
    equities = []
    for index, close in enumerate((100.0, 50.0), start=1):
        equities.append(
            {
                "session_date": session,
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "open_price": close,
                "high_price": close * 1.01,
                "low_price": close * 0.99,
                "close_price": close,
                "previous_close": close,
                "volume": 100_000.0,
                "turnover_inr": 10_000_000.0,
                "trade_count": 1_000.0,
            }
        )
    panel = {
        "schema_version": 1,
        "panel_id": "TEST",
        "sessions": [{"session_date": session, "equities": equities}],
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _rows():
    return [
        {
            "TckrSymb": "S1",
            "SctySrs": "EQ",
            "FinInstrmNm": "S1 LTD",
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
            "TckrSymb": "S2",
            "SctySrs": "EQ",
            "FinInstrmNm": "S2 LTD",
            "ISIN": "INE000000002",
            "IssdCptl": "4000000",
            "ParVal": "100",
            "DelFlg": "N",
            "FreeFltCptl": "",
            "AsstClss": "",
            "ClssfctnTp": "",
            "FinInstrmClssfctn": "",
            "Indx": "",
        },
    ]


def test_size_panel_uses_close_times_issued_size_and_exact_identity():
    raw = _security_file(_rows())
    panel = build_rm001_v2_size_panel(
        market_panel=_market(),
        fetcher=lambda url: raw,
        captured_at_utc=datetime(2026, 10, 1, tzinfo=UTC),
    )
    assert panel["session_count"] == 1
    assert panel["row_count"] == 2
    rows = panel["sessions"][0]["rows"]
    assert rows[0]["total_market_cap_inr"] == pytest.approx(100_000_000.0)
    assert rows[1]["total_market_cap_inr"] == pytest.approx(200_000_000.0)
    assert panel["prospective_source_timing_verified"] is False


def test_size_panel_fails_closed_when_source_unavailable():
    with pytest.raises(AlphaContractError, match="unavailable"):
        build_rm001_v2_size_panel(
            market_panel=_market(),
            fetcher=lambda url: None,
            captured_at_utc=datetime(2026, 10, 1, tzinfo=UTC),
        )


def test_size_panel_fails_closed_below_d007_join_gate():
    raw = _security_file(_rows()[:1])
    with pytest.raises(AlphaContractError, match="join coverage"):
        build_rm001_v2_size_panel(
            market_panel=_market(),
            fetcher=lambda url: raw,
            captured_at_utc=datetime(2026, 10, 1, tzinfo=UTC),
        )
