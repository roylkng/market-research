from datetime import UTC, datetime

import pytest

from marketlab.alpha_announcements import (
    HISTORICAL_DAILY_AN_DT_AUTHORITY,
    SYMBOL_SAMPLE,
    AnnouncementAuditError,
    build_d003_audit,
    normalize_announcement_payload,
)


def _row(
    *,
    symbol: str,
    seq_id: str,
    timestamp: str,
    desc: str = "Updates",
) -> dict:
    return {
        "symbol": symbol,
        "seq_id": seq_id,
        "exchdisstime": timestamp,
        "desc": desc,
        "attchmntText": f"{symbol} has informed the Exchange",
        "attchmntFile": (
            "https://nsearchives.nseindia.com/"
            f"corporate/{symbol}-{seq_id}.pdf"
        ),
    }


def test_normalize_announcement_payload_builds_stable_identity():
    payload = [
        _row(
            symbol="INFY",
            seq_id="1",
            timestamp="17-Sep-2026 15:30:01",
        )
    ]
    rows = normalize_announcement_payload(
        payload,
        requested_start=datetime(2026, 9, 17, tzinfo=UTC).date(),
        requested_end=datetime(2026, 9, 17, tzinfo=UTC).date(),
    )
    assert len(rows) == 1
    assert rows[0]["symbol"] == "INFY"
    assert len(rows[0]["announcement_id"]) == 64
    assert rows[0]["exchange_published_at_utc"].endswith("Z")


def test_normalize_rejects_duplicate_canonical_row():
    row = _row(
        symbol="TCS",
        seq_id="2",
        timestamp="18-Sep-2026 10:00:00",
    )
    with pytest.raises(
        AnnouncementAuditError,
        match="duplicate canonical announcement identity",
    ):
        normalize_announcement_payload(
            [row, dict(row)],
            requested_start=datetime(2026, 9, 18, tzinfo=UTC).date(),
            requested_end=datetime(2026, 9, 18, tzinfo=UTC).date(),
        )


def test_d003_passes_exact_full_daily_and_symbol_reconciliation():
    rows = [
        _row(
            symbol="INFY",
            seq_id="1",
            timestamp="15-Sep-2026 10:00:00",
            desc="Updates",
        ),
        _row(
            symbol="RELIANCE",
            seq_id="2",
            timestamp="17-Sep-2026 14:00:00",
            desc="Investor Presentation",
        ),
        _row(
            symbol="TCS",
            seq_id="3",
            timestamp="21-Sep-2026 17:00:00",
            desc="General Updates",
        ),
        _row(
            symbol="OTHER",
            seq_id="4",
            timestamp="21-Sep-2026 17:10:00",
            desc="Order",
        ),
    ]
    daily = {
        f"2026-09-{day:02d}": []
        for day in range(15, 22)
    }
    daily["2026-09-15"] = [rows[0]]
    daily["2026-09-17"] = [rows[1]]
    daily["2026-09-21"] = rows[2:]

    symbol_payloads = {
        symbol: [row for row in rows if row["symbol"] == symbol]
        for symbol in SYMBOL_SAMPLE
    }
    report = build_d003_audit(
        full_payload=rows,
        full_raw_sha256="a" * 64,
        daily_payloads=daily,
        daily_raw_sha256={
            key: f"{index + 1:064x}"
            for index, key in enumerate(sorted(daily))
        },
        symbol_payloads=symbol_payloads,
        symbol_raw_sha256={
            symbol: f"{index + 100:064x}"
            for index, symbol in enumerate(SYMBOL_SAMPLE)
        },
        generated_at_utc="2026-09-30T12:00:00+00:00",
    )
    assert report["status"] == "PASS"
    assert report["full_vs_daily"]["exact_identity_match"] is True
    assert report["full_vs_daily"]["full_count"] == 4
    assert report["distinct_symbol_count"] == 4
    assert all(
        row["exact_identity_match"]
        for row in report["symbol_reconciliation"].values()
    )
    assert report["market_return_outcomes_opened"] is False


def test_d003_fails_when_full_market_misses_symbol_scoped_row():
    full = [
        _row(
            symbol="INFY",
            seq_id="1",
            timestamp="15-Sep-2026 10:00:00",
        )
    ]
    daily = {
        f"2026-09-{day:02d}": []
        for day in range(15, 22)
    }
    daily["2026-09-15"] = full
    symbol_payloads = {symbol: [] for symbol in SYMBOL_SAMPLE}
    symbol_payloads["INFY"] = [
        *full,
        _row(
            symbol="INFY",
            seq_id="2",
            timestamp="16-Sep-2026 10:00:00",
        ),
    ]
    report = build_d003_audit(
        full_payload=full,
        full_raw_sha256="a" * 64,
        daily_payloads=daily,
        daily_raw_sha256={
            key: f"{index + 1:064x}"
            for index, key in enumerate(sorted(daily))
        },
        symbol_payloads=symbol_payloads,
        symbol_raw_sha256={
            symbol: f"{index + 100:064x}"
            for index, symbol in enumerate(SYMBOL_SAMPLE)
        },
        generated_at_utc="2026-09-30T12:00:00+00:00",
    )
    assert report["status"] == "FAIL"
    assert (
        report["symbol_reconciliation"]["INFY"]["missing_from_whole_market_count"]
        == 1
    )

def test_historical_timestamp_authority_uses_an_dt_without_changing_default() -> None:
    row = {
        "symbol": "AHLUCONT",
        "seq_id": "152114",
        "an_dt": "14-Feb-2023 13:05:54",
        "sort_date": "2023-02-14 13:05:54",
        "exchdisstime": "02-Mar-2023 20:33:52",
        "desc": "Financial Result Updates",
        "attchmntText": "Financial results update",
        "attchmntFile": "https://nsearchives.nseindia.com/corporate/a.pdf",
    }
    day = datetime(2023, 2, 14, tzinfo=UTC).date()

    with pytest.raises(AnnouncementAuditError, match="timestamp outside requested window"):
        normalize_announcement_payload(
            [row],
            requested_start=day,
            requested_end=day,
        )

    rows = normalize_announcement_payload(
        [row],
        requested_start=day,
        requested_end=day,
        timestamp_authority=HISTORICAL_DAILY_AN_DT_AUTHORITY,
    )
    assert len(rows) == 1
    assert rows[0]["exchange_published_at_utc"].startswith("2023-02-14T07:35:54")

