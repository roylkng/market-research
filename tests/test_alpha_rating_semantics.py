import io
from datetime import date

import pytest
from pypdf import PdfWriter

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_rating_semantics import (
    EXPECTED_SOURCE_COUNT,
    RATING_DEFINITIONS,
    SOURCE_LIST_ID,
    SOURCE_LIST_SHA256,
    _text_flags,
    augment_feature_panel_with_rating_semantics,
    build_rating_semantic_panel,
    build_rating_semantic_record,
    validate_rating_source_list,
)


def _minimal_pdf() -> bytes:
    raw = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(raw)
    return raw.getvalue()


def test_t008_action_parser_excludes_withdrawal_boilerplate():
    flags = _text_flags(
        [
            "CRISIL BBB/Stable (Reaffirmed)",
            "CRISIL Ratings reserves the right to withdraw or revise the ratings at any time",
        ]
    )
    assert flags["reaffirmed"] is True
    assert flags["withdrawn"] is False


def test_t008_action_parser_captures_directional_rating_language():
    flags = _text_flags(
        [
            "[ICRA]BBB (Negative); Reaffirmed and Outlook revised from Stable",
            "Short term rating upgraded from [ICRA]A3 to [ICRA]A2+",
            "Removed from Rating Watch with Developing Implications",
            "Issuer Not Cooperating",
        ]
    )
    assert flags["upgrade"] is True
    assert flags["reaffirmed"] is True
    assert flags["outlook_negative"] is True
    assert flags["watch_removed"] is True
    assert flags["watch_developing"] is True
    assert flags["noncooperation"] is True


def test_t008_blank_pdf_is_explicit_no_text():
    source = {
        "announcement_id": "a" * 64,
        "symbol": "TEST",
        "seq_id": "1",
        "exchange_published_at_utc": "2026-09-17T10:00:00Z",
        "description": "Credit Rating",
        "attachment_url": "https://nsearchives.nseindia.com/a.pdf",
    }
    record = build_rating_semantic_record(
        source,
        raw_pdf=_minimal_pdf(),
    )
    assert record["status"] == "NO_TEXT"
    assert record["directional"] is False
    assert record["flags"] == {}


def _source_list(records):
    payload = {
        "schema_version": 1,
        "source_list_id": SOURCE_LIST_ID,
        "trial_id": "AE001-T008-v1",
        "parent_t007_announcement_panel_sha256": (
            "fc3be48ce09905b8d2ebef1ad0e75a7ed22815202abbd7d7b328fe6dfcd3957d"
        ),
        "source_start": "2025-09-01",
        "source_end": "2026-09-25",
        "normalized_description_filter": [
            "credit rating",
            "credit rating- new",
            "credit rating- revision",
        ],
        "source_count": len(records),
        "records": records,
        "market_return_outcomes_attached": False,
        "live_capital_allowed": False,
    }
    payload["source_list_sha256"] = digest(payload)
    return payload


def test_t008_source_list_validator_fails_if_frozen_source_count_changes(
    monkeypatch,
):
    record = {
        "announcement_id": "a" * 64,
        "symbol": "TEST",
        "seq_id": "1",
        "exchange_published_at_utc": "2026-09-17T10:00:00Z",
        "description": "Credit Rating",
        "attachment_text": "",
        "attachment_url": "https://nsearchives.nseindia.com/a.pdf",
    }
    payload = _source_list([record])
    monkeypatch.setattr(
        "marketlab.alpha_rating_semantics.SOURCE_LIST_SHA256",
        payload["source_list_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.alpha_rating_semantics.EXPECTED_SOURCE_COUNT",
        1,
    )
    validate_rating_source_list(payload)
    payload["source_count"] = 2
    unsigned = dict(payload)
    unsigned.pop("source_list_sha256")
    payload["source_list_sha256"] = digest(unsigned)
    with pytest.raises(AlphaContractError):
        validate_rating_source_list(payload)


def _market_panel():
    sessions = []
    for index, day in enumerate(("2026-09-16", "2026-09-17", "2026-09-18")):
        sessions.append(
            {
                "session_date": day,
                "equities": [
                    {
                        "session_date": day,
                        "symbol": "TEST",
                        "isin": "INE000000001",
                        "open_price": 100.0 + index,
                        "high_price": 102.0 + index,
                        "low_price": 99.0 + index,
                        "close_price": 101.0 + index,
                        "previous_close": 100.0 + index,
                        "volume": 100000.0,
                        "turnover_inr": 30000000.0,
                        "trade_count": 1000.0,
                    },
                    {
                        "session_date": day,
                        "symbol": "QUIET",
                        "isin": "INE000000002",
                        "open_price": 50.0,
                        "high_price": 51.0,
                        "low_price": 49.0,
                        "close_price": 50.5,
                        "previous_close": 50.0,
                        "volume": 100000.0,
                        "turnover_inr": 30000000.0,
                        "trade_count": 1000.0,
                    },
                ],
            }
        )
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET",
        "sessions": sessions,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _feature_panel():
    rows = []
    for day in ("2026-09-16", "2026-09-17", "2026-09-18"):
        for symbol, isin in (
            ("TEST", "INE000000001"),
            ("QUIET", "INE000000002"),
        ):
            rows.append(
                {
                    "feature_session": day,
                    "symbol": symbol,
                    "isin": isin,
                    "values": {"base": 1.0},
                    "feature_set_sha256": "base",
                }
            )
    panel = {
        "schema_version": 1,
        "panel_id": "BASE",
        "feature_definitions": [
            {
                "name": "base",
                "family": "price_trend",
                "version": "v1",
                "description": "base",
                "lookback_sessions": 1,
                "availability_lag_sessions": 0,
            }
        ],
        "feature_set_sha256": "base",
        "rows": rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def test_t008_augmentation_maps_cutoff_and_preserves_quiet_rows(monkeypatch):
    sources = [
        {
            "announcement_id": "a" * 64,
            "symbol": "TEST",
            "seq_id": "1",
            "exchange_published_at_utc": "2026-09-17T12:00:00Z",
            "description": "Credit Rating- Revision",
            "attachment_text": "",
            "attachment_url": "https://nsearchives.nseindia.com/a.pdf",
        },
        {
            "announcement_id": "b" * 64,
            "symbol": "TEST",
            "seq_id": "2",
            # 19:00 IST, maps to Sep 18.
            "exchange_published_at_utc": "2026-09-17T13:30:00Z",
            "description": "Credit Rating- New",
            "attachment_text": "",
            "attachment_url": "https://nsearchives.nseindia.com/b.pdf",
        },
    ]
    source_list = _source_list(sources)
    monkeypatch.setattr(
        "marketlab.alpha_rating_semantics.SOURCE_LIST_SHA256",
        source_list["source_list_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.alpha_rating_semantics.EXPECTED_SOURCE_COUNT",
        2,
    )

    records = []
    for source, flags in (
        (
            sources[0],
            {
                "upgrade": True,
                "downgrade": False,
                "reaffirmed": False,
                "outlook_positive": True,
                "outlook_negative": False,
                "watch_positive": False,
                "watch_negative": False,
                "watch_developing": False,
                "watch_removed": False,
                "noncooperation": False,
                "withdrawn": False,
            },
        ),
        (
            sources[1],
            {
                "upgrade": False,
                "downgrade": True,
                "reaffirmed": False,
                "outlook_positive": False,
                "outlook_negative": True,
                "watch_positive": False,
                "watch_negative": False,
                "watch_developing": False,
                "watch_removed": False,
                "noncooperation": False,
                "withdrawn": False,
            },
        ),
    ):
        record = {
            "announcement_id": source["announcement_id"],
            "symbol": source["symbol"],
            "seq_id": source["seq_id"],
            "exchange_published_at_utc": source["exchange_published_at_utc"],
            "description": source["description"],
            "attachment_url": source["attachment_url"],
            "status": "TEXT_READY",
            "raw_sha256": "c" * 64,
            "page_count": 1,
            "first3_text_sha256": "d" * 64,
            "first3_text_char_count": 100,
            "failure_reason": None,
            "flags": flags,
            "directional": True,
        }
        record["record_sha256"] = digest(record)
        records.append(record)

    semantic = build_rating_semantic_panel(
        source_list=source_list,
        records=records,
    )

    augmented = augment_feature_panel_with_rating_semantics(
        feature_panel=_feature_panel(),
        market_panel=_market_panel(),
        semantic_panel=semantic,
    )
    assert augmented["feature_row_count"] == 6
    assert augmented["rating_feature_count"] == len(RATING_DEFINITIONS)

    by_key = {
        (row["feature_session"], row["symbol"]): row["values"]
        for row in augmented["rows"]
    }
    sep17 = by_key[("2026-09-17", "TEST")]
    assert sep17["rating_event_current"] == 1.0
    assert sep17["rating_upgrade_current"] == 1.0
    assert sep17["rating_outlook_positive_current"] == 1.0
    assert sep17["rating_downgrade_current"] == 0.0
    assert sep17["rating_sessions_since_directional_cap60"] == 0.0

    sep18 = by_key[("2026-09-18", "TEST")]
    assert sep18["rating_event_current"] == 1.0
    assert sep18["rating_new_current"] == 1.0
    assert sep18["rating_downgrade_current"] == 1.0
    assert sep18["rating_upgrade_20"] == 1.0
    assert sep18["rating_downgrade_20"] == 1.0

    quiet = by_key[("2026-09-18", "QUIET")]
    assert quiet["rating_event_current"] == 0.0
    assert quiet["rating_sessions_since_directional_cap60"] == 60.0
