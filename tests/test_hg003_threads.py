from __future__ import annotations

import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg003_threads import select_hg003_threads


def _symbols() -> list[str]:
    return ["HINDCOPPER"] + [f"S{idx:02d}" for idx in range(1, 28)]


def _category_map() -> dict[str, list[str]]:
    symbols = _symbols()
    result = {symbol: ["BUYBACK"] for symbol in symbols}
    result["HINDCOPPER"] = ["OFFER_FOR_SALE"]
    for symbol in symbols[1:8]:
        result[symbol].append("SCHEME_REORGANISATION")
    return result


def _hg002() -> dict:
    rows = [
        {
            "symbol": symbol,
            "special_situation_categories": categories,
        }
        for symbol, categories in _category_map().items()
    ]
    return {
        "cohort_id": "HG002-D001-v1",
        "cohort_sha256": (
            "3937b8cb83ef819ff956af4afebb80cd81d8ef233c1e4dd5b6d3688541a48db1"
        ),
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _p2_and_d3() -> tuple[dict, dict, list[dict]]:
    events = []
    manifest = []
    records = []
    serial = 0
    for symbol, categories in _category_map().items():
        for category in categories:
            serial += 1
            event_id = f"E{serial:03d}"
            document_id = f"D{serial:03d}"
            events.append(
                {
                    "announcement_id": event_id,
                    "symbol": symbol,
                    "mapping_state": "CURRENT_INVESTABLE_IDENTITY",
                    "special_situation_categories": [category],
                    "exchange_published_at_utc": (
                        f"2026-09-{(serial % 20) + 1:02d}T12:00:00Z"
                    ),
                }
            )
            if symbol == "HINDCOPPER":
                manifest.append(
                    {
                        "document_id": document_id,
                        "event_ids": [event_id],
                        "symbols": [symbol],
                        "categories": [category],
                        "extraction_state": "NO_EXTRACTABLE_TEXT",
                        "segment_manifest_sha256": "f" * 64,
                        "source_url": (
                            "https://nsearchives.nseindia.com/hindcopper.pdf"
                        ),
                    }
                )
                records.append(
                    {
                        "document_id": document_id,
                        "extraction_state": "NO_EXTRACTABLE_TEXT",
                        "segments": [],
                    }
                )
                continue

            text = f"{symbol} {category} explicit source text"
            text_sha = hashlib.sha256(text.encode()).hexdigest()
            segment = {
                "segment_id": f"{document_id}:page:1",
                "text": text,
                "text_sha256": text_sha,
            }
            manifest.append(
                {
                    "document_id": document_id,
                    "event_ids": [event_id],
                    "symbols": [symbol],
                    "categories": [category],
                    "extraction_state": "READY",
                    "segment_manifest_sha256": "a" * 64,
                    "source_url": (
                        f"https://nsearchives.nseindia.com/{document_id}.pdf"
                    ),
                }
            )
            records.append(
                {
                    "document_id": document_id,
                    "extraction_state": "READY",
                    "segments": [segment],
                }
            )

    p2 = {
        "census_id": "SS002-D001-P2-v1",
        "census_sha256": (
            "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"
        ),
        "events": events,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    d3 = {
        "corpus_id": "SS002-D003-v1",
        "corpus_sha256": (
            "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"
        ),
        "document_count": len(manifest),
        "documents": manifest,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return p2, d3, records


def test_hg003_selects_34_ready_threads_and_retains_hindcopper_gap() -> None:
    p2, d3, records = _p2_and_d3()
    result = select_hg003_threads(_hg002(), p2, d3, records)

    assert result["symbol_count"] == 28
    assert result["thread_count"] == 35
    assert result["selection_state_counts"] == {
        "TEXT_READY": 34,
        "TEXT_UNAVAILABLE": 1,
    }
    assert result["unresolved_thread_ids"] == [
        "HINDCOPPER::OFFER_FOR_SALE"
    ]
    assert result["feasibility_pass"] is True
    assert result["promotion_allowed_to_cohort_l001"] is True
    assert result["portfolio_eligibility_allowed"] is False


def test_hg003_ready_threads_have_evidence_bound_prompts() -> None:
    p2, d3, records = _p2_and_d3()
    result = select_hg003_threads(_hg002(), p2, d3, records)

    ready = [
        row for row in result["rows"]
        if row["selection_state"] == "TEXT_READY"
    ]
    assert len(ready) == 34
    assert all(row["prompt_envelope"] for row in ready)
    assert all(len(row["prompt_sha256"]) == 64 for row in ready)


def test_hg003_fails_closed_if_thread_set_changes() -> None:
    hg002 = _hg002()
    hg002["rows"][1]["special_situation_categories"].append("RIGHTS_ISSUE")
    p2, d3, records = _p2_and_d3()
    with pytest.raises(AlphaContractError, match="expected 35 threads"):
        select_hg003_threads(hg002, p2, d3, records)
