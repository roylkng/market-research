import csv
import io
import zipfile

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_prospective_futures_sources import (
    append_futures_source_probe,
    new_futures_source_ledger,
    session_already_eligible,
    validate_futures_source_ledger,
)


def _fo_zip(day: str) -> bytes:
    fields = [
        "TradDt",
        "Sgmt",
        "Src",
        "FinInstrmTp",
        "FinInstrmId",
        "TckrSymb",
        "XpryDt",
        "FininstrmActlXpryDt",
        "SttlmPric",
        "PrvsClsgPric",
        "UndrlygPric",
        "OpnIntrst",
        "ChngInOpnIntrst",
        "TtlTradgVol",
        "TtlTrfVal",
        "TtlNbOfTxsExctd",
        "NewBrdLotQty",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    for index, expiry in enumerate(("2026-10-29", "2026-11-26"), start=1):
        writer.writerow(
            {
                "TradDt": day,
                "Sgmt": "FO",
                "Src": "NSE",
                "FinInstrmTp": "STF",
                "FinInstrmId": f"FUT{index}",
                "TckrSymb": "TEST",
                "XpryDt": expiry,
                "FininstrmActlXpryDt": expiry,
                "SttlmPric": str(101 + index),
                "PrvsClsgPric": str(100 + index),
                "UndrlygPric": "100",
                "OpnIntrst": "100000",
                "ChngInOpnIntrst": "1000",
                "TtlTradgVol": "500",
                "TtlTrfVal": "5000000",
                "TtlNbOfTxsExctd": "100",
                "NewBrdLotQty": "50",
            }
        )
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("fo.csv", text.getvalue())
    return raw.getvalue()


def test_sc002_ready_before_cutoff_is_eligible():
    ledger, attempt = append_futures_source_probe(
        new_futures_source_ledger(),
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T12:45:00+00:00",
        source_url="https://nsearchives.nseindia.com/fo.zip",
        raw=_fo_zip("2026-09-30"),
    )
    assert attempt is not None
    assert attempt["futures"]["status"] == "READY"
    assert attempt["eligible_before_cutoff"] is True
    assert session_already_eligible(ledger, "2026-09-30") is True
    validate_futures_source_ledger(ledger)


def test_sc002_ready_after_cutoff_is_not_eligible():
    ledger, attempt = append_futures_source_probe(
        new_futures_source_ledger(),
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T13:01:00+00:00",
        source_url="https://nsearchives.nseindia.com/fo.zip",
        raw=_fo_zip("2026-09-30"),
    )
    assert attempt is not None
    assert attempt["futures"]["status"] == "READY"
    assert attempt["eligible_before_cutoff"] is False
    assert session_already_eligible(ledger, "2026-09-30") is False


def test_sc002_missing_source_is_recorded_not_eligible():
    _, attempt = append_futures_source_probe(
        new_futures_source_ledger(),
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T12:00:00+00:00",
        source_url="https://nsearchives.nseindia.com/fo.zip",
        raw=None,
    )
    assert attempt is not None
    assert attempt["futures"]["status"] == "UNAVAILABLE"
    assert attempt["eligible_before_cutoff"] is False


def test_sc002_success_makes_later_probe_idempotent():
    ledger, _ = append_futures_source_probe(
        new_futures_source_ledger(),
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T12:00:00+00:00",
        source_url="x",
        raw=_fo_zip("2026-09-30"),
    )
    second, attempt = append_futures_source_probe(
        ledger,
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T12:30:00+00:00",
        source_url="x",
        raw=None,
    )
    assert attempt is None
    assert second == ledger


def test_sc002_rejects_pre_start_probe():
    with pytest.raises(AlphaContractError, match="start boundary"):
        append_futures_source_probe(
            new_futures_source_ledger(),
            session_date="2026-09-29",
            captured_at_utc="2026-09-29T12:00:00+00:00",
            source_url="x",
            raw=None,
        )
