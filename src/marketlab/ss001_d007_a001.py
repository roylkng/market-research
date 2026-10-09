from __future__ import annotations

from typing import Any

from marketlab.alpha import AlphaContractError, digest

GATE_ID = "SS001-D007-A001-v1"
QUEUE_SHA = "59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618"
P1_SHA = "1a3a2f73eaed8ba09c84ab7c8d60699fa895f39d25d5797bd16138b09fd620cb"
EXPECTED_REQUESTS = 1240
EXPECTED_ISSUERS = frozenset({
    "JAYKAY", "INDIAGLYCO", "HEGAM", "IITL", "ORBTEXP", "PVRINOX",
    "GANDHITUBE", "RATNAVEER", "TEAMLEASE", "TRIVENI", "DUCON",
    "INOXGREEN",
})


def _closed(payload: dict[str, Any], label: str) -> None:
    for key in ("share_action_clearance_proven", "market_capitalization_calculated",
                "return_outcomes_opened", "portfolio_eligibility_allowed",
                "live_capital_allowed"):
        if payload.get(key) is not False:
            raise AlphaContractError(f"A001 {label} requires {key}=false")


def _count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AlphaContractError(f"A001 invalid {label}")
    return value


def assess_a001_readiness(
    queue: dict[str, Any],
    l002: dict[str, Any],
    collection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check readiness only; never authorize a share count or valuation."""
    if queue.get("queue_id") != "SS001-D007-L001-P2-v1":
        raise AlphaContractError("A001 queue identity mismatch")
    if queue.get("queue_sha256") != QUEUE_SHA:
        raise AlphaContractError("A001 queue SHA mismatch")
    if queue.get("fresh_request_count") != EXPECTED_REQUESTS:
        raise AlphaContractError("A001 queue request count mismatch")
    if queue.get("issuer_count") != 12 or queue.get("distinct_document_count") != 82:
        raise AlphaContractError("A001 source population mismatch")
    if queue.get("fresh_document_count") != 70 or queue.get("shard_count") != 16:
        raise AlphaContractError("A001 source shard/document count mismatch")
    _closed(queue, "queue")

    if l002.get("ledger_id") != "SS001-D007-L002-v1":
        raise AlphaContractError("A001 evidence ledger identity mismatch")
    if l002.get("source_queue_sha256") != QUEUE_SHA:
        raise AlphaContractError("A001 L002 queue SHA mismatch")
    if l002.get("source_p1_run_sha256") != P1_SHA:
        raise AlphaContractError("A001 native P1 evidence mismatch")
    for field, wanted in (
        ("issuer_count", 12), ("document_count", 82),
        ("reused_native_document_count", 12), ("fresh_document_count", 70),
        ("fresh_page_request_count", EXPECTED_REQUESTS),
        ("corporate_action_row_count", 12),
    ):
        if l002.get(field) != wanted:
            raise AlphaContractError(f"A001 L002 {field} mismatch")
    _closed(l002, "evidence ledger")

    issuer_rows = l002.get("issuer_pending_pages")
    if not isinstance(issuer_rows, list) or len(issuer_rows) != 12:
        raise AlphaContractError("A001 issuer pending-page ledger unavailable")
    by_symbol: dict[str, int] = {}
    for row in issuer_rows:
        if not isinstance(row, dict):
            raise AlphaContractError("A001 issuer row must be an object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or symbol in by_symbol:
            raise AlphaContractError("A001 duplicate/missing issuer identity")
        by_symbol[symbol] = _count(row.get("pending_pages"), f"{symbol} pending pages")
    if set(by_symbol) != EXPECTED_ISSUERS:
        raise AlphaContractError("A001 frozen issuer roster mismatch")

    pending = _count(l002.get("fresh_remaining_response_count"), "L002 remaining count")
    validated = _count(l002.get("fresh_validated_response_count"), "L002 validated count")
    if pending + validated != EXPECTED_REQUESTS or sum(by_symbol.values()) != pending:
        raise AlphaContractError("A001 L002 page coverage does not reconcile")

    collected = None
    if collection is not None:
        if collection.get("source_queue_sha256") != QUEUE_SHA:
            raise AlphaContractError("A001 collection source SHA mismatch")
        _closed(collection, "R001 collection")
        collected = _count(collection.get("validated_request_count"), "R001 collection count")
        if collected > EXPECTED_REQUESTS or not isinstance(
            collection.get("runtime_model_config_sha256"), str
        ):
            raise AlphaContractError("A001 R001 model/count mismatch")

    if collected == EXPECTED_REQUESTS and pending:
        status = "L002_REASSEMBLY_REQUIRED"
    elif pending:
        status = "SOURCE_EVIDENCE_PENDING"
    elif l002.get("semantic_audit_complete") is not True:
        status = "SEMANTIC_REVIEW_PENDING"
    else:
        status = "INDEPENDENT_REVIEW_LEDGER_REQUIRED"

    output = {
        "schema_version": 1,
        "gate_id": GATE_ID,
        "classification": "ISSUER_EVIDENCE_READINESS_NOT_SHARE_CLEARANCE",
        "source_queue_sha256": QUEUE_SHA,
        "issuer_count": 12,
        "fresh_page_request_count": EXPECTED_REQUESTS,
        "validated_l002_page_count": validated,
        "pending_l002_page_count": pending,
        "r001_transport_validated_count": collected,
        "issuer_pending_pages": [
            {"symbol": key, "pending_pages": by_symbol[key]}
            for key in sorted(by_symbol)
        ],
        "status": status,
        "semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["readiness_sha256"] = digest(output)
    return output
