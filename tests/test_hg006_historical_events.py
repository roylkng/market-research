from __future__ import annotations

from datetime import date

from marketlab.hg006_historical_events import build_historical_event_census


def _row(symbol: str, seq: str, day: str, desc: str, text: str, url: str = "") -> dict:
    return {
        "symbol": symbol,
        "seq_id": seq,
        "exchdisstime": f"{day} 10:00:00",
        "desc": desc,
        "attchmntText": text,
        "attchmntFile": url,
    }


def test_historical_census_builds_symbol_family_chronologies() -> None:
    payloads = {
        "2025-12-30": [
            _row(
                "AAA",
                "1",
                "30-Dec-2025",
                "Scheme of Arrangement",
                "Demerger proposal",
                "https://nsearchives.nseindia.com/corporate/a.pdf",
            ),
            _row(
                "BBB",
                "2",
                "30-Dec-2025",
                "Preferential Allotment",
                "Issue of warrants",
                "https://nsearchives.nseindia.com/corporate/b.pdf",
            ),
        ],
        "2025-12-31": [],
        "2026-01-01": [
            _row(
                "AAA",
                "3",
                "01-Jan-2026",
                "Scheme of Arrangement",
                "NCLT update on demerger",
                "https://nsearchives.nseindia.com/corporate/a2.pdf",
            )
        ],
    }
    hashes = {key: f"sha-{key}" for key in payloads}

    result = build_historical_event_census(
        daily_payloads=payloads,
        daily_raw_sha256=hashes,
        generated_at_utc="2026-10-05T00:00:00Z",
        source_start=date(2025, 12, 30),
        initiation_end=date(2025, 12, 31),
        source_end=date(2026, 1, 1),
    )

    assert result["source_row_count"] == 3
    assert result["retained_event_count"] == 3
    assert result["historical_chronology_count"] == 2
    rows = {(row["symbol"], row["family"]): row for row in result["chronologies"]}
    assert rows[("AAA", "SCHEME_REORGANISATION")]["event_count"] == 2
    assert rows[("AAA", "SCHEME_REORGANISATION")]["followup_event_count"] == 1
    assert rows[("BBB", "PREFERENTIAL_WARRANT")]["event_count"] == 1
    assert result["completion_probabilities_assigned"] is False


def test_2026_only_event_does_not_enter_historical_initiation_cohort() -> None:
    payloads = {
        "2025-12-31": [],
        "2026-01-01": [
            _row(
                "AAA",
                "1",
                "01-Jan-2026",
                "Buyback",
                "Board considers buyback",
                "https://nsearchives.nseindia.com/corporate/a.pdf",
            )
        ],
    }
    hashes = {key: f"sha-{key}" for key in payloads}
    result = build_historical_event_census(
        daily_payloads=payloads,
        daily_raw_sha256=hashes,
        generated_at_utc="2026-10-05T00:00:00Z",
        source_start=date(2025, 12, 31),
        initiation_end=date(2025, 12, 31),
        source_end=date(2026, 1, 1),
    )
    assert result["retained_event_count"] == 1
    assert result["historical_chronology_count"] == 0


def test_excluded_family_does_not_enter_census() -> None:
    payloads = {
        "2025-12-30": [
            _row(
                "AAA",
                "1",
                "30-Dec-2025",
                "Asset Sale",
                "Sale of undertaking",
                "https://nsearchives.nseindia.com/corporate/a.pdf",
            )
        ],
        "2025-12-31": [],
    }
    hashes = {key: f"sha-{key}" for key in payloads}
    result = build_historical_event_census(
        daily_payloads=payloads,
        daily_raw_sha256=hashes,
        generated_at_utc="2026-10-05T00:00:00Z",
        source_start=date(2025, 12, 30),
        initiation_end=date(2025, 12, 30),
        source_end=date(2025, 12, 31),
    )
    assert result["retained_event_count"] == 0
    assert result["historical_chronology_count"] == 0

def test_canonical_day_uses_nse_ist_calendar_not_utc_calendar() -> None:
    payloads = {
        "2025-12-30": [
            {
                "symbol": "AAA",
                "seq_id": "late-utc",
                "exchdisstime": "2025-12-29T20:00:00+00:00",
                "desc": "Buyback",
                "attchmntText": "Board considers buyback",
                "attchmntFile": "https://nsearchives.nseindia.com/corporate/a.pdf",
            }
        ],
        "2025-12-31": [],
    }
    hashes = {key: f"sha-{key}" for key in payloads}

    result = build_historical_event_census(
        daily_payloads=payloads,
        daily_raw_sha256=hashes,
        generated_at_utc="2026-10-05T00:00:00Z",
        source_start=date(2025, 12, 30),
        initiation_end=date(2025, 12, 30),
        source_end=date(2025, 12, 31),
    )

    assert result["retained_event_count"] == 1
    assert result["events"][0]["source_day"] == "2025-12-30"
    assert result["events"][0]["exchange_published_at_utc"].startswith(
        "2025-12-29T20:00:00"
    )

