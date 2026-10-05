from __future__ import annotations

import hashlib

from marketlab.ss002_l001_p2 import (
    FAMILIES,
    PER_FAMILY,
    select_expanded_pilot,
)


def _segments(document_id: str) -> list[dict]:
    text = f"Document {document_id} text"
    return [
        {
            "segment_id": f"{document_id}:1",
            "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
    ]


def _hg002() -> dict:
    return {
        "cohort_id": "HG002-D001-v1",
        "cohort_sha256": (
            "3937b8cb83ef819ff956af4afebb80cd81d8ef233c1e4dd5b6d3688541a48db1"
        ),
        "l001_p1_unvalidated_family_counts": {
            "INSOLVENCY_RESOLUTION": 5,
            "OFFER_FOR_SALE": 1,
            "PREFERENTIAL_WARRANT": 10,
            "RIGHTS_ISSUE": 2,
            "SCHEME_REORGANISATION": 11,
        },
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _p2_and_d3() -> tuple[dict, dict, list[dict]]:
    events = []
    docs = []
    manifest = []
    counter = 0
    for family in FAMILIES:
        for index in range(PER_FAMILY + 1):
            counter += 1
            symbol = f"{family[:4]}{index}"
            document_id = f"D{counter:03d}"
            url = f"https://nsearchives.nseindia.com/{document_id}.pdf"
            event_id = f"E{counter:03d}"
            events.append(
                {
                    "mapping_state": "CURRENT_INVESTABLE_IDENTITY",
                    "special_situation_categories": [family],
                    "approved_attachment_url": url,
                    "exchange_published_at_utc": (
                        f"2026-10-{20-index:02d}T10:00:00Z"
                    ),
                    "announcement_id": event_id,
                    "symbol": symbol,
                }
            )
            record = {
                "document_id": document_id,
                "source_url": url,
                "extraction_state": "READY",
                "event_ids": [event_id],
                "symbols": [symbol],
                "categories": [family],
                "segments": _segments(document_id),
                "segment_manifest_sha256": "a" * 64,
            }
            docs.append(record)
            manifest.append({"document_id": document_id})

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
    return p2, d3, docs


def test_expanded_pilot_selects_five_per_frozen_family() -> None:
    p2, d3, docs = _p2_and_d3()
    output = select_expanded_pilot(_hg002(), p2, d3, docs)
    assert output["selected_document_count"] == 25
    assert output["family_counts"] == {family: 5 for family in FAMILIES}
    assert output["families"] == list(FAMILIES)
    assert output["per_family_cap"] == 5
    assert output["portfolio_eligibility_allowed"] is False


def test_selection_is_newest_first_and_one_symbol_per_family() -> None:
    p2, d3, docs = _p2_and_d3()
    output = select_expanded_pilot(_hg002(), p2, d3, docs)
    scheme = [
        row for row in output["rows"]
        if row["pilot_family"] == "SCHEME_REORGANISATION"
    ]
    assert len(scheme) == 5
    assert scheme[0]["exchange_published_at_utc"] > scheme[-1][
        "exchange_published_at_utc"
    ]
    assert len({row["symbol"] for row in scheme}) == 5


def test_family_set_is_bound_to_hg002() -> None:
    p2, d3, docs = _p2_and_d3()
    hg = _hg002()
    hg["l001_p1_unvalidated_family_counts"]["RIGHTS_ISSUE"] = 3
    import pytest
    from marketlab.alpha import AlphaContractError
    with pytest.raises(AlphaContractError, match="family set changed"):
        select_expanded_pilot(hg, p2, d3, docs)
