from __future__ import annotations

import csv
import gzip
import importlib.util
import io
from pathlib import Path

import pytest


def _load_sealer_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "seal_h024_prospective_events.py"
    spec = importlib.util.spec_from_file_location("seal_h024_prospective_events", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _security_master_gzip(rows: list[dict[str, str]]) -> bytes:
    fieldnames = [
        "TckrSymb",
        "SctySrs",
        "FinInstrmNm",
        "ISIN",
        "SctyTpFlg",
        "CallAuctnInd",
        "PrtdToTrad",
        "SctyStsNrmlMkt",
        "ElgbltyNrmlMkt",
        "ListgDt",
        "DelFlg",
        "Xchg",
        "FinInstrmTp",
        "InstrmTp",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return gzip.compress(buffer.getvalue().encode("utf-8"))


def _row(symbol: str, *, series: str = "EQ", isin: str = "INE000A01001") -> dict[str, str]:
    return {
        "TckrSymb": symbol,
        "SctySrs": series,
        "FinInstrmNm": f"{symbol} Limited",
        "ISIN": isin,
        "SctyTpFlg": "EQ",
        "CallAuctnInd": "0",
        "PrtdToTrad": "1",
        "SctyStsNrmlMkt": "1",
        "ElgbltyNrmlMkt": "1",
        "ListgDt": "20200101",
        "DelFlg": "N",
        "Xchg": "NSE",
        "FinInstrmTp": "STK",
        "InstrmTp": "EQ",
    }


def test_security_master_parser_keeps_only_requested_eq_rows() -> None:
    sealer = _load_sealer_module()
    raw = _security_master_gzip(
        [
            _row("AAA"),
            _row("AAA", series="BE", isin="INE000A01002"),
            _row("BBB"),
        ]
    )

    parsed = sealer._parse_security_master(raw, symbols={"AAA"})

    assert list(parsed) == ["AAA"]
    assert parsed["AAA"]["ISIN"] == "INE000A01001"
    assert parsed["AAA"]["SctySrs"] == "EQ"
    assert parsed["AAA"]["PrtdToTrad"] == "1"


def test_security_master_parser_fails_on_duplicate_requested_eq_row() -> None:
    sealer = _load_sealer_module()
    raw = _security_master_gzip(
        [_row("AAA", isin="INE000A01001"), _row("AAA", isin="INE000A01002")]
    )

    with pytest.raises(sealer.H024EventSealerError, match="duplicate.*AAA"):
        sealer._parse_security_master(raw, symbols={"AAA"})


def test_report_url_accepts_only_approved_nse_https_hosts() -> None:
    sealer = _load_sealer_module()

    assert (
        sealer._find_report_url(
            {"filePath": "https://nsearchives.nseindia.com/content/cm/security.csv.gz"}
        )
        == "https://nsearchives.nseindia.com/content/cm/security.csv.gz"
    )
    with pytest.raises(sealer.H024EventSealerError, match="unapproved"):
        sealer._find_report_url({"url": "https://example.com/security.csv.gz"})


def test_listing_date_parser_is_fail_closed_for_unknown_formats() -> None:
    sealer = _load_sealer_module()

    assert sealer._parse_listing_date("20260916").isoformat() == "2026-09-16"
    assert sealer._parse_listing_date("16-09-2026").isoformat() == "2026-09-16"
    assert sealer._parse_listing_date("") is None
    assert sealer._parse_listing_date("16/Sep/2026") is None
