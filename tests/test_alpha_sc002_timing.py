import json
from pathlib import Path

from marketlab.alpha_prospective_futures_sources import (
    append_futures_source_probe,
    new_futures_source_ledger,
)
from marketlab.alpha_sc002_timing import publication_timing_summary


def _ready_zip(day: str) -> bytes:
    import csv
    import io
    import zipfile

    fields = [
        "TradDt",
        "Sgmt",
        "Src",
        "FinInstrmTp",
        "ISIN",
        "TckrSymb",
        "XpryDt",
        "FininstrmActlXpryDt",
        "OpnIntrst",
        "ChngInOpnIntrst",
        "TtlTradgVol",
        "TtlTrfVal",
        "OpnPric",
        "HghPric",
        "LwPric",
        "ClsPric",
        "SttlmPric",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            "TradDt": day,
            "Sgmt": "FO",
            "Src": "NSE",
            "FinInstrmTp": "STF",
            "ISIN": "",
            "TckrSymb": "TEST",
            "XpryDt": "2026-10-29",
            "FininstrmActlXpryDt": "2026-10-29",
            "OpnIntrst": "1000",
            "ChngInOpnIntrst": "100",
            "TtlTradgVol": "500",
            "TtlTrfVal": "5000000",
            "OpnPric": "100",
            "HghPric": "103",
            "LwPric": "99",
            "ClsPric": "102",
            "SttlmPric": "102",
        }
    )
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("fo.csv", text.getvalue())
    return raw.getvalue()


def _append_ready(ledger, day: str, captured: str):
    updated, attempt = append_futures_source_probe(
        ledger,
        session_date=day,
        captured_at_utc=captured,
        source_url="https://nsearchives.nseindia.com/fo.zip",
        raw=_ready_zip(day),
    )
    assert attempt is not None
    return updated


def test_sc002_timing_requires_three_distinct_ready_sessions():
    ledger = _append_ready(
        new_futures_source_ledger(),
        "2026-09-30",
        "2026-09-30T15:39:27+00:00",
    )
    summary = publication_timing_summary(ledger)
    assert summary["state"] == "INSUFFICIENT_EVIDENCE"
    assert summary["distinct_ready_session_count"] == 1
    assert summary["additional_distinct_ready_sessions_needed"] == 2
    assert summary["candidate_cutoff_ist"] is None
    assert summary["uses_stock_return_or_alpha_outcomes"] is False


def test_sc002_timing_uses_first_ready_per_session_only():
    ledger = new_futures_source_ledger()
    ledger = _append_ready(
        ledger,
        "2026-09-30",
        "2026-09-30T15:39:27+00:00",
    )
    # A later READY attempt on the same day is irrelevant to first publication.
    updated, _ = append_futures_source_probe(
        ledger,
        session_date="2026-09-30",
        captured_at_utc="2026-09-30T16:07:00+00:00",
        source_url="https://nsearchives.nseindia.com/fo.zip",
        raw=_ready_zip("2026-09-30"),
    )
    # append_futures_source_probe allows another post-cutoff attempt because the
    # session was never eligible_before_cutoff. The analyzer must keep the first.
    summary = publication_timing_summary(updated)
    assert summary["distinct_ready_session_count"] == 1
    assert summary["observations"][0]["captured_at_utc"].startswith(
        "2026-09-30T15:39:27"
    )


def test_sc002_timing_candidate_is_latest_plus_buffer_rounded_up():
    ledger = new_futures_source_ledger()
    ledger = _append_ready(
        ledger,
        "2026-09-30",
        "2026-09-30T15:39:27+00:00",
    )
    ledger = _append_ready(
        ledger,
        "2026-10-01",
        "2026-10-01T15:34:00+00:00",
    )
    ledger = _append_ready(
        ledger,
        "2026-10-05",
        "2026-10-05T15:47:10+00:00",
    )
    summary = publication_timing_summary(ledger)
    assert summary["state"] == "SOURCE_TIMING_READY_FOR_SUCCESSOR_DESIGN"
    assert summary["distinct_ready_session_count"] == 3
    assert summary["additional_distinct_ready_sessions_needed"] == 0
    # Latest is 21:17:10 IST, +30 minutes = 21:47:10, rounded -> 22:00.
    assert summary["candidate_cutoff_ist"] == "22:00:00"
    assert summary["candidate_cutoff_session_offset_days"] == 0
    assert summary["candidate_cutoff_basis_session"] == "2026-10-05"
    assert summary["successor_trial_cutoff_frozen"] is False



def test_sc002_timing_supports_first_ready_after_local_midnight():
    ledger = new_futures_source_ledger()
    ledger = _append_ready(
        ledger,
        "2026-09-30",
        "2026-09-30T18:45:00+00:00",
    )
    ledger = _append_ready(
        ledger,
        "2026-10-01",
        "2026-10-01T18:50:00+00:00",
    )
    ledger = _append_ready(
        ledger,
        "2026-10-05",
        "2026-10-05T19:05:00+00:00",
    )
    summary = publication_timing_summary(ledger)
    # 19:05 UTC is 00:35 IST on D+1. Add 30m -> 01:05, round -> 01:15 D+1.
    assert summary["candidate_cutoff_ist"] == "01:15:00"
    assert summary["candidate_cutoff_session_offset_days"] == 1
    assert (
        summary["observations"][-1][
            "local_seconds_after_session_midnight"
        ]
        > 24 * 3600
    )



def test_checked_in_sc002_timing_summary_matches_canonical_ledger():
    root = Path(__file__).resolve().parents[1]
    ledger = json.loads(
        (
            root
            / "research/prospective/ae001-sc002/source-ledger.json"
        ).read_text(encoding="utf-8")
    )
    expected = json.loads(
        (
            root
            / "research/prospective/ae001-sc002/publication-timing-summary.json"
        ).read_text(encoding="utf-8")
    )
    assert publication_timing_summary(ledger) == expected
