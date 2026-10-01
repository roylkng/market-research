import csv
import gzip
import io
import zipfile

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_size_timing import (
    append_size_source_probe,
    new_size_source_ledger,
    size_timing_summary,
    target_ready_observed,
    validate_size_source_ledger,
)


def _market_zip(day: str) -> bytes:
    fields = [
        "TradDt",
        "Sgmt",
        "Src",
        "FinInstrmTp",
        "ISIN",
        "TckrSymb",
        "SctySrs",
        "OpnPric",
        "HghPric",
        "LwPric",
        "ClsPric",
        "PrvsClsgPric",
        "TtlTradgVol",
        "TtlTrfVal",
        "TtlNbOfTxsExctd",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    for symbol, isin, close in (
        ("AAA", "INE000000001", 100),
        ("BBB", "INE000000002", 50),
    ):
        writer.writerow(
            {
                "TradDt": day,
                "Sgmt": "CM",
                "Src": "NSE",
                "FinInstrmTp": "STK",
                "ISIN": isin,
                "TckrSymb": symbol,
                "SctySrs": "EQ",
                "OpnPric": str(close - 1),
                "HghPric": str(close + 1),
                "LwPric": str(close - 2),
                "ClsPric": str(close),
                "PrvsClsgPric": str(close - 1),
                "TtlTradgVol": "100000",
                "TtlTrfVal": "10000000",
                "TtlNbOfTxsExctd": "1000",
            }
        )
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("cm.csv", text.getvalue())
    return raw.getvalue()


def _security_gzip():
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
    writer.writerows(
        [
            {
                "TckrSymb": "AAA",
                "SctySrs": "EQ",
                "FinInstrmNm": "AAA LTD",
                "ISIN": "INE000000001",
                "IssdCptl": "1000000",
                "ParVal": "10",
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
                "ParVal": "10",
                "DelFlg": "N",
                "FreeFltCptl": "",
                "AsstClss": "",
                "ClssfctnTp": "",
                "FinInstrmClssfctn": "",
                "Indx": "",
            },
        ]
    )
    return gzip.compress(text.getvalue().encode("utf-8"), mtime=0)


def _sc001_attempt(session="2026-10-01"):
    market_raw = _market_zip(session)
    attempt = {
        "seq": 1,
        "session_date": session,
        "captured_at_utc": f"{session}T12:00:00+00:00",
        "decision_cutoff_utc": f"{session}T13:00:00+00:00",
        "captured_before_or_at_cutoff": True,
        "market": {
            "status": "READY",
            "raw_sha256": __import__("hashlib").sha256(market_raw).hexdigest(),
        },
        "delivery": {"status": "READY"},
        "eligible_before_cutoff": True,
        "live_capital_allowed": False,
    }
    attempt["attempt_sha256"] = digest(attempt)
    return attempt, market_raw


def test_size_source_ready_before_preopen_cutoff():
    target, market_raw = _sc001_attempt()
    ledger, attempt = append_size_source_probe(
        new_size_source_ledger(),
        sc001_attempt=target,
        observation_date="2026-10-02",
        captured_at_utc="2026-10-02T02:50:00+00:00",
        market_raw=market_raw,
        security_raw=_security_gzip(),
        source_url="https://nsearchives.nseindia.com/security.csv.gz",
    )
    assert attempt is not None
    assert attempt["source_status"] == "READY"
    assert attempt["ready_before_preopen_cutoff"] is True
    assert attempt["diagnostics"]["total_size_session_pass"] is True
    assert target_ready_observed(ledger, "2026-10-01") is True
    validate_size_source_ledger(ledger)


def test_size_source_quality_failure_is_not_ready():
    target, market_raw = _sc001_attempt()
    bad = gzip.compress(b"TckrSymb,SctySrs\nAAA,EQ\n", mtime=0)
    _, attempt = append_size_source_probe(
        new_size_source_ledger(),
        sc001_attempt=target,
        observation_date="2026-10-02",
        captured_at_utc="2026-10-02T02:00:00+00:00",
        market_raw=market_raw,
        security_raw=bad,
        source_url="x",
    )
    assert attempt is not None
    assert attempt["source_status"] == "PARSER_REJECTED"
    assert attempt["ready_before_preopen_cutoff"] is False


def test_size_source_rejects_tampered_sc001_market_bytes():
    target, _ = _sc001_attempt()
    with pytest.raises(AlphaContractError, match="market bytes hash mismatch"):
        append_size_source_probe(
            new_size_source_ledger(),
            sc001_attempt=target,
            observation_date="2026-10-02",
            captured_at_utc="2026-10-02T02:00:00+00:00",
            market_raw=b"tampered",
            security_raw=_security_gzip(),
            source_url="x",
        )


def test_size_timing_summary_requires_three_distinct_ready_sessions():
    ledger = new_size_source_ledger()
    for target_session, observation_date in (
        ("2026-10-01", "2026-10-02"),
        ("2026-10-02", "2026-10-03"),
        ("2026-10-03", "2026-10-04"),
    ):
        target, market_raw = _sc001_attempt(target_session)
        ledger, _ = append_size_source_probe(
            ledger,
            sc001_attempt=target,
            observation_date=observation_date,
            captured_at_utc=f"{observation_date}T02:00:00+00:00",
            market_raw=market_raw,
            security_raw=_security_gzip(),
            source_url="x",
        )
    summary = size_timing_summary(ledger)
    assert summary["distinct_ready_before_cutoff_session_count"] == 3
    assert summary["additional_ready_sessions_needed"] == 0
    assert summary["prospective_size_source_timing_ready"] is True
    assert summary["prospective_size_use_enabled"] is False


def test_size_source_rejects_pre_start_observation():
    target, market_raw = _sc001_attempt("2026-09-30")
    with pytest.raises(AlphaContractError, match="frozen start"):
        append_size_source_probe(
            new_size_source_ledger(),
            sc001_attempt=target,
            observation_date="2026-10-01",
            captured_at_utc="2026-10-01T02:00:00+00:00",
            market_raw=market_raw,
            security_raw=None,
            source_url="x",
        )
