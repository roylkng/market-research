from __future__ import annotations

import copy
from typing import Any

from marketlab.alpha import AlphaContractError

EXECUTION_ID = "HG006-L001-P2-v1"
QUEUE_SHA = "6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934"
MODEL_CONFIG_SHA = "043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d"
SHARD_COUNT = 16


def _segment_id(row: dict[str, Any], page_or_id: object) -> str:
    if isinstance(page_or_id, str):
        return page_or_id
    if not isinstance(page_or_id, int) or isinstance(page_or_id, bool):
        raise TypeError("evidence page reference must be integer or segment id")
    suffix = f":pdf:page:{page_or_id:04d}"
    request = row.get("prompt_envelope", {}).get("request")
    if not isinstance(request, dict):
        raise AlphaContractError("HG006 P2 request unavailable")
    segments = request.get("segments")
    if not isinstance(segments, list):
        raise AlphaContractError("HG006 P2 segments unavailable")
    matches = [
        str(segment["segment_id"])
        for segment in segments
        if isinstance(segment, dict)
        and str(segment.get("segment_id") or "").endswith(suffix)
    ]
    if len(matches) != 1:
        raise AlphaContractError(
            f"{row['request_id']}: expected one segment for page {page_or_id}, "
            f"observed {len(matches)}"
        )
    return matches[0]


def _evidence(row: dict[str, Any], refs: list[object]) -> list[str]:
    return [_segment_id(row, ref) for ref in refs]


def materialize_native_output(
    row: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    request = row.get("prompt_envelope", {}).get("request")
    if not isinstance(request, dict):
        raise AlphaContractError("HG006 P2 request unavailable")
    template = request.get("required_output_template")
    if not isinstance(template, dict):
        raise AlphaContractError("HG006 P2 output template unavailable")
    output = copy.deepcopy(template)

    output["stage_observations"] = [
        {
            "stage": stage,
            "evidence_segment_ids": _evidence(row, refs),
        }
        for stage, refs in decision.get("s", [])
    ]

    if "t" in decision:
        state, refs = decision["t"]
        output["explicit_terminal_language"] = state
        output["terminal_evidence_segment_ids"] = _evidence(row, refs)

    output["transaction_anchors"] = [
        {
            "anchor_type": anchor_type,
            "value": value,
            "evidence_segment_ids": _evidence(row, refs),
        }
        for anchor_type, value, refs in decision.get("a", [])
    ]

    if "c" in decision:
        description, refs = decision["c"]
        output["family_semantic_conflict"] = {
            "description": description,
            "evidence_segment_ids": _evidence(row, refs),
        }

    output["unresolved_questions"] = list(decision.get("u", []))
    output["contradictions_within_document"] = list(decision.get("x", []))
    output["extraction_caveats"] = list(decision.get("v", []))
    return output


def build_native_bundle(
    queue: dict[str, Any],
    p0_run: dict[str, Any],
    decisions: dict[str, Any],
    *,
    shard_id: int,
) -> dict[str, Any]:
    if not isinstance(shard_id, int) or isinstance(shard_id, bool) or not 0 <= shard_id < SHARD_COUNT:
        raise AlphaContractError("HG006 P2 shard_id out of range")
    if (
        queue.get("queue_id") != "HG006-L001-P1-v1"
        or queue.get("queue_sha256") != QUEUE_SHA
    ):
        raise AlphaContractError("unexpected frozen HG006 queue")
    if queue.get("model_config_sha256") != MODEL_CONFIG_SHA:
        raise AlphaContractError("HG006 P2 model-config SHA mismatch")

    p0_rows = p0_run.get("rows")
    if not isinstance(p0_rows, list):
        raise AlphaContractError("HG006 P2 P0 rows unavailable")
    p0_ids = {
        str(row["request_id"])
        for row in p0_rows
        if isinstance(row, dict)
    }

    queue_rows = queue.get("requests")
    if not isinstance(queue_rows, list):
        raise AlphaContractError("HG006 P2 queue rows unavailable")
    shard_rows = [
        row
        for row in queue_rows
        if isinstance(row, dict) and int(row.get("shard_id", -1)) == shard_id
    ]
    if not shard_rows:
        raise AlphaContractError("HG006 P2 frozen shard is empty")
    pending = [
        row for row in shard_rows if str(row["request_id"]) not in p0_ids
    ]

    if not isinstance(decisions, dict):
        raise TypeError("HG006 P2 native decisions must be object")
    for request_id, decision in decisions.items():
        if not request_id or not isinstance(decision, dict):
            raise TypeError("HG006 P2 native decisions must map request IDs to objects")
    pending_ids = {str(row["request_id"]) for row in pending}
    if pending_ids != set(decisions):
        missing = sorted(pending_ids - set(decisions))
        extra = sorted(set(decisions) - pending_ids)
        raise AlphaContractError(
            f"HG006 P2 shard {shard_id:02d} decision accounting mismatch "
            f"missing={missing} extra={extra}"
        )

    responses = [
        {
            "request_id": str(row["request_id"]),
            "status": "MODEL_OUTPUT",
            "model_output": materialize_native_output(
                row,
                decisions[str(row["request_id"])],
            ),
        }
        for row in sorted(pending, key=lambda item: str(item["request_id"]))
    ]

    return {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "bundle_id": f"HG006-L001-P2-SHARD-{shard_id:02d}-NATIVE-v1",
        "source_queue_sha256": QUEUE_SHA,
        "model_config_sha256": MODEL_CONFIG_SHA,
        "shard_id": shard_id,
        "fresh_response_count": len(responses),
        "p0_reuse_count": len(shard_rows) - len(pending),
        "responses": responses,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
