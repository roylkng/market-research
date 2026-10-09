from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss001_d007_l002 import build_issuer_evidence
from marketlab.ss001_l001_batch import validate_config, validate_queue


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _read_verified_responses(
    queue: dict[str, Any],
    config: dict[str, Any],
    output_dir: Path,
) -> list[dict[str, Any]]:
    rows = validate_queue(queue)
    config_sha = validate_config(config)
    run_config_path = output_dir / "run-config.json"
    if not run_config_path.is_file():
        raise AlphaContractError("L002 R001 run configuration receipt is missing")
    pinned = _read_json(run_config_path)
    if pinned.get("runtime_model_config_sha256") != config_sha or pinned.get("model_config") != config:
        raise AlphaContractError("L002 R001 run config differs from pinned receipt")

    collected: list[dict[str, Any]] = []
    for row in rows:
        directory = (
            output_dir / "requests" / f"shard-{int(row['shard_id']):02d}"
            / str(row["request_id"])
        )
        accepted = []
        for path in sorted(directory.glob("attempt-[0-9][0-9][0-9].json")):
            receipt = _read_json(path)
            sha = receipt.get("receipt_sha256")
            body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
            if sha != digest(body):
                raise AlphaContractError(f"L002 R001 receipt SHA mismatch: {path}")
            if (
                receipt.get("request_id") != row["request_id"]
                or receipt.get("runtime_model_config_sha256") != config_sha
            ):
                raise AlphaContractError("L002 R001 attempt identity mismatch")
            if receipt.get("status") == "VALIDATED":
                accepted.append(receipt.get("sealed"))
        if len(accepted) > 1:
            raise AlphaContractError("L002 multiple accepted R001 responses for one page")
        if accepted:
            if not isinstance(accepted[0], dict):
                raise TypeError("L002 accepted R001 response must be an object")
            collected.append(accepted[0])
    return collected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize source-validated D007 L002 issuer evidence ledger"
    )
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--p1-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--r001-root", type=Path)
    parser.add_argument("--r001-config", type=Path)
    parser.add_argument("--require-full", action="store_true")
    args = parser.parse_args()

    queue = _read_json(args.queue)
    p1_run = _read_json(args.p1_run)

    if bool(args.r001_root) != bool(args.r001_config):
        parser.error("--r001-root and --r001-config must be supplied together")
    config = _read_json(args.r001_config) if args.r001_config else None
    collected = (
        _read_verified_responses(queue, config, args.r001_root)
        if config is not None and args.r001_root is not None
        else []
    )

    ledger = build_issuer_evidence(
        queue,
        p1_run,
        runtime_config=config,
        validated_r001_rows=collected,
    )
    if args.require_full and ledger["fresh_remaining_response_count"]:
        raise AlphaContractError("L002 requires all 1,240 frozen page responses")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "ledger_id": ledger["ledger_id"],
        "ledger_sha256": ledger["ledger_sha256"],
        "status": ledger["status"],
        "issuer_count": ledger["issuer_count"],
        "document_count": ledger["document_count"],
        "prior_native_document_count": ledger["prior_native_document_count"],
        "fresh_validated_response_count": ledger["fresh_validated_response_count"],
        "fresh_remaining_response_count": ledger["fresh_remaining_response_count"],
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
