from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest

CENSUS_ID = "SS002-D001-P1-v1"
EXPECTED_D001_ID = "SS002-D001-v1"
EXPECTED_D001_SHA = "0e831d4ce29d03e6916d4e244d177f2ee1451ce98d35c0a37e50e0e79b12fa54"
EXPECTED_EVENT_COUNT = 6435

PRIMARY_CATEGORIES = frozenset(
    {
        "BUYBACK",
        "LIVE_OPEN_OFFER_CONTROL",
        "DELISTING",
        "SCHEME_REORGANISATION",
        "RIGHTS_ISSUE",
        "PREFERENTIAL_WARRANT",
        "ASSET_SALE_DIVESTMENT",
        "INSOLVENCY_RESOLUTION",
        "CAPITAL_REDUCTION",
        "OFFER_FOR_SALE",
        "TENDER_OFFER",
    }
)

LIVE_OFFER_TOKENS = ("open offer", "takeover offer", "change of control")
SAST_TOKEN = "substantial acquisition of shares"
ALLOWED_ATTACHMENT_HOSTS = frozenset(
    {"nsearchives.nseindia.com", "archives.nseindia.com"}
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _text(event: dict[str, Any]) -> str:
    return (
        f"{_clean(event.get('desc'))} {_clean(event.get('attchmntText'))}"
    ).casefold()


def _official_attachment(value: object) -> bool:
    raw = _clean(value)
    try:
        parsed = urlparse(raw)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").casefold() in ALLOWED_ATTACHMENT_HOSTS
    )


def refine_categories(event: dict[str, Any]) -> list[str]:
    original = event.get("special_situation_categories")
    if not isinstance(original, list) or not all(
        isinstance(category, str) and category for category in original
    ):
        raise AlphaContractError("SS002 P1 event categories are unavailable")

    result = {category for category in original if category != "OPEN_OFFER_CONTROL"}
    if "OPEN_OFFER_CONTROL" in original:
        text = _text(event)
        live = any(token in text for token in LIVE_OFFER_TOKENS)
        sast = SAST_TOKEN in text
        if not live and not sast:
            raise AlphaContractError(
                "SS002 P1 legacy OPEN_OFFER_CONTROL cannot be source-reclassified"
            )
        if live:
            result.add("LIVE_OPEN_OFFER_CONTROL")
        if sast:
            result.add("SAST_DISCLOSURE")
    return sorted(result)


def _actionability(
    event: dict[str, Any],
    categories: list[str],
) -> str:
    mapping = event.get("mapping_state")
    if mapping == "CURRENT_IDENTITY_UNMAPPED":
        return "HISTORICAL_OR_NONCURRENT"
    if mapping != "CURRENT_IDENTITY_MAPPED":
        raise AlphaContractError(f"SS002 P1 unexpected mapping state: {mapping}")
    if any(category in PRIMARY_CATEGORIES for category in categories):
        return "CURRENT_ACTIONABLE_PRIMARY"
    return "CURRENT_CONTEXT_ONLY"


def build_p1_census(d001: dict[str, Any]) -> dict[str, Any]:
    if d001.get("census_id") != EXPECTED_D001_ID:
        raise AlphaContractError("SS002 P1 requires frozen failed D001 census")
    if d001.get("census_sha256") != EXPECTED_D001_SHA:
        raise AlphaContractError("SS002 P1 D001 census SHA mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if d001.get(field) is not False:
            raise AlphaContractError(f"SS002 P1 requires D001 {field}=false")

    events = d001.get("events")
    if not isinstance(events, list) or len(events) != EXPECTED_EVENT_COUNT:
        raise AlphaContractError("SS002 P1 requires exact 6,435-event D001 corpus")

    refined = []
    category_counts: Counter[str] = Counter()
    actionability_counts: Counter[str] = Counter()
    legacy_open_offer_count = 0
    legacy_open_offer_accounted = 0
    current_primary_attachment_ready = 0
    current_primary_symbols: set[str] = set()
    seen_ids: set[str] = set()

    for event in events:
        if not isinstance(event, dict):
            raise TypeError("SS002 P1 event rows must be objects")
        event_id = str(event.get("announcement_id") or "")
        if not event_id or event_id in seen_ids:
            raise AlphaContractError("SS002 P1 announcement identities must be unique")
        seen_ids.add(event_id)

        categories = refine_categories(event)
        original = event["special_situation_categories"]
        if "OPEN_OFFER_CONTROL" in original:
            legacy_open_offer_count += 1
            if (
                "LIVE_OPEN_OFFER_CONTROL" in categories
                or "SAST_DISCLOSURE" in categories
            ):
                legacy_open_offer_accounted += 1

        state = _actionability(event, categories)
        attachment_ready = _official_attachment(event.get("attchmntFile"))
        if state == "CURRENT_ACTIONABLE_PRIMARY":
            symbol = str(event.get("symbol") or "").upper()
            context = event.get("current_context")
            if not symbol or not isinstance(context, dict):
                raise AlphaContractError(
                    "SS002 P1 current actionable event lacks exact current context"
                )
            current_primary_symbols.add(symbol)
            if attachment_ready:
                current_primary_attachment_ready += 1

        category_counts.update(categories)
        actionability_counts[state] += 1
        refined.append(
            {
                **event,
                "d001_special_situation_categories": list(original),
                "p1_special_situation_categories": categories,
                "p1_actionability_state": state,
                "official_attachment_ready": attachment_ready,
            }
        )

    current_primary_count = actionability_counts["CURRENT_ACTIONABLE_PRIMARY"]
    threshold_passes = {
        "exact_input_census_hash": True,
        "all_6435_events_reclassified_once": len(refined) == EXPECTED_EVENT_COUNT,
        "all_legacy_open_offer_events_accounted": (
            legacy_open_offer_count == legacy_open_offer_accounted
        ),
        "current_primary_exact_mapping_only": all(
            row["mapping_state"] == "CURRENT_IDENTITY_MAPPED"
            for row in refined
            if row["p1_actionability_state"] == "CURRENT_ACTIONABLE_PRIMARY"
        ),
        "all_current_primary_have_official_attachment": (
            current_primary_attachment_ready == current_primary_count
        ),
    }

    output = {
        "schema_version": 1,
        "census_id": CENSUS_ID,
        "classification": "CURRENT_ACTIONABLE_SPECIAL_SITUATION_CENSUS_NOT_ALPHA",
        "source_d001_census_sha256": EXPECTED_D001_SHA,
        "source_candidate_event_count": EXPECTED_EVENT_COUNT,
        "event_count": len(refined),
        "category_counts": dict(sorted(category_counts.items())),
        "actionability_state_counts": dict(sorted(actionability_counts.items())),
        "legacy_open_offer_event_count": legacy_open_offer_count,
        "legacy_open_offer_accounted_count": legacy_open_offer_accounted,
        "current_actionable_primary_event_count": current_primary_count,
        "current_actionable_primary_symbol_count": len(current_primary_symbols),
        "current_actionable_primary_attachment_ready_count": (
            current_primary_attachment_ready
        ),
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_attachment_acquisition": all(
            threshold_passes.values()
        ),
        "events": sorted(
            refined,
            key=lambda row: (
                str(row.get("exchange_published_at_utc") or ""),
                str(row.get("symbol") or ""),
                str(row.get("seq_id") or ""),
            ),
        ),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["census_sha256"] = digest(output)
    return output
