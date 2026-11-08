"""Measure actual local inference separately from correctness and release approval.

Uses the existing semantic worker and exact source checks unchanged. Expected
labels are scored only after predictions are sealed and never enter requests.
A completed experiment is not a production model approval or investment edge.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash, strict_keys, timestamp
from marketlab.company_change_news_review import SOURCE_KEYS
from marketlab.company_change_pipeline import model_config
from marketlab.company_change_semantics import checked_reading, propose, score_events
from marketlab.company_change_store import EvidenceStore, loads_unique, writable_workspace

VERSION = "CC001-OPEN-MODEL-TRIAL-v1"
PIN_KEYS = {"schema_version", "model_repository", "model_revision", "model_filename",
            "model_sha256", "model_bytes", "runtime_repository", "runtime_commit",
            "server_alias", "context_tokens", "max_output_tokens", "threads", "port",
            "evaluation_scope", "case_symbols"}


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def validate_pin(pin: dict) -> None:
    strict_keys(pin, PIN_KEYS, "model trial pin")
    if set(pin) != PIN_KEYS or type(pin["schema_version"]) is not int or pin["schema_version"] != 1:
        raise ChangeError("incomplete trial pin")
    for key in ("model_revision", "runtime_commit"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(pin[key])):
            raise ChangeError("model and runtime must use immutable commit revisions")
    if not re.fullmatch(r"[0-9a-f]{64}", str(pin["model_sha256"])):
        raise ChangeError("model content hash required")
    if pin["model_repository"] != "Qwen/Qwen2.5-1.5B-Instruct-GGUF" or pin["runtime_repository"] != "ggml-org/llama.cpp":
        raise ChangeError("trial limited to explicitly inspected official repositories")
    if not re.fullmatch(r"[a-z0-9._-]+\.gguf", str(pin["model_filename"])):
        raise ChangeError("unsafe model filename")
    if not re.fullmatch(r"[a-z0-9._-]{1,80}", str(pin["server_alias"])):
        raise ChangeError("invalid local model alias")
    for key, low, high in (("model_bytes", 1, 2_000_000_000), ("context_tokens", 2048, 16384),
                           ("max_output_tokens", 256, 2048), ("threads", 1, 4), ("port", 1024, 65535)):
        if type(pin[key]) is not int or not low <= pin[key] <= high:
            raise ChangeError("invalid bounded runtime setting: " + key)
    if (not isinstance(pin["case_symbols"], list) or not 1 <= len(pin["case_symbols"]) <= 4
            or len(set(pin["case_symbols"])) != len(pin["case_symbols"])
            or not all(isinstance(s, str) and re.fullmatch(r"[A-Z0-9&._-]{1,30}", s) for s in pin["case_symbols"])):
        raise ChangeError("trial requires one to four distinct declared issuers")
    if pin["evaluation_scope"] != "SEEN_DEVELOPMENT_CASES_NOT_INDEPENDENT_HOLDOUT":
        raise ChangeError("the existing development fixtures cannot be relabelled independent")


def runtime_receipt(pin: dict, model: Path, server: Path, source_commit: str, observed_at: str) -> dict:
    validate_pin(pin)
    if source_commit != pin["runtime_commit"]:
        raise ChangeError("runtime checkout differs from locked revision")
    if model.is_symlink() or not model.is_file() or model.stat().st_size != pin["model_bytes"]:
        raise ChangeError("model file size or type mismatch")
    if file_sha(model) != pin["model_sha256"]:
        raise ChangeError("model weight hash mismatch")
    if server.is_symlink() or not server.is_file():
        raise ChangeError("local server binary unavailable")
    receipt = {"engine": VERSION, "pin_sha256": canonical_hash(pin),
               "model_sha256": pin["model_sha256"], "model_bytes": pin["model_bytes"],
               "server_sha256": file_sha(server), "runtime_commit": source_commit,
               "recorded_at": timestamp(observed_at).isoformat(), "hardware": "CPU",
               "provider_credentials_required": False, "production_activation": False}
    receipt["receipt_sha256"] = canonical_hash(receipt)
    return receipt


def write_sealed(path: Path, payload: dict) -> None:
    data = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ChangeError("refusing to overwrite a different sealed trial artifact")


def select_cases(store: EvidenceStore, sources: list[dict], symbols: list[str]) -> list[dict]:
    """Choose exact original documents, never labels, model successes or returns."""
    if len(sources) != len(symbols) or {s.get("symbol") for s in sources} != set(symbols):
        raise ChangeError("trial source set differs from declared denominator")
    readings = []
    exists = store.db.execute("SELECT name FROM sqlite_master WHERE name='cc_news_readings'").fetchone()
    stored = [loads_unique(row[0]) for row in store.db.execute("SELECT payload FROM cc_news_readings")] if exists else []
    for symbol in symbols:
        selected = [s for s in sources if s["symbol"] == symbol]
        if len(selected) != 1 or set(selected[0]) != SOURCE_KEYS:
            raise ChangeError("one exact source reference is required per issuer")
        source = selected[0]
        matches = [r for r in stored if all(r.get(k) == source[k] for k in SOURCE_KEYS)]
        if not matches:
            # Keep a missing case in the manifest instead of silently reducing n.
            readings.append({"source": source, "missing": True})
            continue
        reading = max(matches, key=lambda r: (timestamp(r["known_at"]), r["reading_sha256"]))
        checked_reading(store, reading)
        readings.append({"source": source, "reading": reading, "missing": False})
    return readings


def table_counts(store: EvidenceStore) -> dict:
    counts = {}
    for name in ("cc_news_reviews", "reviews", "extractions", "decisions"):
        exists = store.db.execute("SELECT name FROM sqlite_master WHERE name=?", (name,)).fetchone()
        counts[name] = store.db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] if exists else 0
    return counts


def run_trial(store: EvidenceStore, pin: dict, receipt: dict, sources: list[dict], folder: Path,
              *, executor=propose) -> dict:
    validate_pin(pin)
    if (receipt.get("pin_sha256") != canonical_hash(pin)
            or canonical_hash({k: v for k, v in receipt.items() if k != "receipt_sha256"}) != receipt.get("receipt_sha256")
            or receipt.get("model_sha256") != pin["model_sha256"]
            or receipt.get("runtime_commit") != pin["runtime_commit"]):
        raise ChangeError("runtime receipt and trial pin disagree")
    if os.environ.get("CC001_MODEL_API_KEY"):
        raise ChangeError("credential-free local trial must not receive a provider API key")
    config = model_config()
    expected_url = f"http://127.0.0.1:{pin['port']}/v1/chat/completions"
    if config["url"] != expected_url or config["model"] != pin["server_alias"]:
        raise ChangeError("trial must use the declared loopback model endpoint")
    cases = select_cases(store, sources, pin["case_symbols"])
    plan = {"engine": VERSION, "pin": pin, "runtime_receipt_sha256": receipt["receipt_sha256"],
            "worker_code_sha256": file_sha(Path(propose.__code__.co_filename)),
            "cases": [{"source": c["source"], "missing": c["missing"],
                       "reading_sha256": c["reading"]["reading_sha256"] if not c["missing"] else None} for c in cases],
            "labels_in_requests": False, "automatic_review_approval": False}
    plan["plan_sha256"] = canonical_hash(plan)
    write_sealed(folder / "plan.json", plan)
    before = table_counts(store)
    results = []
    for case in cases:
        if case["missing"]:
            results.append({"symbol": case["source"]["symbol"], "source": case["source"],
                            "status": "MISSING_SOURCE", "model_called": False})
            continue
        start = time.monotonic()
        reading = case["reading"]
        result = executor(store, reading, execute=True, config=config, max_tokens=pin["max_output_tokens"])
        generation = {"completion_tokens": None, "finish_reason": None}
        if result.get("response_blob_sha256"):
            try:
                body = loads_unique(store.read_blob(result["response_blob_sha256"]))
                count = body.get("usage", {}).get("completion_tokens")
                generation["completion_tokens"] = count if type(count) is int and count >= 0 else None
                choices = body.get("choices", [])
                generation["finish_reason"] = choices[0].get("finish_reason") if choices else None
            except (ValueError, TypeError, KeyError, AttributeError):
                pass
        results.append({"symbol": reading["symbol"], "source": case["source"],
                        "generation": generation, "elapsed_seconds": round(time.monotonic() - start, 3), **result})
    after = table_counts(store)
    if before != after:
        raise ChangeError("model trial unexpectedly mutated reviews or financial decision tables")
    report = {"engine": VERSION, "as_of": store.clock(), "plan_sha256": plan["plan_sha256"],
              "evaluation_scope": pin["evaluation_scope"], "attempts": results,
              "planned_cases": len(cases), "source_review_counts_before": before,
              "source_review_counts_after": after, "production_activation": False,
              "live_capital_allowed": False}
    report["report_sha256"] = canonical_hash(report)
    write_sealed(folder / "predictions.json", report)
    return report


def score_trial(report: dict, fixture: list[dict]) -> dict:
    """A score can be zero while measurement succeeded. Never equate the two."""
    if canonical_hash({k: v for k, v in report.items() if k != "report_sha256"}) != report.get("report_sha256"):
        raise ChangeError("predictions were modified before scoring")
    labels, predictions, rows = {}, {}, []
    by_source = {canonical_hash(r["source"]): r for r in fixture}
    if len(by_source) != len(fixture):
        raise ChangeError("duplicate source labels")
    if {canonical_hash(r["source"]) for r in report["attempts"]} != set(by_source):
        raise ChangeError("labels must cover the entire frozen source denominator")
    for attempt in report["attempts"]:
        key = canonical_hash(attempt["source"])
        expected = by_source[key]
        labels[key] = [{k: expected[k] for k in ("category", "stage", "actor_scope")}]
        if attempt["status"] != "MISSING_SOURCE":
            predictions[key] = attempt
        rows.append({"symbol": attempt["symbol"], "status": attempt["status"],
                     "reason": attempt.get("reason"), "elapsed_seconds": attempt.get("elapsed_seconds"),
                     "expected": labels[key][0], "proposed": [
                         {k: p[k] for k in ("category", "stage", "actor_scope")}
                         for p in attempt.get("proposals", [])],
                     "request_id": attempt.get("request_id"),
                     "response_blob_sha256": attempt.get("response_blob_sha256"),
                     "generation": attempt.get("generation", {})})
    metrics = score_events(predictions, {"provenance": report["evaluation_scope"], "cases": labels})
    valid = sum(r["status"] == "PROPOSED" for r in rows)
    retained = sum(bool(r["response_blob_sha256"]) for r in rows)
    output = {"engine": VERSION, "input_report_sha256": report["report_sha256"],
              "planned_cases": report["planned_cases"], "retained_provider_responses": retained,
              "cases_with_generated_tokens": sum((r["generation"].get("completion_tokens") or 0) > 0 for r in rows),
              "source_validated_proposals": valid, "status_counts": dict(Counter(r["status"] for r in rows)),
              "classification_metrics": metrics, "cases": rows,
              "measurement_has_all_responses": retained == report["planned_cases"],
              "release_decision": "HOLD_NO_INDEPENDENT_VALIDATION",
              "production_model_approved": False, "live_capital_allowed": False,
              "limits": ["Four seen development cases are not an independent or representative quality estimate.",
                         "Exact quotations do not prove correct interpretation or complete event extraction.",
                         "A successful runtime experiment does not establish prediction performance."]}
    output["score_sha256"] = canonical_hash(output)
    return output


def render(score: dict) -> str:
    def esc(v):
        return html.escape(str(v), quote=True)
    rows = "".join(f"<tr><td>{esc(r['symbol'])}</td><td>{esc(r['status'])}</td>"
                   f"<td>{esc(r['reason'] or '')}</td><td>{esc(r['elapsed_seconds'])}</td></tr>"
                   for r in score["cases"])
    return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Actual model trial</title><style>*{box-sizing:border-box}body{font:16px system-ui;margin:0;background:#f4f6f5;color:#19343f}main{max-width:1080px;margin:auto;padding:28px 20px}.banner{padding:20px;background:#19343f;color:white;border-radius:12px}table{width:100%;table-layout:fixed;border-collapse:collapse;margin:24px 0}td,th{text-align:left;padding:12px 5px;border-bottom:1px solid #ccd;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}</style><main><h1>Inference ran. Did it survive the evidence checks?</h1><div class='banner'><b>Release status: HOLD</b><p>Measured generation, source validation and classification agreement are different results. This is a development sample, not investment-performance evidence.</p></div>""" + f"<p>{score['retained_provider_responses']} retained responses out of {score['planned_cases']} planned cases. {score['source_validated_proposals']} source-validated proposals.</p><table><tr><th>Issuer</th><th>Outcome</th><th>Reason</th><th>Seconds</th></tr>{rows}</table><pre>{esc(json.dumps(score['classification_metrics'], indent=2))}</pre></main></html>"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    certify = sub.add_parser("certify")
    certify.add_argument("--pin", type=Path, required=True)
    certify.add_argument("--model", type=Path, required=True)
    certify.add_argument("--server", type=Path, required=True)
    certify.add_argument("--runtime-commit", required=True)
    certify.add_argument("--output", type=Path, required=True)
    trial = sub.add_parser("run")
    trial.add_argument("--workspace", type=Path, required=True)
    trial.add_argument("--pin", type=Path, required=True)
    trial.add_argument("--receipt", type=Path, required=True)
    trial.add_argument("--fixture", type=Path, required=True)
    trial.add_argument("--output", type=Path, required=True)
    scoring = sub.add_parser("score")
    scoring.add_argument("--predictions", type=Path, required=True)
    scoring.add_argument("--fixture", type=Path, required=True)
    scoring.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "certify":
        from marketlab.company_change_store import now_utc
        payload = runtime_receipt(loads_unique(args.pin.read_bytes()), args.model, args.server,
                                  args.runtime_commit, now_utc())
        write_sealed(args.output, payload)
    elif args.mode == "run":
        fixture = loads_unique(args.fixture.read_bytes())
        # Strip labels before selecting or constructing ANY model requests.
        sources = [r["source"] for r in fixture]
        with EvidenceStore(args.workspace) as store:
            payload = run_trial(store, loads_unique(args.pin.read_bytes()),
                                loads_unique(args.receipt.read_bytes()), sources, args.output)
    else:
        payload = score_trial(loads_unique(args.predictions.read_bytes()), loads_unique(args.fixture.read_bytes()))
        writable_workspace(args.output)
        write_sealed(args.output / "score.json", payload)
        (args.output / "score.html").write_text(render(payload), encoding="utf-8")
    print(json.dumps(payload, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
