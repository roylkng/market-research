from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_special_situations import approved_attachment_url

BINDING_ID = "SS001-D007-Q002-v1"
Q001_SHA = "53aea9016adfc62abfd778a1eb7b4bd6f6de262c30d01f1b7edf91abf2dbb4be"
D002_SHA = "eab922954ef20a12a7635107722b4e800b59cfa56ff0659da42afb3fc22218f9"
D003_SHA = "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"
EXPECTED_PACKETS = 50
EXPECTED_ANNOUNCEMENTS = 244
EXPECTED_D003_DOCUMENTS = 1539


def _closed(payload: dict[str, Any], label: str) -> None:
    for field in ("return_outcomes_opened", "portfolio_eligibility_allowed", "live_capital_allowed"):
        if payload.get(field) is not False:
            raise AlphaContractError(f"Q002 {label} requires {field}=false")
    if "model_fitted" in payload and payload["model_fitted"] is not False:
        raise AlphaContractError(f"Q002 {label} refuses fitted input")


def _require_d007(queue: dict[str, Any], pilot: dict[str, Any]) -> list[dict[str, Any]]:
    if queue.get("queue_id") != "SS001-D007-Q001-v1" or queue.get("queue_sha256") != Q001_SHA:
        raise AlphaContractError("Q002 frozen Q001 source queue mismatch")
    if pilot.get("queue_id") != queue["queue_id"] or pilot.get("source_queue_sha256") != Q001_SHA:
        raise AlphaContractError("Q002 frozen Q001 pilot source mismatch")
    if queue.get("review_packet_count") != 331 or queue.get("pilot_packet_count") != EXPECTED_PACKETS:
        raise AlphaContractError("Q002 Q001 population mismatch")
    if pilot.get("packet_count") != EXPECTED_PACKETS:
        raise AlphaContractError("Q002 requires exactly 50 frozen pilot packets")
    if queue.get("share_action_clearance_proven") is not False:
        raise AlphaContractError("Q002 Q001 cannot contain share-action clearance")
    if queue.get("market_capitalization_calculated") is not False:
        raise AlphaContractError("Q002 Q001 cannot contain capitalizations")
    for payload, label in ((queue, "Q001"), (pilot, "Q001_PILOT")):
        if payload.get("portfolio_eligibility_allowed") is not False:
            raise AlphaContractError(f"Q002 {label} cannot authorize portfolios")
        if payload.get("live_capital_allowed") is not False:
            raise AlphaContractError(f"Q002 {label} cannot authorize live capital")
    _closed(queue, "Q001")

    all_rows = queue.get("packets")
    pilot_rows = pilot.get("packets")
    if not isinstance(all_rows, list) or len(all_rows) != 331:
        raise AlphaContractError("Q002 requires all Q001 source packets")
    if not isinstance(pilot_rows, list) or len(pilot_rows) != EXPECTED_PACKETS:
        raise AlphaContractError("Q002 pilot packet list missing")
    if pilot_rows != all_rows[:EXPECTED_PACKETS]:
        raise AlphaContractError("Q002 pilot must reproduce exact first 50 Q001 packets")

    symbols: set[str] = set()
    announcement_count = 0
    for rank, packet in enumerate(pilot_rows, start=1):
        if not isinstance(packet, dict):
            raise TypeError("Q002 pilot packet must be object")
        symbol = packet.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in symbols:
            raise AlphaContractError("Q002 duplicate or invalid pilot symbol")
        if packet.get("review_queue_rank") != rank or packet.get("in_first_50_pilot") is not True:
            raise AlphaContractError("Q002 frozen Q001 pilot order changed")
        if packet.get("share_action_clearance_proven") is not False:
            raise AlphaContractError("Q002 cannot consume cleared Q001 packet")
        if packet.get("capitalization_calculation_allowed") is not False:
            raise AlphaContractError("Q002 refuses capitalization-eligible Q001 packet")
        symbols.add(symbol)
        evidence = packet.get("announcement_evidence")
        if not isinstance(evidence, list):
            raise AlphaContractError("Q002 announcement evidence unavailable")
        announcement_count += len(evidence)
    if announcement_count != EXPECTED_ANNOUNCEMENTS:
        raise AlphaContractError("Q002 frozen 244-announcement pilot accounting changed")
    return pilot_rows


def _d002_event_index(d002: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if d002.get("corpus_id") != "SS002-D002-v1" or d002.get("corpus_sha256") != D002_SHA:
        raise AlphaContractError("Q002 D002 corpus SHA mismatch")
    _closed(d002, "D002")
    docs = d002.get("documents")
    if not isinstance(docs, list):
        raise AlphaContractError("Q002 D002 documents unavailable")
    index: dict[str, dict[str, Any]] = {}
    for row in docs:
        if not isinstance(row, dict):
            raise TypeError("Q002 D002 document row must be object")
        if row.get("status") != "READY":
            continue
        url = approved_attachment_url(row.get("source_url"))
        doc_id = row.get("document_id")
        if url is None or not isinstance(doc_id, str) or len(doc_id) != 64:
            raise AlphaContractError("Q002 D002 READY document identity/URL invalid")
        events = row.get("event_ids")
        if not isinstance(events, list) or not events:
            raise AlphaContractError("Q002 D002 READY document lacks event IDs")
        for event_id in events:
            if not isinstance(event_id, str) or not event_id:
                raise AlphaContractError("Q002 D002 invalid event ID")
            if event_id in index:
                raise AlphaContractError("Q002 D002 event mapped to multiple source URLs")
            index[event_id] = row
    return index


def _d003_document_index(d003: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if d003.get("corpus_id") != "SS002-D003-v1" or d003.get("corpus_sha256") != D003_SHA:
        raise AlphaContractError("Q002 D003 corpus SHA mismatch")
    if d003.get("source_d002_corpus_sha256") != D002_SHA:
        raise AlphaContractError("Q002 D003 not bound to frozen D002 source")
    _closed(d003, "D003")
    docs = d003.get("documents")
    if not isinstance(docs, list) or len(docs) != EXPECTED_D003_DOCUMENTS:
        raise AlphaContractError("Q002 requires frozen 1539-document D003 manifest")
    result: dict[str, dict[str, Any]] = {}
    for row in docs:
        if not isinstance(row, dict):
            raise TypeError("Q002 D003 document row must be object")
        doc_id = row.get("document_id")
        if not isinstance(doc_id, str) or len(doc_id) != 64 or doc_id in result:
            raise AlphaContractError("Q002 D003 document IDs must be unique SHA strings")
        result[doc_id] = row
    return result


def build_q002_document_binding(
    *,
    queue: dict[str, Any],
    pilot: dict[str, Any],
    d002: dict[str, Any],
    d003: dict[str, Any],
) -> dict[str, Any]:
    pilot_rows = _require_d007(queue, pilot)
    d002_by_event = _d002_event_index(d002)
    d003_by_id = _d003_document_index(d003)
    packets: list[dict[str, Any]] = []
    event_states: Counter[str] = Counter()
    unique_ready_documents: set[str] = set()
    seen_event_ids: set[str] = set()

    for packet in pilot_rows:
        symbol = packet["symbol"]
        mapped_events: list[dict[str, Any]] = []
        for source in packet["announcement_evidence"]:
            event_id = source.get("event_id")
            if not isinstance(event_id, str) or not event_id or event_id in seen_event_ids:
                raise AlphaContractError("Q002 announcement event ID is duplicated or invalid")
            seen_event_ids.add(event_id)
            approved_url = source.get("source_attachment_url")
            if approved_url is None:
                if source.get("attachment_link_state") != "OFFICIAL_DOCUMENT_LINK_UNAVAILABLE":
                    raise AlphaContractError("Q002 absent NSE attachment state conflicts with Q001")
                mapped = {
                    "event_id": event_id,
                    "source_url": None,
                    "document_id": None,
                    "segment_manifest_sha256": None,
                    "segment_ids": [],
                    "segment_count": 0,
                    "binding_state": "NO_OFFICIAL_ATTACHMENT",
                    "binding_reason": "Q001 official NSE link unavailable",
                }
            else:
                if approved_attachment_url(approved_url) != approved_url:
                    raise AlphaContractError("Q002 Q001 URL is not approved NSE attachment")
                d002row = d002_by_event.get(event_id)
                if d002row is None:
                    raise AlphaContractError(f"Q002 D002 official source binding absent: {event_id}")
                if d002row.get("source_url") != approved_url:
                    raise AlphaContractError(f"Q002 D002 official URL mismatch: {event_id}")
                if symbol not in d002row.get("symbols", []):
                    raise AlphaContractError(f"Q002 issuer symbol/D002 document mismatch: {event_id}")
                doc_id = str(d002row["document_id"])
                d3 = d003_by_id.get(doc_id)
                if d3 is None:
                    raise AlphaContractError(f"Q002 D003 document SHA not found: {doc_id}")
                if event_id not in d3.get("event_ids", []) or symbol not in d3.get("symbols", []):
                    raise AlphaContractError(f"Q002 D003 event issuer association mismatch: {event_id}")
                ready = d3.get("extraction_state") == "READY"
                if ready:
                    segment_ids = d3.get("segment_ids")
                    count = d3.get("segment_count")
                    manifest_sha = d3.get("segment_manifest_sha256")
                    if (
                        not isinstance(segment_ids, list)
                        or not segment_ids
                        or not isinstance(count, int)
                        or count != len(segment_ids)
                        or len(set(segment_ids)) != len(segment_ids)
                        or not isinstance(manifest_sha, str)
                        or len(manifest_sha) != 64
                        or d3.get("hash_reproduced") is not True
                    ):
                        raise AlphaContractError(f"Q002 D003 READY text manifest invalid: {doc_id}")
                    unique_ready_documents.add(doc_id)
                    state = "TEXT_READY"
                    reason = None
                else:
                    segment_ids = []
                    count = 0
                    manifest_sha = None
                    state = "DOCUMENT_READY_TEXT_UNAVAILABLE"
                    reason = str(d3.get("extraction_state") or "UNKNOWN")
                mapped = {
                    "event_id": event_id,
                    "source_url": approved_url,
                    "document_id": doc_id,
                    "segment_manifest_sha256": manifest_sha,
                    "segment_ids": segment_ids,
                    "segment_count": count,
                    "binding_state": state,
                    "binding_reason": reason,
                }
            event_states[mapped["binding_state"]] += 1
            mapped_events.append(mapped)

        packets.append(
            {
                "symbol": symbol,
                "review_queue_rank": packet["review_queue_rank"],
                "review_state": packet["review_state"],
                "source_record_count": packet["source_record_count"],
                "corporate_action_evidence": packet["corporate_action_evidence"],
                "announcement_evidence": mapped_events,
                "review_questions": packet["review_questions"],
                "share_action_clearance_proven": False,
                "capitalization_calculation_allowed": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    bound = (
        event_states["TEXT_READY"]
        + event_states["DOCUMENT_READY_TEXT_UNAVAILABLE"]
    )
    ready_ratio = event_states["TEXT_READY"] / bound if bound else 0.0
    gates = {
        "first_50_packets_exact": len(packets) == EXPECTED_PACKETS,
        "all_244_announcement_refs_accounted": sum(event_states.values()) == EXPECTED_ANNOUNCEMENTS,
        "exact_d002_event_url_binding": True,
        "d003_document_sha_bound": True,
        "at_least_90pct_linked_events_text_ready": ready_ratio >= 0.90,
        "zero_capitalization_or_share_clearance": True,
    }
    result = {
        "schema_version": 1,
        "binding_id": BINDING_ID,
        "classification": "EVIDENCE_BOUND_SHARE_ACTION_REVIEW_NOT_CLEARANCE",
        "source_q001_queue_sha256": Q001_SHA,
        "source_d002_corpus_sha256": D002_SHA,
        "source_d003_corpus_sha256": D003_SHA,
        "pilot_packet_count": len(packets),
        "announcement_reference_count": sum(event_states.values()),
        "event_binding_state_counts": dict(sorted(event_states.items())),
        "unique_text_ready_document_count": len(unique_ready_documents),
        "approved_linked_text_ready_ratio": ready_ratio,
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_l001_adjudication_pilot": all(gates.values()),
        "packets": packets,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["binding_sha256"] = digest(result)
    return result
