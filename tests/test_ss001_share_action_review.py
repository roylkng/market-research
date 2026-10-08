from __future__ import annotations

import hashlib
import json

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_share_action_review import build_share_action_review


def _payloads() -> tuple[dict, dict, dict, dict[str, bytes]]:
    d005_rows = [
        {
            "symbol": f"S{i:04d}",
            "source_readiness_state": (
                "TIME_AND_PRICE_READY" if i < 1960 else "D005_SOURCE_NOT_READY"
            ),
            "report_date": "2026-06-30" if i < 1960 else None,
        }
        for i in range(2319)
    ]
    d005 = {
        "audit_id": "SS001-D005-v1",
        "audit_sha256": "b5fe97c3a9e83e8acbfce9cddf4eed476d60c29ca5125caa400368b4f5c7e984",
        "time_and_price_ready_count": 1960,
        "rows": d005_rows,
    }
    raw_chunks = {}
    chunks = []
    for i in range(7):
        row = {
            "series": "EQ" if i < 2 else "GS",
            "symbol": f"S{i:04d}",
            "isin": "INE000000001",
            "exDate": "15-Sep-2026",
            "subject": "Bonus 1:1" if i == 0 else "Dividend",
        }
        raw = json.dumps([row], sort_keys=True).encode()
        sha = hashlib.sha256(raw).hexdigest()
        raw_chunks[sha] = raw
        chunks.append({"raw_sha256": sha, "row_count": 1})
    d001 = {
        "census_id": "SS001-D001-v1",
        "census_sha256": "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7",
        "corporate_action_row_count": 7,
        "source_metadata": {
            "corporate_action_window": {
                "from_date": "2025-10-05",
                "to_date": "2026-10-04",
                "chunks": chunks,
            }
        },
        "rows": [{"symbol": f"S{i:04d}"} for i in range(2319)],
    }

    events = []
    for i in range(2272):
        current = i < 1666
        events.append(
            {
                "announcement_id": f"E{i:04d}",
                "symbol": f"S{i:04d}" if current else f"OLD{i:04d}",
                "mapping_state": (
                    "CURRENT_INVESTABLE_IDENTITY"
                    if current
                    else "ARCHIVAL_NONCURRENT_IDENTITY"
                ),
                "exchange_published_at_utc": (
                    "2026-09-15T11:00:00Z"
                    if i != 1
                    else "2026-10-02T11:00:00Z"
                ),
                "special_situation_categories": (
                    ["PREFERENTIAL_WARRANT"] if i < 2 else ["OTHER"]
                ),
            }
        )
    p2 = {
        "census_id": "SS002-D001-P2-v1",
        "census_sha256": "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071",
        "events": events,
    }
    for item in (d005, d001, p2):
        item.update(
            {
                "return_outcomes_opened": False,
                "model_fitted": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )
    return d005, d001, p2, raw_chunks


def _build() -> dict:
    d005, d001, p2, chunks = _payloads()
    return build_share_action_review(
        d005_panel=d005,
        d001_census=d001,
        p2_census=p2,
        raw_action_chunks=chunks,
    )


def test_intervening_actions_and_announcements_are_not_clearance() -> None:
    result = _build()
    rows = {row["symbol"]: row for row in result["rows"]}
    assert result["feasibility_pass"] is True
    assert result["d005_time_and_price_ready_count"] == 1960
    assert rows["S0000"]["review_state"] == "BOTH_SOURCES_REVIEW_REQUIRED"
    assert rows["S0001"]["review_state"] == "NO_OBSERVED_TRIGGER_STILL_UNVERIFIED"
    assert rows["S1960"]["review_state"] == "D005_SOURCE_NOT_READY"
    assert rows["S0000"]["share_action_clearance_proven"] is False
    assert all(row["capitalization_calculation_allowed"] is False for row in result["rows"])


def test_raw_action_hash_mismatch_fails_closed() -> None:
    d005, d001, p2, chunks = _payloads()
    first = next(iter(chunks))
    chunks[first] = b"tampered"
    with pytest.raises(AlphaContractError, match="raw SHA mismatch"):
        build_share_action_review(
            d005_panel=d005, d001_census=d001,
            p2_census=p2, raw_action_chunks=chunks,
        )


def test_unparseable_eq_ex_date_fails_closed() -> None:
    d005, d001, p2, chunks = _payloads()
    first = d001["source_metadata"]["corporate_action_window"]["chunks"][0]
    raw = json.dumps(
        [{
            "series": "EQ",
            "symbol": "S0000",
            "exDate": "UNAVAILABLE",
            "subject": "Bonus",
        }],
        sort_keys=True,
    ).encode()
    old_sha = first["raw_sha256"]
    new_sha = hashlib.sha256(raw).hexdigest()
    del chunks[old_sha]
    chunks[new_sha] = raw
    first["raw_sha256"] = new_sha
    with pytest.raises(AlphaContractError, match="ex-date unavailable"):
        build_share_action_review(
            d005_panel=d005, d001_census=d001,
            p2_census=p2, raw_action_chunks=chunks,
        )


def test_publication_cutoff_blocks_future_announcement() -> None:
    result = _build()
    row = next(x for x in result["rows"] if x["symbol"] == "S0001")
    assert row["intervening_announcement_candidates"] == []
    assert row["share_action_clearance_proven"] is False
    assert result["market_capitalization_calculated"] is False
    assert result["portfolio_eligibility_allowed"] is False
