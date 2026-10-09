from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

SELECTION_ID = "SS001-D007-L001-P2-P0-SELECTION-v1"
EXPECTED_QUEUE_ID = "SS001-D007-L001-P2-v1"
EXPECTED_QUEUE_SHA = "59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618"
EXPECTED_MODEL_CONFIG_SHA = "133b5705036d1782f671d6a171fe5f24298939cf6d84314875c2e8452e7169dc"
ISSUERS = (
    "JAYKAY",
    "INDIAGLYCO",
    "HEGAM",
    "IITL",
    "ORBTEXP",
    "PVRINOX",
    "GANDHITUBE",
    "RATNAVEER",
    "TEAMLEASE",
    "TRIVENI",
    "DUCON",
    "INOXGREEN",
)
PER_ISSUER = 2


def select_page_pilot(queue: dict[str, Any]) -> dict[str, Any]:
    if queue.get("queue_id") != EXPECTED_QUEUE_ID:
        raise AlphaContractError("P2-P0 source queue id mismatch")
    if queue.get("queue_sha256") != EXPECTED_QUEUE_SHA:
        raise AlphaContractError("P2-P0 source queue SHA mismatch")
    if queue.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
        raise AlphaContractError("P2-P0 model config SHA mismatch")
    if queue.get("fresh_request_count") != 1240:
        raise AlphaContractError("P2-P0 fresh request count mismatch")
    if queue.get("issuer_symbols") != list(ISSUERS):
        raise AlphaContractError("P2-P0 issuer order mismatch")
    if queue.get("model_inference_executed") is not False:
        raise AlphaContractError("P2-P0 source queue already claims inference")
    for field in (
        "share_action_clearance_proven",
        "market_capitalization_calculated",
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if queue.get(field) is not False:
            raise AlphaContractError(f"P2-P0 requires source {field}=false")

    requests = queue.get("requests")
    if not isinstance(requests, list) or len(requests) != 1240:
        raise AlphaContractError("P2-P0 request rows unavailable")

    selected = []
    counts: Counter[str] = Counter()
    for row in requests:
        if not isinstance(row, dict):
            raise TypeError("P2-P0 request row must be object")
        symbol = str(row.get("symbol") or "")
        if symbol not in ISSUERS:
            raise AlphaContractError("P2-P0 request has unexpected issuer")
        if counts[symbol] >= PER_ISSUER:
            continue
        prompt = row.get("prompt_envelope")
        if not isinstance(prompt, dict):
            raise AlphaContractError("P2-P0 request prompt unavailable")
        request = prompt.get("request")
        if not isinstance(request, dict):
            raise AlphaContractError("P2-P0 prompt request unavailable")
        segments = request.get("segments")
        if not isinstance(segments, list) or len(segments) != 1:
            raise AlphaContractError("P2-P0 request must contain one segment")
        if segments[0].get("segment_id") != row.get("segment_id"):
            raise AlphaContractError("P2-P0 segment identity mismatch")
        selected.append(row)
        counts[symbol] += 1

    if dict(counts) != {symbol: PER_ISSUER for symbol in ISSUERS}:
        raise AlphaContractError(f"P2-P0 issuer sample counts mismatch: {dict(counts)}")
    if len(selected) != 24:
        raise AlphaContractError("P2-P0 must select exactly 24 requests")

    output = {
        "schema_version": 1,
        "selection_id": SELECTION_ID,
        "classification": "FROZEN_PAGE_LEVEL_LLM_FEASIBILITY_SELECTION_NOT_ALPHA",
        "source_queue_id": EXPECTED_QUEUE_ID,
        "source_queue_sha256": EXPECTED_QUEUE_SHA,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "issuer_symbols": list(ISSUERS),
        "per_issuer": PER_ISSUER,
        "selected_request_count": len(selected),
        "issuer_counts": dict(sorted(counts.items())),
        "rows": selected,
        "model_inference_executed": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["selection_sha256"] = digest(output)
    return output
