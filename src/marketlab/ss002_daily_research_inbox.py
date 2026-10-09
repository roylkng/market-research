from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_special_situations import CATEGORY_TOKENS, approved_attachment_url

INBOX_ID = "SS002-P002-v1"
SOURCE_CAPTURE_SHAS = {
    "2026-10-05": "abaf46c8a03c15488991451090081c7739c9c3349aece2b763a685d784b92652",
    "2026-10-06": "182f392a683978f3196e7467b8e832286a6b6b76e4c8bd049c42fa0e24c70772",
    "2026-10-07": "9eddbcf450672c36ccf090254de16dbd3b7bb6b3898fa25872717f6b73743822",
    "2026-10-08": "cefe063a076ff9bfb6a88e06293fe435e5a7a62707b0e294d247640d10ca135d",
}
EXPECTED_EVENT_COUNT = 54
EXPECTED_CURRENT_EQ_COUNT = 36
EXPECTED_HG001_SHA = "79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff"
EXPECTED_HG001_COUNT = 2319
IST = ZoneInfo("Asia/Kolkata")

RESEARCH_STATES = frozenset(
    {
        "CONVERGENT_PRIOR_RESEARCH",
        "SINGLE_LANE_PRIOR_RESEARCH",
        "NEW_EVENT_NO_PRIOR_LANE",
        "IDENTITY_REVIEW_REQUIRED",
        "ARCHIVAL_OR_UNMATCHED",
    }
)


def _verify_hash(payload: dict[str, Any], field: str, expected: str) -> None:
    if payload.get(field) != expected:
        raise AlphaContractError(f"P002 {field} mismatch")
    stripped = {key: value for key, value in payload.items() if key != field}
    if digest(stripped) != expected:
        raise AlphaContractError(f"P002 tampered source payload for {field}")


def _validate_sources(
    daily_captures: dict[str, dict[str, Any]],
    hg001: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if set(daily_captures) != set(SOURCE_CAPTURE_SHAS):
        raise AlphaContractError("P002 requires exactly the four frozen capture dates")

    for day, capture in sorted(daily_captures.items()):
        if not isinstance(capture, dict):
            raise TypeError("P002 daily source must be a JSON object")
        _verify_hash(capture, "capture_sha256", SOURCE_CAPTURE_SHAS[day])
        if capture.get("source_day_ist") != day:
            raise AlphaContractError(f"P002 capture day mismatch for {day}")
        if capture.get("capture_id") != f"SS002-P001-{day}-v1":
            raise AlphaContractError(f"P002 unexpected source capture ID for {day}")
        if capture.get("contract_id") != "SS002-P001-v1":
            raise AlphaContractError(f"P002 unexpected daily source contract for {day}")
        for key in (
            "model_inference_executed",
            "return_outcomes_opened",
            "model_fitted",
            "share_action_clearance_proven",
            "market_capitalization_calculated",
            "portfolio_eligibility_allowed",
            "live_capital_allowed",
        ):
            if capture.get(key) is not False:
                raise AlphaContractError(f"P002 requires capture {key}=false")

    if not isinstance(hg001, dict):
        raise TypeError("P002 HG001 source must be a JSON object")
    _verify_hash(hg001, "router_sha256", EXPECTED_HG001_SHA)
    if hg001.get("router_id") != "HG001-D001-v1":
        raise AlphaContractError("P002 wrong HG001 router ID")
    if hg001.get("identity_count") != EXPECTED_HG001_COUNT:
        raise AlphaContractError("P002 wrong HG001 population")
    for key in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if hg001.get(key) is not False:
            raise AlphaContractError(f"P002 requires HG001 {key}=false")
    rows = hg001.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_HG001_COUNT:
        raise AlphaContractError("P002 HG001 source rows incomplete")
    index = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("P002 HG001 row must be an object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in index:
            raise AlphaContractError("P002 HG001 source symbols missing or duplicated")
        index[symbol] = row
    return index


def _source_day_of(event: dict[str, Any]) -> str:
    try:
        stamp = datetime.fromisoformat(str(event["exchange_published_at_utc"]))
    except (KeyError, ValueError) as exc:
        raise AlphaContractError("P002 invalid announcement timestamp") from exc
    if stamp.tzinfo is None:
        raise AlphaContractError("P002 announcement timestamp lacks timezone")
    return stamp.astimezone(IST).date().isoformat()


def _category_hints(event: dict[str, Any]) -> list[str]:
    values = event.get("category_hints_only")
    if not isinstance(values, list) or not values:
        raise AlphaContractError("P002 candidate categories unavailable")
    if not all(isinstance(v, str) for v in values) or len(set(values)) != len(values):
        raise AlphaContractError("P002 category hints invalid or duplicated")
    if not set(values).issubset(set(CATEGORY_TOKENS)):
        raise AlphaContractError("P002 unexpected special-situation hint")
    return sorted(values)


def build_daily_research_inbox(
    daily_captures: dict[str, dict[str, Any]],
    hg001: dict[str, Any],
) -> dict[str, Any]:
    by_symbol = _validate_sources(daily_captures, hg001)
    seen_events: set[str] = set()
    entries = []
    thread_index: dict[str, list[str]] = defaultdict(list)
    research_counts: Counter[str] = Counter()
    day_counts: Counter[str] = Counter()
    matched_count = 0
    document_ready_count = 0
    exact_hg001_join_count = 0
    governance_review_count = 0

    for day, capture in sorted(daily_captures.items()):
        candidates = capture.get("candidate_events")
        announcements = capture.get("announcements")
        if not isinstance(candidates, list) or not isinstance(announcements, list):
            raise AlphaContractError("P002 daily capture lacks event arrays")
        if capture.get("candidate_event_count") != len(candidates):
            raise AlphaContractError("P002 daily candidate count mismatch")
        if capture.get("announcement_count") != len(announcements):
            raise AlphaContractError("P002 daily announcement count mismatch")
        announcement_ids = {
            row.get("announcement_id") for row in announcements if isinstance(row, dict)
        }

        day_matched = 0
        for event in candidates:
            if not isinstance(event, dict):
                raise TypeError("P002 event must be a JSON object")
            event_id = event.get("announcement_id")
            symbol = event.get("symbol")
            if (
                not isinstance(event_id, str) or not event_id
                or not isinstance(symbol, str) or not symbol
            ):
                raise AlphaContractError("P002 canonical event identity unavailable")
            if event_id in seen_events or event_id not in announcement_ids:
                raise AlphaContractError("P002 duplicate or unverified canonical event")
            seen_events.add(event_id)
            if _source_day_of(event) != day:
                raise AlphaContractError("P002 announcement publication day mismatch")
            categories = _category_hints(event)

            mapping = event.get("mapping_state")
            current = mapping == "SYMBOL_IN_EQ_MASTER_AT_CAPTURE"
            if mapping not in {
                "SYMBOL_IN_EQ_MASTER_AT_CAPTURE",
                "ARCHIVAL_OR_UNMATCHED_AT_CAPTURE",
            }:
                raise AlphaContractError("P002 invalid capture-day EQ mapping")
            prior = by_symbol.get(symbol)
            exact_join = bool(
                current and prior is not None
                and event.get("current_eq_isin_at_capture") == prior.get("isin")
            )
            if current:
                matched_count += 1
                day_matched += 1
            if exact_join:
                exact_hg001_join_count += 1
                lane_count = prior.get("active_opportunity_lane_count")
                if not isinstance(lane_count, int) or lane_count < 0 or lane_count > 3:
                    raise AlphaContractError("P002 invalid historical opportunity lane count")
                research_state = (
                    "CONVERGENT_PRIOR_RESEARCH" if lane_count >= 2
                    else "SINGLE_LANE_PRIOR_RESEARCH" if lane_count == 1
                    else "NEW_EVENT_NO_PRIOR_LANE"
                )
                historical = {
                    "snapshot_id": "HG001-D001-v1",
                    "asof_source_period": "2026-10-04",
                    "research_route": prior.get("research_route"),
                    "active_opportunity_lanes": prior.get("active_opportunity_lanes"),
                    "governance_caution_flags": prior.get("governance_caution_flags"),
                    "asset_caution_flags": prior.get("asset_caution_flags"),
                    "liquidity_band": prior.get("liquidity_band"),
                    "in_existing_u001": prior.get("in_existing_u001"),
                }
                if prior.get("governance_caution_flags"):
                    governance_review_count += 1
            elif current:
                research_state = "IDENTITY_REVIEW_REQUIRED"
                historical = None
            else:
                research_state = "ARCHIVAL_OR_UNMATCHED"
                historical = None

            raw_url = event.get("approved_attachment_url")
            url = approved_attachment_url(raw_url)
            attachment_ready = bool(
                current and event.get("attachment_state") == "OFFICIAL_URL" and url is not None
            )
            if event.get("attachment_state") == "OFFICIAL_URL" and url is None:
                raise AlphaContractError("P002 official URL classification is invalid")
            if attachment_ready:
                document_ready_count += 1

            research_counts[research_state] += 1
            day_counts[day] += 1
            membership = []
            for category in categories:
                thread_key = f"{symbol}::{category}"
                thread_index[thread_key].append(event_id)
                membership.append(thread_key)

            entries.append(
                {
                    "source_day_ist": day,
                    "capture_sha256": capture["capture_sha256"],
                    "source_lag_state": capture.get("source_lag_state"),
                    "source_raw_sha256": event.get("source_raw_sha256"),
                    "announcement_id": event_id,
                    "exchange_published_at_utc": event["exchange_published_at_utc"],
                    "symbol": symbol,
                    "isin_at_capture": event.get("current_eq_isin_at_capture"),
                    "company_name_at_capture": event.get("current_eq_name_at_capture"),
                    "mapping_state": mapping,
                    "category_hints_only": categories,
                    "economic_relevance_verified": False,
                    "approved_attachment_url": url,
                    "document_intake_state": (
                        "DOCUMENT_INTAKE_READY" if attachment_ready
                        else "NO_APPROVED_CURRENT_ATTACHMENT"
                    ),
                    "research_attention_state": research_state,
                    "exact_historical_identity_match": exact_join,
                    "historical_research_context": historical,
                    "thread_memberships": membership,
                    "return_outcomes_opened": False,
                    "share_action_clearance_proven": False,
                    "market_capitalization_calculated": False,
                    "portfolio_eligibility_allowed": False,
                    "live_capital_allowed": False,
                }
            )
        if day_matched != capture.get("candidate_current_eq_event_count"):
            raise AlphaContractError(f"P002 current EQ source count mismatch for {day}")

    if len(entries) != EXPECTED_EVENT_COUNT or matched_count != EXPECTED_CURRENT_EQ_COUNT:
        raise AlphaContractError("P002 unexpected frozen daily population")
    if set(research_counts) - RESEARCH_STATES:
        raise AlphaContractError("P002 emitted unknown research routing state")

    entries.sort(
        key=lambda row: (
            row["source_day_ist"],
            row["exchange_published_at_utc"],
            row["symbol"],
            row["announcement_id"],
        )
    )
    result = {
        "schema_version": 1,
        "inbox_id": INBOX_ID,
        "classification": "DAILY_SOURCE_ONLY_SPECIAL_SITUATION_RESEARCH_INBOX_NOT_ALPHA",
        "capture_shas": dict(sorted(SOURCE_CAPTURE_SHAS.items())),
        "source_hg001_router_sha256": EXPECTED_HG001_SHA,
        "source_days": sorted(SOURCE_CAPTURE_SHAS),
        "source_event_count": len(entries),
        "current_eq_at_capture_event_count": matched_count,
        "archival_or_unmatched_count": len(entries) - matched_count,
        "exact_hg001_identity_match_count": exact_hg001_join_count,
        "document_intake_ready_count": document_ready_count,
        "prior_governance_caution_event_count": governance_review_count,
        "research_attention_state_counts": dict(sorted(research_counts.items())),
        "source_day_event_counts": dict(sorted(day_counts.items())),
        "thread_count": len(thread_index),
        "thread_index": {
            key: sorted(ids) for key, ids in sorted(thread_index.items())
        },
        "events": entries,
        "source_only_gate_pass": True,
        "model_inference_executed": False,
        "economic_relevance_verified": False,
        "return_outcomes_opened": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["inbox_sha256"] = digest(result)
    return result
