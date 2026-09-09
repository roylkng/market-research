import io
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h019_complete_input_universe as h019


def archive(member: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        output.writestr(member, "SYMBOL,SERIES\n")
    return buffer.getvalue()


def test_legacy_bhavcopy_date_comes_from_member_name() -> None:
    assert h019.legacy_bhavcopy_source_date(archive("cm31DEC2020bhav.csv")) == date(
        2020, 12, 31
    )


def test_legacy_bhavcopy_date_accepts_archive_subdirectory() -> None:
    assert h019.legacy_bhavcopy_source_date(archive("archive/cm30JUN2021bhav.csv")) == date(
        2021, 6, 30
    )


def test_unexpected_member_name_fails_closed() -> None:
    with pytest.raises(h019.H019InputError, match="unexpected"):
        h019.legacy_bhavcopy_source_date(archive("equities.csv"))


def test_multiple_members_fail_closed() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        output.writestr("cm31DEC2020bhav.csv", "x")
        output.writestr("extra.csv", "y")
    with pytest.raises(h019.H019InputError, match="exactly one"):
        h019.legacy_bhavcopy_source_date(buffer.getvalue())
