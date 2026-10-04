from __future__ import annotations

from datetime import date

from marketlab.ss002_special_situations import classify_special_situation


def test_special_situation_taxonomy_is_semantic_not_directional() -> None:
    row = {
        "desc": "Board Meeting - Buy Back of Shares",
        "attchmntText": "Consideration of buyback proposal",
    }
    assert classify_special_situation(row) == ["BUYBACK"]

    scheme = {
        "desc": "Scheme of Arrangement",
        "attchmntText": "Demerger and capital reduction",
    }
    assert classify_special_situation(scheme) == [
        "CAPITAL_REDUCTION",
        "SCHEME_REORGANISATION",
    ]


def test_unrelated_announcement_has_no_special_situation_category() -> None:
    row = {
        "desc": "Newspaper Publication",
        "attchmntText": "Financial results advertisement",
    }
    assert classify_special_situation(row) == []


def test_frozen_window_is_calendar_based() -> None:
    start = date(2026, 4, 1)
    end = date(2026, 10, 4)
    assert (end - start).days + 1 == 187


def test_routine_sast_disclosure_is_not_open_offer_control() -> None:
    row = {
        "desc": "Disclosure under Regulation 29(2)",
        "attchmntText": (
            "Disclosure under SEBI Substantial Acquisition of Shares "
            "and Takeovers Regulations, 2011"
        ),
    }
    assert classify_special_situation(row) == []


def test_explicit_open_offer_remains_control_candidate() -> None:
    row = {
        "desc": "Open Offer",
        "attchmntText": "Public announcement for open offer and change of control",
    }
    assert classify_special_situation(row) == ["OPEN_OFFER_CONTROL"]
