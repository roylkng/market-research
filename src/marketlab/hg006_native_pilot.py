from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

SELECTION_ID = "HG006-L001-P0-SELECTION-v1"
EXPECTED_QUEUE_ID = "HG006-L001-P1-v1"
EXPECTED_QUEUE_SHA = "6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934"
EXPECTED_MODEL_CONFIG_SHA = "043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d"
FAMILIES = ("PREFERENTIAL_WARRANT", "SCHEME_REORGANISATION")
PER_FAMILY = 10


def select_native_pilot(queue: dict[str, Any]) -> dict[str, Any]:
    if queue.get("queue_id") != EXPECTED_QUEUE_ID:
        raise AlphaContractError("HG006 P0 requires frozen L001 P1 queue")
    if queue.get("queue_sha256") != EXPECTED_QUEUE_SHA:
        raise AlphaContractError("HG006 P0 queue SHA mismatch")
    if queue.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
        raise AlphaContractError("HG006 P0 model config SHA mismatch")
    if queue.get("request_count") != 1448:
        raise AlphaContractError("HG006 P0 queue request count mismatch")
    for field in (
        "historical_terminal_labels_opened",
        "completion_probabilities_assigned",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if queue.get(field) is not False:
            raise AlphaContractError(f"HG006 P0 requires queue {field}=false")

    rows = queue.get("requests")
    if not isinstance(rows, list) or len(rows) != 1448:
        raise AlphaContractError("HG006 P0 queue rows unavailable")
    by_family: dict[str, list[dict[str, Any]]] = {family: [] for family in FAMILIES}
    seen_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 P0 queue row must be object")
        request_id = str(row.get("request_id") or "")
        family = str(row.get("family") or "")
        if not request_id or request_id in seen_ids:
            raise AlphaContractError("HG006 P0 request IDs must be unique")
        seen_ids.add(request_id)
        if family in by_family:
            by_family[family].append(row)

    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for family in FAMILIES:
        family_rows = sorted(by_family[family], key=lambda row: str(row["request_id"]))
        if len(family_rows) < PER_FAMILY:
            raise AlphaContractError(f"HG006 P0 insufficient requests for {family}")
        chosen = family_rows[:PER_FAMILY]
        selected.extend(chosen)
        counts[family] = len(chosen)

    selected = sorted(selected, key=lambda row: str(row["request_id"]))
    output = {
        "schema_version": 1,
        "selection_id": SELECTION_ID,
        "classification": "DETERMINISTIC_NATIVE_HISTORICAL_LLM_FEASIBILITY_SAMPLE_NOT_LABELS",
        "source_queue_sha256": EXPECTED_QUEUE_SHA,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "selection_rule": "LEXICOGRAPHIC_FIRST_10_REQUEST_IDS_PER_FAMILY",
        "selected_request_count": len(selected),
        "selected_counts_by_family": dict(sorted(counts.items())),
        "rows": selected,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["selection_sha256"] = digest(output)
    return output
