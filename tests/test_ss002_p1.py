from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_p1 import refine_categories


def _event(
    text: str,
    *,
    categories: list[str] | None = None,
) -> dict:
    return {
        "desc": "",
        "attchmntText": text,
        "special_situation_categories": categories or ["OPEN_OFFER_CONTROL"],
    }


def test_generic_sast_disclosure_is_not_live_open_offer() -> None:
    categories = refine_categories(
        _event("Disclosure under Regulation 29(2) of SEBI Substantial Acquisition of Shares")
    )
    assert categories == ["SAST_DISCLOSURE"]


def test_actual_open_offer_is_live_offer_control() -> None:
    categories = refine_categories(
        _event("Detailed Public Statement for Open Offer under SEBI Takeover Regulations")
    )
    assert categories == ["LIVE_OPEN_OFFER_CONTROL"]


def test_event_can_be_live_offer_and_sast_context() -> None:
    categories = refine_categories(
        _event("Open Offer under SEBI Substantial Acquisition of Shares and Takeovers")
    )
    assert categories == ["LIVE_OPEN_OFFER_CONTROL", "SAST_DISCLOSURE"]


def test_non_open_offer_categories_are_preserved() -> None:
    categories = refine_categories(
        _event(
            "Board approves buyback",
            categories=["BUYBACK"],
        )
    )
    assert categories == ["BUYBACK"]


def test_legacy_open_offer_without_frozen_token_fails_closed() -> None:
    with pytest.raises(AlphaContractError, match="cannot be source-reclassified"):
        refine_categories(_event("Unrelated filing"))
