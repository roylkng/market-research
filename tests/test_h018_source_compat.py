import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h018_checkpoint_market as h018

HEADER = (
    "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,"
    "Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield\n"
)


def _row(name: str, day: str) -> bytes:
    return (
        HEADER + f"{name},{day},6864.15,6944.05,6864.15,6918.05,72.75,1.06,1,1,1,1,1\n"
    ).encode()


def test_h018_accepts_official_cnx500_hyphen_date_before_rename():
    parsed = h018._parse_nifty500_h018(_row("CNX 500", "28-11-2014"), date(2014, 11, 28))
    assert parsed == {"open": 6864.15, "close": 6918.05}


def test_h018_accepts_official_cnx500_slash_date_before_rename():
    parsed = h018._parse_nifty500_h018(_row("CNX 500", "09/06/2014"), date(2014, 6, 9))
    assert parsed == {"open": 6864.15, "close": 6918.05}


def test_h018_rejects_cnx500_name_on_or_after_rename():
    with pytest.raises(ValueError):
        h018._parse_nifty500_h018(_row("CNX 500", "09-11-2015"), date(2015, 11, 9))


def test_h018_rejects_wrong_source_date():
    with pytest.raises(ValueError):
        h018._parse_nifty500_h018(_row("CNX 500", "27/11/2014"), date(2014, 11, 28))


def test_h018_rejects_mixed_cnx_date_delimiters():
    with pytest.raises(ValueError):
        h018._parse_nifty500_h018(_row("CNX 500", "28/11-2014"), date(2014, 11, 28))


def test_h018_keeps_existing_nifty500_path():
    parsed = h018._parse_nifty500_h018(_row("Nifty 500", "16-11-2015"), date(2015, 11, 16))
    assert parsed == {"open": 6864.15, "close": 6918.05}
