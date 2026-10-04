from __future__ import annotations

from marketlab.ss001_shareholding_census import summarize_shareholding_master


def _row(
    *,
    symbol: str = "TEST",
    report_date: str,
    broadcast: str,
    record_id: int,
    revised: bool = False,
) -> dict:
    return {
        "symbol": symbol,
        "recordId": record_id,
        "date": report_date,
        "broadcastDate": broadcast,
        "xbrl": (
            "https://nsearchives.nseindia.com/corporate/xbrl/"
            f"SHP_{record_id}_WEB.xml"
        ),
        "revisedStatus": "Revised" if revised else "",
        "revisionDate": report_date if revised else "",
    }


def test_latest_revision_and_adjacent_prior_are_selected() -> None:
    payload = [
        _row(
            report_date="30-Jun-2026",
            broadcast="10-Jul-2026 10:00:00",
            record_id=1,
        ),
        _row(
            report_date="30-Jun-2026",
            broadcast="20-Jul-2026 10:00:00",
            record_id=2,
            revised=True,
        ),
        _row(
            report_date="30-Sep-2026",
            broadcast="03-Oct-2026 10:00:00",
            record_id=3,
        ),
    ]

    result = summarize_shareholding_master(
        payload,
        symbol="TEST",
        raw_sha256="a" * 64,
    )

    assert result["source_state"] == "READY"
    assert result["latest"]["report_date"] == "2026-09-30"
    assert result["latest"]["record_id"] == "3"
    assert result["prior"]["report_date"] == "2026-06-30"
    assert result["prior"]["record_id"] == "2"
    assert result["has_adjacent_prior"] is True


def test_empty_payload_is_explicit_no_standard_quarter() -> None:
    result = summarize_shareholding_master(
        [],
        symbol="TEST",
        raw_sha256="b" * 64,
    )
    assert result["source_state"] == "NO_STANDARD_QUARTER"
    assert result["latest"] is None
    assert result["has_adjacent_prior"] is False
