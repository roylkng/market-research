from marketlab.alpha_d010_p1 import (
    MetadataProbe,
    extract_daily_report_metadata,
    short_archive_url,
    summarize_p1,
)


def test_d010_p1_short_archive_url_uses_resolved_official_path():
    assert short_archive_url.__module__
    assert short_archive_url(
        __import__("datetime").date(2026, 9, 25)
    ) == (
        "https://nsearchives.nseindia.com/archives/equities/"
        "shortSelling/shortselling_25092026.csv"
    )


def test_d010_p1_extracts_short_and_slb_metadata():
    payload = {
        "data": [
            {
                "fileKey": "CM-SHORT-SELLING",
                "displayName": "CM Short Selling",
                "filePath": "https://nsearchives.nseindia.com/content/cm",
                "fileActlName": "shortselling_01102026.csv",
                "tradingDate": "01-Oct-2026",
            },
            {
                "fileKey": "SLB-OPEN",
                "displayName": "SLB Daily Open Positions",
                "filePath": "https://nsearchives.nseindia.com/content/slb",
                "fileActlName": "slb_openpos_01102026.csv",
                "tradingDate": "01-Oct-2026",
            },
        ]
    }
    result = extract_daily_report_metadata(
        MetadataProbe(
            key="CM",
            raw_sha256="a" * 64,
            payload=payload,
        )
    )
    assert result["matched_object_count"] == 2
    assert any(
        row["short_selling_match"] for row in result["matches"]
    )
    assert any(
        row["slb_open_position_match"] for row in result["matches"]
    )
    assert all(
        row["explicit_download_url"].startswith(
            "https://nsearchives.nseindia.com/"
        )
        for row in result["matches"]
    )


def test_d010_p1_summary_promotes_short_and_unique_slb_metadata(monkeypatch):
    from marketlab import alpha_d010_p1 as module

    short_attempts = [
        {
            "session_date": day.isoformat(),
            "response": {"status": "READY"},
        }
        for day in module.PROBE_DATES
    ]
    metadata_results = [
        {
            "key": "CM",
            "raw_sha256": "a" * 64,
            "matches": [],
        },
        {
            "key": "SLB",
            "raw_sha256": "b" * 64,
            "matches": [
                {
                    "metadata": {},
                    "short_selling_match": False,
                    "slb_open_position_match": True,
                    "explicit_download_url": (
                        "https://nsearchives.nseindia.com/"
                        "content/slb/slb_openpos_01102026.csv"
                    ),
                }
            ],
        },
        {
            "key": "SLBS",
            "raw_sha256": "c" * 64,
            "matches": [],
        },
    ]
    report = summarize_p1(
        short_attempts=short_attempts,
        metadata_results=metadata_results,
    )
    assert report["short_selling"]["status"] == (
        "PROMOTE_P2_HISTORICAL_COVERAGE"
    )
    assert report["slb_open_positions"]["status"] == (
        "UNIQUE_EXPLICIT_METADATA_DOWNLOAD_URL"
    )
