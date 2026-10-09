from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlparse

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss001_l001_batch import (
    SOURCE_QUEUE_SHA,
    TRANSPORT_ID,
    build_collection_status,
    build_preflight,
    validate_and_seal_response,
    validate_config,
    validate_queue,
)


class ProviderTransportError(RuntimeError):
    """Raised on a failed external model request, without exposing API credentials."""


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _atomic_new_json(path: Path, payload: dict[str, Any]) -> None:
    """Write an append-only receipt, even with concurrent workers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as handle:
        temp = Path(handle.name)
        handle.write(
            json.dumps(
                payload, indent=2, sort_keys=True,
                ensure_ascii=False, allow_nan=False,
            ) + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())
    try:
        # Atomic hard link with EEXIST semantics: never replace a committed receipt.
        os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _pin_run_configuration(output_dir: Path, config: dict[str, Any]) -> str:
    config_sha = validate_config(config)
    path = output_dir / "run-config.json"
    if path.exists():
        existing = _load_json(path)
        if existing.get("runtime_model_config_sha256") != config_sha:
            raise AlphaContractError("R001 output directory already pinned to a different runtime")
        if existing.get("model_config") != config:
            raise AlphaContractError("R001 config bytes differ from pinned model configuration")
    else:
        _atomic_new_json(
            path,
            {
                "transport_id": TRANSPORT_ID,
                "source_queue_sha256": SOURCE_QUEUE_SHA,
                "model_config": config,
                "runtime_model_config_sha256": config_sha,
                "source_runtime_equivalence_claimed": False,
            },
        )
    return config_sha


def _provider_response(
    session: requests.Session,
    config: dict[str, Any],
    row: dict[str, Any],
) -> str:
    endpoint = config["api_endpoint"]
    parsed_loopback = urlparse(endpoint).hostname in {"localhost", "127.0.0.1", "::1"}
    token = os.environ.get(config["auth_env"])
    if not token and not parsed_loopback:
        raise ProviderTransportError("remote endpoint requires configured API secret")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    prompt = row["prompt_envelope"]
    body: dict[str, Any] = {
        "model": config["model_id"],
        "messages": [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": json.dumps(
                prompt["request"],
                sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )},
        ],
        config["token_parameter"]: config["max_completion_tokens"],
    }
    if config["json_object_mode"]:
        body["response_format"] = {"type": "json_object"}
    for key in ("temperature", "top_p"):
        if config[key] is not None:
            body[key] = config[key]

    try:
        response = session.post(
            endpoint,
            json=body,
            headers=headers,
            timeout=config["timeout_seconds"],
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise ProviderTransportError(
            f"model transport failed: {type(exc).__name__}"
        ) from exc
    if response.status_code != 200:
        raise ProviderTransportError(f"model returned HTTP {response.status_code}")
    if len(response.content) > 4_000_000:
        raise ProviderTransportError("model response exceeded maximum permitted bytes")
    try:
        payload = response.json()
        text = payload["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text:
            raise ValueError("missing model message content")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderTransportError("model returned invalid Chat Completions envelope") from exc
    return text


def _attempt_files(path: Path) -> list[Path]:
    files = sorted(path.glob("attempt-[0-9][0-9][0-9].json"))
    if len(files) >= 999:
        raise AlphaContractError("R001 exceeded request attempt limit")
    return files


def _request_dir(output_dir: Path, row: dict[str, Any]) -> Path:
    return (
        output_dir
        / "requests"
        / f"shard-{int(row['shard_id']):02d}"
        / str(row["request_id"])
    )


def execute_shard(
    *,
    queue: dict[str, Any],
    config: dict[str, Any],
    output_dir: Path,
    shard_id: int,
    max_requests: int | None = None,
    retry_failed: bool = False,
    transport: Any = None,
) -> dict[str, Any]:
    rows = validate_queue(queue)
    config_sha = _pin_run_configuration(output_dir, config)
    if shard_id not in range(16):
        raise ValueError("R001 shard_id must be 0..15")
    if max_requests is not None and max_requests <= 0:
        raise ValueError("R001 max_requests must be positive")
    pending = [row for row in rows if row["shard_id"] == shard_id]

    attempted = 0
    existing_validated = 0
    skipped_failed = 0
    successes = 0
    failures = 0

    with requests.Session() as session:
        for row in pending:
            directory = _request_dir(output_dir, row)
            attempts = _attempt_files(directory)
            records = [_load_json(path) for path in attempts]
            for record in records:
                if (
                    record.get("request_id") != row["request_id"]
                    or record.get("runtime_model_config_sha256") != config_sha
                ):
                    raise AlphaContractError("R001 previously recorded attempt has mismatched identity")
                checksum = record.get("receipt_sha256")
                if digest({key: value for key, value in record.items()
                           if key != "receipt_sha256"}) != checksum:
                    raise AlphaContractError("R001 previous receipt SHA mismatch")
                if record.get("status") == "VALIDATED":
                    sealed = record.get("sealed")
                    if not isinstance(sealed, dict):
                        raise AlphaContractError("R001 validated receipt is missing sealed output")
                    reproduced = validate_and_seal_response(
                        row, config, sealed.get("raw_model_response_text")
                    )
                    if sealed != reproduced:
                        raise AlphaContractError("R001 cached validated output was modified")
            if any(record.get("status") == "VALIDATED" for record in records):
                existing_validated += 1
                continue
            if records and not retry_failed:
                skipped_failed += 1
                continue
            if max_requests is not None and attempted >= max_requests:
                break

            attempt_no = len(attempts) + 1
            receipt: dict[str, Any] = {
                "schema_version": 1,
                "transport_id": TRANSPORT_ID,
                "source_queue_sha256": SOURCE_QUEUE_SHA,
                "runtime_model_config_sha256": config_sha,
                "source_runtime_equivalence_claimed": False,
                "request_id": row["request_id"],
                "global_request_index": row["global_request_index"],
                "shard_id": row["shard_id"],
                "prompt_sha256": row["prompt_sha256"],
                "attempt": attempt_no,
            }

            try:
                raw_content = (
                    transport(row, config)
                    if transport is not None
                    else _provider_response(session, config, row)
                )
                if not isinstance(raw_content, str):
                    raise ProviderTransportError("model response content must be a string")
                try:
                    sealed = validate_and_seal_response(row, config, raw_content)
                except (AlphaContractError, ValueError, TypeError) as exc:
                    receipt["status"] = "MODEL_OUTPUT_INVALID"
                    receipt["error"] = str(exc)
                    receipt["raw_model_response_text"] = raw_content
                    failures += 1
                else:
                    receipt["status"] = "VALIDATED"
                    receipt["sealed"] = sealed
                    successes += 1
            except ProviderTransportError as exc:
                receipt["status"] = "TRANSPORT_FAILED"
                receipt["error"] = str(exc)
                failures += 1

            receipt["receipt_sha256"] = digest(receipt)
            _atomic_new_json(directory / f"attempt-{attempt_no:03d}.json", receipt)
            attempted += 1

    return {
        "schema_version": 1,
        "transport_id": TRANSPORT_ID,
        "source_queue_sha256": SOURCE_QUEUE_SHA,
        "runtime_model_config_sha256": config_sha,
        "shard_id": shard_id,
        "expected_requests_in_shard": len(pending),
        "new_attempts": attempted,
        "new_validated": successes,
        "new_failures": failures,
        "existing_validated_skipped": existing_validated,
        "failed_requests_skipped": skipped_failed,
        "status": "PARTIAL_VALIDATED_EXTRACTIONS",
        "semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def collect_verified(
    queue: dict[str, Any],
    config: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    config_sha = _pin_run_configuration(output_dir, config)
    rows = validate_queue(queue)
    sealed_rows = []
    failure_count = 0
    for row in rows:
        attempts = _attempt_files(_request_dir(output_dir, row))
        validated = []
        for path in attempts:
            receipt = _load_json(path)
            checksum = receipt.pop("receipt_sha256", None)
            if digest(receipt) != checksum:
                raise AlphaContractError(f"R001 recorded receipt SHA mismatch: {path}")
            if receipt.get("runtime_model_config_sha256") != config_sha:
                raise AlphaContractError("R001 collection detected mixed model configurations")
            if receipt.get("request_id") != row["request_id"]:
                raise AlphaContractError("R001 collection detected tampered request ID")
            if receipt.get("status") == "VALIDATED":
                validated.append(receipt.get("sealed"))
            else:
                failure_count += 1
        if len(validated) > 1:
            raise AlphaContractError("R001 multiple accepted extractions for one request")
        if validated:
            sealed_rows.append(validated[0])

    status = build_collection_status(queue, config, sealed_rows)
    status["recorded_failure_attempt_count"] = failure_count
    status["source_runtime_equivalence_claimed"] = False
    status["collection_sha256"] = digest(
        {key: value for key, value in status.items() if key != "collection_sha256"}
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description="SS001 L001 exact-page batch transport")
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--run-shard", type=int)
    mode.add_argument("--collect", action="store_true")
    parser.add_argument("--max-requests", type=int)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()

    queue = _load_json(args.queue)
    config = _load_json(args.config)
    if args.dry_run:
        preflight = build_preflight(queue, config)
        _pin_run_configuration(args.output_dir, config)
        path = args.output_dir / "preflight.json"
        if path.exists() and _load_json(path) != preflight:
            raise AlphaContractError("R001 frozen preflight changed")
        if not path.exists():
            _atomic_new_json(path, preflight)
        print(json.dumps(preflight, sort_keys=True))
    elif args.collect:
        status = collect_verified(queue, config, args.output_dir)
        path = args.output_dir / "collection-status.json"
        # A collection status can change as more immutable request receipts arrive.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(status, sort_keys=True))
    else:
        result = execute_shard(
            queue=queue,
            config=config,
            output_dir=args.output_dir,
            shard_id=args.run_shard,
            max_requests=args.max_requests,
            retry_failed=args.retry_failed,
        )
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
