from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from marketlab.alpha import AlphaContractError

EXECUTION_ID = "HG006-L001-P2-v1"
QUEUE_SHA = "6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934"
MODEL_CONFIG_SHA = "043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d"
SHARD_ID = 0
EXPECTED_FRESH_COUNT = 77
PART_COUNT = 8


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def _load_decisions(root: Path) -> dict:
    merged: dict[str, dict] = {}
    for part in range(PART_COUNT):
        path = root / f"part-{part:02d}.json"
        payload = _load(path)
        for request_id, decision in payload.items():
            if request_id in merged:
                raise AlphaContractError(
                    f"HG006 shard 00 duplicate model decision: {request_id}"
                )
            if not isinstance(decision, dict):
                raise TypeError("HG006 shard 00 model decision must be object")
            merged[request_id] = decision
    if len(merged) != EXPECTED_FRESH_COUNT:
        raise AlphaContractError(
            f"HG006 shard 00 expected {EXPECTED_FRESH_COUNT} fresh decisions, "
            f"observed {len(merged)}"
        )
    return merged


def _segment_id(row: dict, page_or_id: object) -> str:
    if isinstance(page_or_id, str):
        return page_or_id
    if not isinstance(page_or_id, int) or isinstance(page_or_id, bool):
        raise TypeError("evidence page reference must be integer or segment id")
    suffix = f":pdf:page:{page_or_id:04d}"
    request = row.get("prompt_envelope", {}).get("request")
    if not isinstance(request, dict):
        raise AlphaContractError("HG006 shard 00 request unavailable")
    segments = request.get("segments")
    if not isinstance(segments, list):
        raise AlphaContractError("HG006 shard 00 segments unavailable")
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


def _evidence(row: dict, refs: list[object]) -> list[str]:
    return [_segment_id(row, ref) for ref in refs]


def _materialize_output(row: dict, decision: dict) -> dict:
    request = row.get("prompt_envelope", {}).get("request")
    if not isinstance(request, dict):
        raise AlphaContractError("HG006 shard 00 request unavailable")
    template = request.get("required_output_template")
    if not isinstance(template, dict):
        raise AlphaContractError("HG006 shard 00 output template unavailable")
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


def build_bundle(queue: dict, p0_run: dict, decisions: dict) -> dict:
    if (
        queue.get("queue_id") != "HG006-L001-P1-v1"
        or queue.get("queue_sha256") != QUEUE_SHA
    ):
        raise AlphaContractError("unexpected frozen HG006 queue")
    if queue.get("model_config_sha256") != MODEL_CONFIG_SHA:
        raise AlphaContractError("HG006 shard 00 model-config SHA mismatch")

    p0_rows = p0_run.get("rows")
    if not isinstance(p0_rows, list):
        raise AlphaContractError("HG006 shard 00 P0 rows unavailable")
    p0_ids = {str(row["request_id"]) for row in p0_rows if isinstance(row, dict)}

    queue_rows = queue.get("requests")
    if not isinstance(queue_rows, list):
        raise AlphaContractError("HG006 shard 00 queue rows unavailable")
    shard_rows = [
        row
        for row in queue_rows
        if isinstance(row, dict) and int(row.get("shard_id", -1)) == SHARD_ID
    ]
    if len(shard_rows) != 79:
        raise AlphaContractError(
            f"HG006 shard 00 expected 79 requests, observed {len(shard_rows)}"
        )
    pending = [
        row for row in shard_rows if str(row["request_id"]) not in p0_ids
    ]
    if len(pending) != EXPECTED_FRESH_COUNT:
        raise AlphaContractError(
            f"HG006 shard 00 expected {EXPECTED_FRESH_COUNT} pending requests, "
            f"observed {len(pending)}"
        )

    pending_ids = {str(row["request_id"]) for row in pending}
    if pending_ids != set(decisions):
        missing = sorted(pending_ids - set(decisions))
        extra = sorted(set(decisions) - pending_ids)
        raise AlphaContractError(
            f"HG006 shard 00 model-decision accounting mismatch "
            f"missing={missing} extra={extra}"
        )

    responses = [
        {
            "request_id": str(row["request_id"]),
            "status": "MODEL_OUTPUT",
            "model_output": _materialize_output(
                row,
                decisions[str(row["request_id"])],
            ),
        }
        for row in sorted(pending, key=lambda item: str(item["request_id"]))
    ]

    return {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "bundle_id": "HG006-L001-P2-SHARD-00-NATIVE-v1",
        "source_queue_sha256": QUEUE_SHA,
        "model_config_sha256": MODEL_CONFIG_SHA,
        "shard_id": SHARD_ID,
        "fresh_response_count": len(responses),
        "p0_reuse_count": len(shard_rows) - len(pending),
        "responses": responses,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--p0-run", type=Path, required=True)
    parser.add_argument("--decisions-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    bundle = build_bundle(
        _load(args.queue),
        _load(args.p0_run),
        _load_decisions(args.decisions_dir),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            bundle,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "bundle_id": bundle["bundle_id"],
                "fresh_response_count": bundle["fresh_response_count"],
                "p0_reuse_count": bundle["p0_reuse_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
