import csv
import io
import zipfile

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_prospective_sources import new_source_ledger
from marketlab.alpha_sc003_preopen import (
    append_sc003_probe,
    latest_completed_sc001_target,
    new_sc003_ledger,
    preopen_readiness_summary,
    target_ready_observed,
    validate_sc003_ledger,
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


def _sc001():
    ledger = new_source_ledger()
    ledger.pop("ledger_sha256")
    ledger["attempts"] = [
        {
            "seq": 1,
            "session_date": "2026-09-30",
            "captured_at_utc": "2026-09-30T12:50:00+00:00",
            "decision_cutoff_utc": "2026-09-30T13:00:00+00:00",
            "captured_before_or_at_cutoff": True,
            "market": {"status": "READY"},
            "delivery": {"status": "READY"},
            "eligible_before_cutoff": True,
            "live_capital_allowed": False,
        },
        {
            "seq": 2,
            "session_date": "2026-10-01",
            "captured_at_utc": "2026-10-01T12:00:00+00:00",
            "decision_cutoff_utc": "2026-10-01T13:00:00+00:00",
            "captured_before_or_at_cutoff": True,
            "market": {"status": "READY"},
            "delivery": {"status": "READY"},
            "eligible_before_cutoff": True,
            "live_capital_allowed": False,
        },
    ]
    from marketlab.alpha import digest

    for attempt in ledger["attempts"]:
        attempt["attempt_sha256"] = digest(attempt)
    ledger["attempt_count"] = len(ledger["attempts"])
    ledger["ledger_sha256"] = digest(ledger)
    return ledger


def test_sc003_targets_latest_prior_sc001_eligible_session():
    target = latest_completed_sc001_target(
        _sc001(),
        observation_date="2026-10-02",
    )
    assert target["session_date"] == "2026-10-01"


def test_sc003_ready_before_0830_is_eligible_for_successor_design():
    target = latest_completed_sc001_target(
        _sc001(),
        observation_date="2026-10-02",
    )
    ledger, attempt = append_sc003_probe(
        new_sc003_ledger(),
        sc001_attempt=target,
        observation_date="2026-10-02",
        captured_at_utc="2026-10-02T02:50:00+00:00",
        source_url="https://nsearchives.nseindia.com/fo.zip",
        raw=_fo_zip("2026-10-01"),
    )
    assert attempt is not None
    assert attempt["source_status"] == "READY"
    assert attempt["ready_before_preopen_cutoff"] is True
    assert target_ready_observed(ledger, "2026-10-01") is True
    validate_sc003_ledger(ledger)


def test_sc003_ready_after_0830_is_recorded_but_not_preopen_ready():
    target = latest_completed_sc001_target(
        _sc001(),
        observation_date="2026-10-02",
    )
    ledger, attempt = append_sc003_probe(
        new_sc003_ledger(),
        sc001_attempt=target,
        observation_date="2026-10-02",
        captured_at_utc="2026-10-02T03:01:00+00:00",
        source_url="x",
        raw=_fo_zip("2026-10-01"),
    )
    assert attempt is not None
    assert attempt["source_status"] == "READY"
    assert attempt["ready_before_preopen_cutoff"] is False
    assert target_ready_observed(ledger, "2026-10-01") is True


def test_sc003_ready_observation_makes_target_idempotent():
    target = latest_completed_sc001_target(
        _sc001(),
        observation_date="2026-10-02",
    )
    ledger, _ = append_sc003_probe(
        new_sc003_ledger(),
        sc001_attempt=target,
        observation_date="2026-10-02",
        captured_at_utc="2026-10-02T02:00:00+00:00",
        source_url="x",
        raw=_fo_zip("2026-10-01"),
    )
    second, attempt = append_sc003_probe(
        ledger,
        sc001_attempt=target,
        observation_date="2026-10-02",
        captured_at_utc="2026-10-02T02:30:00+00:00",
        source_url="x",
        raw=None,
    )
    assert attempt is None
    assert second == ledger


def test_sc003_summary_requires_three_distinct_preopen_ready_sessions():
    ledger = new_sc003_ledger()
    sc001 = _sc001()
    targets = [
        dict(sc001["attempts"][0], session_date="2026-09-29"),
        dict(sc001["attempts"][0], session_date="2026-09-30"),
        dict(sc001["attempts"][1], session_date="2026-10-01"),
    ]
    from marketlab.alpha import digest

    for target in targets:
        target.pop("attempt_sha256", None)
        target["attempt_sha256"] = digest(target)

    for observation_date, target in zip(
        ("2026-09-30", "2026-10-01", "2026-10-02"),
        targets,
        strict=True,
    ):
        ledger, _ = append_sc003_probe(
            ledger,
            sc001_attempt=target,
            observation_date=observation_date,
            captured_at_utc=f"{observation_date}T02:00:00+00:00",
            source_url="x",
            raw=_fo_zip(target["session_date"]),
        )

    summary = preopen_readiness_summary(ledger)
    assert summary["distinct_ready_before_cutoff_session_count"] == 3
    assert summary["additional_ready_sessions_needed"] == 0
    assert summary["successor_preopen_design_ready"] is True
    assert summary["successor_trial_frozen"] is False


def test_sc003_refuses_observation_before_frozen_start():
    target = latest_completed_sc001_target(
        _sc001(),
        observation_date="2026-10-01",
    )
    with pytest.raises(AlphaContractError, match="frozen start"):
        append_sc003_probe(
            new_sc003_ledger(),
            sc001_attempt=target,
            observation_date="2026-10-01",
            captured_at_utc="2026-10-01T02:00:00+00:00",
            source_url="x",
            raw=None,
        )
