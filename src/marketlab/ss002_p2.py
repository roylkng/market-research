from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest

CENSUS_ID = "SS002-D001-P2-v1"
EXPECTED_P1_ID = "SS002-D001-P1-v1"
EXPECTED_P1_SHA = "2d0f39e218cdb1784d390a45685f0e787cff9edb4443a2c395d8806219213e2c"
EXPECTED_EVENT_COUNT = 6435
ALLOWED_ATTACHMENT_HOSTS = frozenset(
    {"nsearchives.nseindia.com", "archives.nseindia.com"}
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


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


def build_p2_census(p1: dict[str, Any]) -> dict[str, Any]:
    if p1.get("census_id") != EXPECTED_P1_ID:
        raise AlphaContractError("SS002 P2 requires frozen P1 census")
    if p1.get("census_sha256") != EXPECTED_P1_SHA:
        raise AlphaContractError("SS002 P2 P1 census SHA mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if p1.get(field) is not False:
            raise AlphaContractError(f"SS002 P2 requires P1 {field}=false")

    events = p1.get("events")
    if not isinstance(events, list) or len(events) != EXPECTED_EVENT_COUNT:
        raise AlphaContractError("SS002 P2 requires exact 6,435-event P1 corpus")

    output_events = []
    state_counts: Counter[str] = Counter()
    primary_symbols: set[str] = set()
    primary_attachment_ready = 0
    demoted_news_count = 0
    seen_ids: set[str] = set()

    for event in events:
        if not isinstance(event, dict):
            raise TypeError("SS002 P2 event rows must be objects")
        event_id = str(event.get("announcement_id") or "")
        if not event_id or event_id in seen_ids:
            raise AlphaContractError("SS002 P2 announcement identities must be unique")
        seen_ids.add(event_id)

        prior_state = str(event.get("p1_actionability_state") or "")
        official_attachment = _official_attachment(event.get("attchmntFile"))
        desc = _clean(event.get("desc"))

        state = prior_state
        if (
            prior_state == "CURRENT_ACTIONABLE_PRIMARY"
            and desc.casefold() == "news verification"
            and not official_attachment
        ):
            state = "CURRENT_UNCONFIRMED_NEWS_QUERY"
            demoted_news_count += 1

        if state == "CURRENT_ACTIONABLE_PRIMARY":
            if event.get("mapping_state") != "CURRENT_IDENTITY_MAPPED":
                raise AlphaContractError(
                    "SS002 P2 current primary event is not exact-current mapped"
                )
            if not official_attachment:
                raise AlphaContractError(
                    "SS002 P2 current primary event lacks official attachment"
                )
            symbol = str(event.get("symbol") or "").upper()
            if not symbol:
                raise AlphaContractError("SS002 P2 current primary symbol is empty")
            primary_symbols.add(symbol)
            primary_attachment_ready += 1

        if state == "CURRENT_UNCONFIRMED_NEWS_QUERY":
            if desc.casefold() != "news verification":
                raise AlphaContractError(
                    "SS002 P2 unconfirmed-news state requires News Verification desc"
                )

        state_counts[state] += 1
        output_events.append(
            {
                **event,
                "p1_actionability_state_original": prior_state,
                "p2_actionability_state": state,
                "p2_official_attachment_ready": official_attachment,
            }
        )

    current_primary_count = state_counts["CURRENT_ACTIONABLE_PRIMARY"]
    threshold_passes = {
        "exact_p1_census_hash": True,
        "all_6435_events_accounted_once": len(output_events) == EXPECTED_EVENT_COUNT,
        "current_primary_exact_mapping_only": all(
            row.get("mapping_state") == "CURRENT_IDENTITY_MAPPED"
            for row in output_events
            if row["p2_actionability_state"] == "CURRENT_ACTIONABLE_PRIMARY"
        ),
        "all_current_primary_have_official_attachment": (
            primary_attachment_ready == current_primary_count
        ),
        "all_demoted_rows_are_news_verification": all(
            _clean(row.get("desc")).casefold() == "news verification"
            for row in output_events
            if row["p2_actionability_state"] == "CURRENT_UNCONFIRMED_NEWS_QUERY"
        ),
    }

    output = {
        "schema_version": 1,
        "census_id": CENSUS_ID,
        "classification": "ATTACHMENT_READY_CURRENT_SPECIAL_SITUATION_CENSUS_NOT_ALPHA",
        "source_p1_census_sha256": EXPECTED_P1_SHA,
        "event_count": len(output_events),
        "actionability_state_counts": dict(sorted(state_counts.items())),
        "demoted_unconfirmed_news_query_count": demoted_news_count,
        "current_actionable_primary_event_count": current_primary_count,
        "current_actionable_primary_symbol_count": len(primary_symbols),
        "current_actionable_primary_attachment_ready_count": (
            primary_attachment_ready
        ),
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_attachment_acquisition": all(
            threshold_passes.values()
        ),
        "events": sorted(
            output_events,
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
