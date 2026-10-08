from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_special_situations import approved_attachment_url

QUEUE_ID = "SS001-D007-Q001-v1"
D006_SHA = "b2aef97d107a1494adafa70d18321ee2e484d7b4796fe6ed7a7b0f5336f2f479"
P2_SHA = "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"

PRIORITY = (
    "BOTH_SOURCES_REVIEW_REQUIRED",
    "CORPORATE_ACTION_REVIEW_REQUIRED",
    "ANNOUNCEMENT_REVIEW_REQUIRED",
)
EXPECTED_COUNTS = {
    "BOTH_SOURCES_REVIEW_REQUIRED": 24,
    "CORPORATE_ACTION_REVIEW_REQUIRED": 11,
    "ANNOUNCEMENT_REVIEW_REQUIRED": 296,
    "D005_SOURCE_NOT_READY": 359,
    "NO_OBSERVED_TRIGGER_STILL_UNVERIFIED": 1629,
}
REVIEW_QUESTIONS = (
    "Did the listed issuer's equity share count actually change?",
    "Was the change effective after the shareholding report date and by October 1?",
    "Does this event affect the exact listed EQ security and ISIN?",
    "Is this actually a subsidiary, debt-security or procedural event?",
    "Are other share classes, partly paid shares or conversion rights relevant?",
)


def _flags_false(payload: dict[str, Any], label: str) -> None:
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if payload.get(field) is not False:
            raise AlphaContractError(f"D007 {label} requires {field}=false")


def _index_events(p2: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if p2.get("census_id") != "SS002-D001-P2-v1" or p2.get("census_sha256") != P2_SHA:
        raise AlphaContractError("D007 requires frozen SS002 P2 source")
    _flags_false(p2, "P2")
    events = p2.get("events")
    if not isinstance(events, list) or len(events) != 2272:
        raise AlphaContractError("D007 P2 event accounting mismatch")
    indexed: dict[str, dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict):
            raise TypeError("D007 event must be an object")
        event_id = event.get("announcement_id")
        if not isinstance(event_id, str) or not event_id or event_id in indexed:
            raise AlphaContractError("D007 P2 event ID must be unique")
        indexed[event_id] = event
    return indexed


def _validate_review_rows(d006: dict[str, Any]) -> list[dict[str, Any]]:
    if d006.get("audit_id") != "SS001-D006-v1" or d006.get("audit_sha256") != D006_SHA:
        raise AlphaContractError("D007 requires frozen D006 source")
    _flags_false(d006, "D006")
    if d006.get("identity_count") != 2319 or d006.get("d005_time_and_price_ready_count") != 1960:
        raise AlphaContractError("D007 D006 population mismatch")
    if d006.get("share_action_clearance_proven") is not False:
        raise AlphaContractError("D007 refuses a clearance-eligible D006 source")
    if d006.get("market_capitalization_calculated") is not False:
        raise AlphaContractError("D007 refuses a capitalized D006 source")
    if d006.get("review_state_counts") != EXPECTED_COUNTS:
        raise AlphaContractError("D007 frozen review state counts changed")
    rows = d006.get("rows")
    if not isinstance(rows, list) or len(rows) != 2319:
        raise AlphaContractError("D007 requires all 2319 D006 rows")
    symbols: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("D007 D006 row must be an object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in symbols:
            raise AlphaContractError("D007 D006 symbols must be unique")
        symbols.add(symbol)
    return rows


def build_share_change_packets(
    *,
    d006_review: dict[str, Any],
    p2_census: dict[str, Any],
) -> dict[str, Any]:
    rows = _validate_review_rows(d006_review)
    events = _index_events(p2_census)
    packets: list[dict[str, Any]] = []

    for row in rows:
        state = row["review_state"]
        if state not in PRIORITY:
            continue
        symbol = str(row["symbol"])
        actions = row.get("intervening_corporate_actions")
        announcements = row.get("intervening_announcement_candidates")
        if not isinstance(actions, list) or not isinstance(announcements, list):
            raise AlphaContractError(f"D007 {symbol} source evidence list missing")
        if not actions and not announcements:
            raise AlphaContractError(f"D007 {symbol} review state lacks evidence")
        if state == "BOTH_SOURCES_REVIEW_REQUIRED" and (not actions or not announcements):
            raise AlphaContractError(f"D007 {symbol} BOTH sources not actually present")
        if state == "CORPORATE_ACTION_REVIEW_REQUIRED" and (not actions or announcements):
            raise AlphaContractError(f"D007 {symbol} corporate-only state mismatch")
        if state == "ANNOUNCEMENT_REVIEW_REQUIRED" and (actions or not announcements):
            raise AlphaContractError(f"D007 {symbol} announcement-only state mismatch")

        seen_event_ids: set[str] = set()
        resolved = []
        ready_document_links = 0
        for announcement in announcements:
            if not isinstance(announcement, dict):
                raise TypeError("D007 review announcement must be an object")
            event_id = announcement.get("event_id")
            if not isinstance(event_id, str) or event_id in seen_event_ids:
                raise AlphaContractError(f"D007 {symbol} duplicate/invalid event ID")
            seen_event_ids.add(event_id)
            p2 = events.get(event_id)
            if p2 is None or p2.get("symbol") != symbol:
                raise AlphaContractError(f"D007 {symbol} canonical event identity mismatch")
            if p2.get("mapping_state") != "CURRENT_INVESTABLE_IDENTITY":
                raise AlphaContractError(f"D007 {symbol} event is not current-investable")

            url = p2.get("approved_attachment_url")
            if p2.get("attachment_state") == "READY":
                approved = approved_attachment_url(url)
                if approved is None:
                    raise AlphaContractError(f"D007 {symbol} READY NSE attachment URL invalid")
                ready_document_links += 1
                link_state = "APPROVED_NSE_ATTACHMENT_LINK"
            else:
                approved = None
                link_state = "OFFICIAL_DOCUMENT_LINK_UNAVAILABLE"
            resolved.append(
                {
                    "event_id": event_id,
                    "exchange_published_at_utc": announcement.get("published_at_utc"),
                    "categories": announcement.get("categories"),
                    "source_attachment_url": approved,
                    "attachment_link_state": link_state,
                    "document_sha256_bound": False,
                }
            )

        verified_actions = []
        for action in actions:
            if not isinstance(action, dict) or action.get("symbol") != symbol:
                raise AlphaContractError(f"D007 {symbol} corporate action identity mismatch")
            sha = action.get("source_raw_sha256")
            if not isinstance(sha, str) or len(sha) != 64:
                raise AlphaContractError(f"D007 {symbol} corporate action SHA unavailable")
            verified_actions.append(
                {
                    "ex_date": action.get("ex_date"),
                    "subject": action.get("subject"),
                    "source_isin": action.get("isin"),
                    "source_raw_sha256": sha,
                }
            )

        packets.append(
            {
                "symbol": symbol,
                "review_state": state,
                "priority_tier": PRIORITY.index(state) + 1,
                "source_record_count": len(actions) + len(announcements),
                "corporate_action_count": len(actions),
                "announcement_candidate_count": len(announcements),
                "approved_document_link_count": ready_document_links,
                "corporate_action_evidence": verified_actions,
                "announcement_evidence": resolved,
                "review_questions": list(REVIEW_QUESTIONS),
                "source_packet_status": (
                    "NSE_LINKS_PRESENT" if ready_document_links else "NO_P2_NSE_DOCUMENT_LINK"
                ),
                "share_action_clearance_proven": False,
                "capitalization_calculation_allowed": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    if len(packets) != 331:
        raise AlphaContractError("D007 expected exactly 331 distinct review symbols")

    packets.sort(
        key=lambda p: (
            p["priority_tier"],
            -p["source_record_count"],
            p["symbol"],
        )
    )
    for index, packet in enumerate(packets, start=1):
        packet["review_queue_rank"] = index
        packet["in_first_50_pilot"] = index <= 50
    source_states = Counter(packet["source_packet_status"] for packet in packets)

    output = {
        "schema_version": 1,
        "queue_id": QUEUE_ID,
        "classification": "SOURCE_EVIDENCE_ROUTING_NOT_SHARE_COUNT_CLEARANCE",
        "source_d006_sha256": D006_SHA,
        "source_p2_sha256": P2_SHA,
        "source_identity_count": 2319,
        "source_time_and_price_ready_count": 1960,
        "review_packet_count": 331,
        "pilot_packet_count": 50,
        "remaining_review_packet_count": 281,
        "queue_counts_by_state": {state: EXPECTED_COUNTS[state] for state in PRIORITY},
        "source_packet_state_counts": dict(sorted(source_states.items())),
        "packets": packets,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["queue_sha256"] = digest(output)
    return output
