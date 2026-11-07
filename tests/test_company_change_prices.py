from __future__ import annotations

import io
import zipfile
from datetime import date

import pytest

from marketlab.company_change import ChangeError
from marketlab.company_change_prices import archive_close, parse_bhavcopy, quote_session
from marketlab.company_change_store import EvidenceStore

IDENTITY = {"symbol": "TEST", "isin": "INE000A01001", "scope": "CONSOLIDATED"}
NOW = "2026-11-07T18:00:00+00:00"
DAY = date(2026, 11, 6)


def source(*, content_date="2026-11-06", ticker="TEST", isin="INE000A01001", price="70.25", volume="1234", duplicates=False):
    text = "TradDt,ISIN,TckrSymb,SctySrs,Sgmt,Src,FinInstrmTp,ClsPric,TtlTradgVol\n"
    row = f"{content_date},{isin},{ticker},EQ,CM,NSE,STK,{price},{volume}\n"
    text += row + (row if duplicates else "")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BhavCopy_NSE_CM_0_0_0_20261106_F_0000.csv", text)
    return buffer.getvalue()


def test_close_preserves_session_date_not_fake_intraday_timestamp():
    quote = parse_bhavcopy(source(), IDENTITY, DAY, NOW)
    assert quote["price"] == 70.25
    assert quote["quoted_at"] is None
    assert quote["session_date"] == "2026-11-06"
    assert quote["price_type"].startswith("OFFICIAL_SESSION_CLOSE")
    assert quote["source_line"] == 2
    assert quote_session(quote) == DAY


@pytest.mark.parametrize("change", [
    {"content_date": "2026-11-05"}, {"ticker": "OTHER"}, {"isin": "INE000A01002"},
    {"price": "NaN"}, {"price": "-5"}, {"price": "0"}, {"volume": "0"}, {"duplicates": True},
])
def test_invalid_close_sources_never_become_prices(change):
    with pytest.raises(ChangeError):
        parse_bhavcopy(source(**change), IDENTITY, DAY, NOW)


def test_future_or_stale_session_is_rejected():
    with pytest.raises(ChangeError, match="future or stale"):
        parse_bhavcopy(source(), IDENTITY, DAY, "2026-11-05T10:00:00Z")
    with pytest.raises(ChangeError, match="future or stale"):
        parse_bhavcopy(source(), IDENTITY, DAY, "2026-11-15T10:00:00Z")


def test_incompatible_archive_not_extracted_to_filesystem():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../unexpected.csv", "bad")
    with pytest.raises(ChangeError):
        parse_bhavcopy(buffer.getvalue(), IDENTITY, DAY, NOW)
    with pytest.raises(ChangeError):
        parse_bhavcopy(b"<html>unavailable</html>", IDENTITY, DAY, NOW)


def test_weekend_probe_uses_actual_source_date_and_retains_original(tmp_path):
    calls = []
    raw = source()
    def fetch(url, hosts):
        calls.append(url)
        if "20261107" in url:
            raise ChangeError("No file")
        return raw, url
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        quote = archive_close(store, IDENTITY, fetcher=fetch)
        assert len(calls) == 2
        assert quote["session_date"] == "2026-11-06"
        assert len(quote["archive_probes"]) == 1
        assert store.read_blob(quote["raw_sha256"]) == raw


def test_invalid_retrieved_file_does_not_search_older_prices(tmp_path):
    calls = []
    def fetch(url, hosts):
        calls.append(url)
        return b"wrong", url
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store, pytest.raises(ChangeError):
        archive_close(store, IDENTITY, fetcher=fetch)
    assert len(calls) == 1
