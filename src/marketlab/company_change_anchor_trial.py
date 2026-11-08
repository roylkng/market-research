"""Credential-free paired model trial using exact source-block selection.

Separate from production interpretation. Pins, sources and prompts seal before
inference. Failed outputs remain in the denominator and no result approves a buy.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

import requests

from marketlab.company_change import ChangeError, canonical_hash, timestamp
from marketlab.company_change_anchors import make_payload, validate_response
from marketlab.company_change_model_trial import (
    file_sha,
    score_trial,
    select_cases,
    table_counts,
    write_sealed,
)
from marketlab.company_change_pipeline import model_config
from marketlab.company_change_semantics import checked_reading
from marketlab.company_change_store import EvidenceStore, loads_unique

VERSION = "CC001-ANCHORED-MODEL-TRIAL-v1"
ENDPOINT = "http://127.0.0.1:18766/v1/chat/completions"
RUNTIME = "053b1539c02617eff744f89525ee57497c3c1fbe"


def validate_pin(pin: dict) -> None:
    if set(pin) != {"runtime_commit", "case_symbols", "models", "context_tokens", "max_output_tokens", "threads"}:
        raise ChangeError("incomplete anchored trial pin")
    if pin["runtime_commit"] != RUNTIME or set(pin["models"]) != {"small", "large"}:
        raise ChangeError("unexpected pinned comparison")
    if pin["case_symbols"] != ["SEAMECLTD", "DHRUV", "VIKRAN", "PRESTIGE"]:
        raise ChangeError("development source denominator changed")
    for key, limit in (("context_tokens", 16384), ("max_output_tokens", 1536), ("threads", 4)):
        if type(pin[key]) is not int or not 1 <= pin[key] <= limit:
            raise ChangeError("unbounded trial runtime")
    for key, setting in pin["models"].items():
        expected = "1.5B" if key == "small" else "7B"
        if (set(setting) != {"repository", "revision", "alias", "files"}
                or setting["repository"] != f"Qwen/Qwen2.5-{expected}-Instruct-GGUF"
                or not re.fullmatch(r"[0-9a-f]{40}", setting["revision"])
                or setting["alias"] != "cc001-anchored-" + key
                or len(setting["files"]) != (1 if key == "small" else 2)):
            raise ChangeError("unapproved model identity or revision")
        names = set()
        for f in setting["files"]:
            if (set(f) != {"filename", "sha256"}
                    or not re.fullmatch(r"qwen2\.5-[a-z0-9._-]+\.gguf", f["filename"])
                    or not re.fullmatch(r"[0-9a-f]{64}", f["sha256"])
                    or f["filename"] in names):
                raise ChangeError("invalid model shard pin")
            names.add(f["filename"])


def certify(pin: dict, key: str, folder: Path, binary: Path, commit: str, now: str) -> dict:
    validate_pin(pin)
    if key not in pin["models"] or commit != pin["runtime_commit"]:
        raise ChangeError("model key or runtime differs from pin")
    evidence = []
    for spec in pin["models"][key]["files"]:
        path = folder / spec["filename"]
        if (path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 5_000_000_000
                or file_sha(path) != spec["sha256"]):
            raise ChangeError("model shard content mismatch")
        evidence.append({**spec, "bytes": path.stat().st_size})
    if sum(f["bytes"] for f in evidence) > 6_000_000_000 or binary.is_symlink() or not binary.is_file():
        raise ChangeError("model budget or runtime binary invalid")
    return {"model_key": key, "model": pin["models"][key], "weights": evidence,
            "runtime_commit": commit, "runtime_binary_sha256": file_sha(binary),
            "pin_sha256": canonical_hash(pin), "recorded_at": timestamp(now).isoformat()}


def one_attempt(store: EvidenceStore, reading: dict, model: str, max_tokens: int,
                *, session=None) -> dict:
    checked_reading(store, reading)
    if os.environ.get("CC001_MODEL_API_KEY"):
        raise ChangeError("local trial must not use a provider credential")
    config = model_config()
    if config["url"] != ENDPOINT or config["model"] != model:
        raise ChangeError("only the declared loopback model is allowed")
    payload, evidence = make_payload(reading, model, max_tokens)
    request = {"engine": VERSION, "endpoint": ENDPOINT, "payload": payload,
               "catalog": evidence, "reading_sha256": reading["reading_sha256"],
               "code_sha256": canonical_hash([file_sha(Path(__file__)), file_sha(Path(make_payload.__code__.co_filename))])}
    request_id = canonical_hash(request)
    request_sha = store.put_blob(json.dumps(request, sort_keys=True, ensure_ascii=False).encode())
    store.db.execute("""CREATE TABLE IF NOT EXISTS cc_anchor_attempts(
        id TEXT PRIMARY KEY, payload TEXT NOT NULL)""")
    store.db.commit()
    result = {"request_id": request_id, "request_blob_sha256": request_sha,
              "reading_sha256": reading["reading_sha256"], "status": "RUNNING",
              "started_at": store.clock(), "model_called": True,
              "generation": {}, "live_capital_allowed": False}
    with store.transaction():
        prior = store.db.execute("SELECT payload FROM cc_anchor_attempts WHERE id=?", (request_id,)).fetchone()
        if prior:
            retained = loads_unique(prior[0])
            if retained.get("request_id") != request_id or retained.get("reading_sha256") != reading["reading_sha256"]:
                raise ChangeError("retained attempt identity mismatch")
            if retained["status"] != "RUNNING" and canonical_hash({k: v for k, v in retained.items() if k != "result_sha256"}) != retained.get("result_sha256"):
                raise ChangeError("retained attempt integrity failure")
            return {**retained, "reused_attempt": True}
        store.db.execute("INSERT INTO cc_anchor_attempts VALUES (?,?)", (request_id, json.dumps(result)))
    client = session or requests.Session()
    started = time.monotonic()
    try:
        if session is None:
            client.trust_env = False
        with client.post(ENDPOINT, json=payload, stream=True, timeout=(10, 360),
                         allow_redirects=False) as response:
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2 * 1024 * 1024:
                    raise ChangeError("provider response exceeds limit")
                chunks.append(chunk)
            raw = b"".join(chunks)
            result["response_blob_sha256"] = store.put_blob(raw)
            if response.status_code != 200:
                raise ChangeError(f"provider HTTP status {response.status_code}")
        envelope = loads_unique(raw)
        if isinstance(envelope, dict):
            usage = envelope.get("usage")
            choices = envelope.get("choices")
            tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
            finish = choices[0].get("finish_reason") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
            result["generation"] = {"completion_tokens": tokens if type(tokens) is int and tokens >= 0 else None,
                                    "finish_reason": finish}
        result.update(validate_response(raw, reading, evidence))
    except (ValueError, TypeError, KeyError, OSError, requests.RequestException) as exc:
        result.update(status="FAILED_NO_AUTOMATIC_RETRY", error_type=type(exc).__name__,
                      reason=str(exc) if isinstance(exc, ChangeError) else "Transport or validation failed")
    finally:
        if session is None:
            client.close()
    result.update(finished_at=store.clock(), elapsed_seconds=round(time.monotonic() - started, 3))
    result["result_sha256"] = canonical_hash(result)
    with store.transaction():
        store.db.execute("UPDATE cc_anchor_attempts SET payload=? WHERE id=?",
                         (json.dumps(result, allow_nan=False), request_id))
    return result


def run(store: EvidenceStore, pin: dict, receipt: dict, sources: list[dict], folder: Path) -> dict:
    validate_pin(pin)
    if (receipt.get("pin_sha256") != canonical_hash(pin) or receipt.get("model_key") not in pin["models"]
            or receipt.get("model") != pin["models"][receipt["model_key"]]):
        raise ChangeError("runtime receipt does not match the declared trial")
    key = receipt["model_key"]
    cases = select_cases(store, sources, pin["case_symbols"])
    before = table_counts(store)
    plan = {"engine": VERSION, "runtime": receipt, "pin": pin,
            "sources": sources, "labels_in_requests": False,
            "worker_code_sha256": file_sha(Path(__file__)),
            "anchor_code_sha256": file_sha(Path(make_payload.__code__.co_filename)),
            "planned_cases": len(cases), "policy": "SEEN_DEVELOPMENT_CASES_NOT_INDEPENDENT_HOLDOUT"}
    plan["plan_sha256"] = canonical_hash(plan)
    write_sealed(folder / "plan.json", plan)
    attempts = []
    for case in cases:
        if case["missing"]:
            result = {"status": "MISSING_SOURCE", "model_called": False}
        else:
            result = one_attempt(store, case["reading"], pin["models"][key]["alias"], pin["max_output_tokens"])
        attempts.append({"symbol": case["source"]["symbol"], "source": case["source"], **result})
    after = table_counts(store)
    if before != after:
        raise ChangeError("trial changed reviews or financial tables")
    report = {"engine": VERSION, "as_of": store.clock(), "model_key": key,
              "plan_sha256": plan["plan_sha256"], "attempts": attempts, "planned_cases": len(cases),
              "evaluation_scope": plan["policy"], "source_review_counts_before": before,
              "source_review_counts_after": after, "production_activation": False,
              "live_capital_allowed": False}
    report["report_sha256"] = canonical_hash(report)
    write_sealed(folder / "predictions.json", report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "score"))
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--pin", type=Path)
    parser.add_argument("--model-key", choices=("small", "large"))
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--server", type=Path)
    parser.add_argument("--runtime-commit")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    fixture = loads_unique(args.fixture.read_bytes())
    if args.mode == "run":
        if any(getattr(args, k) is None for k in ("workspace", "pin", "model_key", "model_dir", "server", "runtime_commit")):
            raise ChangeError("run requires workspace and pinned runtime inputs")
        pin = loads_unique(args.pin.read_bytes())
        sources = [r["source"] for r in fixture]
        with EvidenceStore(args.workspace) as store:
            receipt = certify(pin, args.model_key, args.model_dir, args.server, args.runtime_commit, store.clock())
            write_sealed(args.output / "runtime.json", receipt)
            report = run(store, pin, receipt, sources, args.output)
        print(json.dumps({"model": args.model_key, "report_sha256": report["report_sha256"]}))
    else:
        predictions = loads_unique((args.output / "predictions.json").read_bytes())
        report = score_trial(predictions, fixture)
        report.pop("score_sha256")
        report.update(engine=VERSION, model_key=predictions["model_key"],
                      evidence_validation_scope="EXACT_SOURCE_LOCATIONS_NOT_SEMANTIC_ENTAILMENT")
        report["score_sha256"] = canonical_hash(report)
        write_sealed(args.output / "score.json", report)
        print(json.dumps(report, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
