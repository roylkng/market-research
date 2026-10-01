from datetime import date

from marketlab.alpha_d010_p2 import (
    PROBE_DATES,
    slb_archive_url,
    summarize_p2,
)


def test_d010_p2_url_is_exact_metadata_resolved_archive():
    assert slb_archive_url(date(2026, 9, 25)) == (
        "https://nsearchives.nseindia.com/archives/slbs/open_pos/"
        "slb_openpos_25092026.csv"
    )


def test_d010_p2_promotes_only_stable_ready_schema():
    attempts = [
        {
            "session_date": day.isoformat(),
            "response": {
                "status": "READY",
                "header": ["SYMBOL", "OPEN_POSITION"],
            },
        }
        for day in PROBE_DATES
    ]
    report = summarize_p2(attempts)
    assert report["ready_count"] == 3
    assert report["schema_count"] == 1
    assert report["status"] == "PROMOTE_P3_HISTORICAL_COVERAGE"


def test_d010_p2_rejects_schema_drift():
    attempts = []
    for index, day in enumerate(PROBE_DATES):
        attempts.append(
            {
                "session_date": day.isoformat(),
                "response": {
                    "status": "READY",
                    "header": (
                        ["SYMBOL", "OPEN_POSITION"]
                        if index < 2
                        else ["SYMBOL", "QTY"]
                    ),
                },
            }
        )
    report = summarize_p2(attempts)
    assert report["status"] == "READY_ALL_SESSIONS_SCHEMA_UNSTABLE"
