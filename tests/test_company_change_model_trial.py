from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_model_trial import (
    file_sha,
    render,
    run_trial,
    runtime_receipt,
    score_trial,
    select_cases,
    validate_pin,
    write_sealed,
)
from marketlab.company_change_news import setup
from marketlab.company_change_store import EvidenceStore

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-11-08T06:00:00Z"


def pin():
    return json.loads((ROOT / "data/cc001/open-model-trial.json").read_text())


def make_reading(store, symbol="SEAMECLTD"):
    capture = store.capture(b"original public issuer disclosure", {"url": "https://issuer.example/source"})
    text = f"{symbol} published an order award. " + "The work is not yet commenced. " * 8
    reading = {"symbol": symbol, "isin": "INE000A01001", "url": "https://issuer.example/source",
               "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
               "raw_sha256": capture["raw_sha256"], "capture_id": capture["id"],
               "known_at": NOW, "published_at": "2026-11-07T10:00:00Z"}
    reading["reading_sha256"] = canonical_hash(reading)
    setup(store)
    store.db.execute("INSERT INTO cc_news_readings VALUES (?,?,?,?,?)",
        (reading["reading_sha256"], symbol, "recipe", NOW, json.dumps(reading)))
    store.db.commit()
    return reading


def source(reading):
    return {k: reading[k] for k in ("symbol", "isin", "url", "raw_sha256", "text_sha256")}


def certify(tmp_path, settings):
    model, server = tmp_path / "model.gguf", tmp_path / "server"
    model.write_bytes(b"test weights, not actual inference")
    server.write_bytes(b"test binary, not actual inference")
    settings["model_bytes"] = model.stat().st_size
    settings["model_sha256"] = file_sha(model)
    return runtime_receipt(settings, model, server, settings["runtime_commit"], NOW)


def sealed(payload, key="report_sha256"):
    return {**payload, key: canonical_hash(payload)}


def test_official_model_and_runtime_are_immutable_and_cpu_bounded():
    value = pin()
    validate_pin(value)
    assert value["model_sha256"] == "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
    assert value["model_bytes"] == 1117320736
    assert value["threads"] <= 4
    assert len(value["case_symbols"]) == 4


@pytest.mark.parametrize("key,value", [("model_revision", "main"), ("runtime_commit", "latest"),
    ("model_sha256", "bad"), ("model_filename", "../model.gguf"), ("threads", 16),
    ("max_output_tokens", True), ("context_tokens", 100000), ("evaluation_scope", "INDEPENDENT_HOLDOUT"),
    ("model_repository", "someone/unknown"), ("case_symbols", ["X", "X"])])
def test_invalid_or_unbounded_pins_fail(key, value):
    settings = pin()
    settings[key] = value
    with pytest.raises(ChangeError):
        validate_pin(settings)


def test_weight_certification_requires_content_and_commit_match(tmp_path):
    settings = pin()
    receipt = certify(tmp_path, settings)
    assert receipt["provider_credentials_required"] is False
    assert receipt["production_activation"] is False
    assert receipt["receipt_sha256"] == canonical_hash({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    with pytest.raises(ChangeError, match="revision"):
        runtime_receipt(settings, tmp_path / "model.gguf", tmp_path / "server", "a" * 40, NOW)
    (tmp_path / "model.gguf").write_bytes(b"t" * settings["model_bytes"])
    with pytest.raises(ChangeError, match="hash"):
        runtime_receipt(settings, tmp_path / "model.gguf", tmp_path / "server", settings["runtime_commit"], NOW)


def test_missing_source_is_retained_in_frozen_denominator(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading = make_reading(store)
        sources = [source(reading), {**source(reading), "symbol": "DHRUV"}]
        cases = select_cases(store, sources, ["SEAMECLTD", "DHRUV"])
        assert len(cases) == 2 and cases[1]["missing"]
        with pytest.raises(ChangeError, match="denominator"):
            select_cases(store, sources[:1], ["SEAMECLTD", "DHRUV"])
        sources[0]["isin"] = "INE000A01002"
        assert select_cases(store, sources, ["SEAMECLTD", "DHRUV"])[0]["missing"]


def test_plan_precedes_generation_labels_excluded_and_no_review_mutation(tmp_path, monkeypatch):
    settings = pin()
    settings["case_symbols"] = ["SEAMECLTD"]
    receipt = certify(tmp_path, settings)
    monkeypatch.setenv("CC001_MODEL_URL", f"http://127.0.0.1:{settings['port']}/v1/chat/completions")
    monkeypatch.setenv("CC001_MODEL_NAME", settings["server_alias"])
    monkeypatch.setenv("CC001_ALLOW_LOCAL_MODEL", "1")
    monkeypatch.delenv("CC001_MODEL_API_KEY", raising=False)
    output = tmp_path / "out"
    calls = []
    with EvidenceStore(tmp_path / "workspace", clock=lambda: NOW) as store:
        reading = make_reading(store)
        def execute(store, record, **kwargs):
            calls.append(record)
            plan = json.loads((output / "plan.json").read_text())
            assert plan["labels_in_requests"] is False
            assert "expected" not in json.dumps(plan)
            assert "category" not in record and "stage" not in record
            assert kwargs["execute"] is True
            response = {"choices": [{"finish_reason": "stop"}], "usage": {"completion_tokens": 250}}
            return {"status": "FAILED_NO_AUTOMATIC_RETRY", "reason": "quote mismatch",
                    "response_blob_sha256": store.put_blob(json.dumps(response).encode()), "model_called": True}
        report = run_trial(store, settings, receipt, [source(reading)], output, executor=execute)
        assert len(calls) == 1
        assert report["source_review_counts_before"] == report["source_review_counts_after"]
        assert report["attempts"][0]["generation"]["completion_tokens"] == 250
        assert (output / "predictions.json").exists()


def test_remote_endpoint_or_credentials_cannot_be_used_for_local_trial(tmp_path, monkeypatch):
    settings = pin()
    receipt = certify(tmp_path, settings)
    with EvidenceStore(tmp_path / "work", clock=lambda: NOW) as store:
        monkeypatch.setenv("CC001_MODEL_API_KEY", "do-not-use")
        with pytest.raises(ChangeError, match="credential"):
            run_trial(store, settings, receipt, [], tmp_path / "out")
        monkeypatch.delenv("CC001_MODEL_API_KEY")
        monkeypatch.setenv("CC001_MODEL_URL", "https://provider.example/v1/chat/completions")
        monkeypatch.setenv("CC001_MODEL_NAME", settings["server_alias"])
        with pytest.raises(ChangeError, match="loopback"):
            run_trial(store, settings, receipt, [], tmp_path / "out")


def scoring_fixture():
    cases, labels = [], []
    event = {"category": "ORDER", "stage": "LETTER_OF_AWARD", "actor_scope": "ISSUER"}
    for name, status in [("A", "PROPOSED"), ("B", "FAILED_NO_AUTOMATIC_RETRY"), ("C", "ABSTAIN"), ("D", "MISSING_SOURCE")]:
        reference = {"symbol": name}
        labels.append({"source": reference, **event})
        cases.append({"symbol": name, "source": reference, "status": status,
                      "proposals": [event] if status == "PROPOSED" else [],
                      "response_blob_sha256": "a" * 64 if status != "MISSING_SOURCE" else None,
                      "generation": {"completion_tokens": 100} if status != "MISSING_SOURCE" else {}})
    return sealed({"attempts": cases, "planned_cases": 4, "evaluation_scope": "SEEN_DEVELOPMENT_CASES_NOT_INDEPENDENT_HOLDOUT"}), labels


def test_failures_abstentions_missing_documents_count_and_never_approve_release():
    predictions, labels = scoring_fixture()
    score = score_trial(predictions, labels)
    assert score["classification_metrics"]["recall"] == .25
    assert score["retained_provider_responses"] == 3
    assert score["cases_with_generated_tokens"] == 3
    assert score["source_validated_proposals"] == 1
    assert not score["measurement_has_all_responses"]
    assert not score["production_model_approved"]
    assert score["release_decision"] == "HOLD_NO_INDEPENDENT_VALIDATION"
    assert score["classification_metrics"]["counts"]["missing_documents"] == 1


def test_no_label_filtering_or_changed_predictions_after_execution():
    predictions, labels = scoring_fixture()
    with pytest.raises(ChangeError, match="denominator"):
        score_trial(predictions, labels[:2])
    predictions["attempts"][0]["status"] = "ABSTAIN"
    with pytest.raises(ChangeError, match="modified"):
        score_trial(predictions, labels)


def test_same_time_all_correct_cannot_approve_unvalidated_model():
    predictions, labels = scoring_fixture()
    for row, label in zip(predictions["attempts"], labels, strict=True):
        row.update(status="PROPOSED", response_blob_sha256="a" * 64,
                   proposals=[{k: label[k] for k in ("category", "stage", "actor_scope")}])
    predictions = sealed({k: v for k, v in predictions.items() if k != "report_sha256"})
    score = score_trial(predictions, labels)
    assert score["classification_metrics"]["recall"] == 1
    assert score["production_model_approved"] is False


def test_sealed_outputs_never_overwrite_changed_run(tmp_path):
    p = tmp_path / "plan.json"
    write_sealed(p, {"cases": [1, 2]})
    write_sealed(p, {"cases": [1, 2]})
    with pytest.raises(ChangeError, match="overwrite"):
        write_sealed(p, {"cases": [1]})


def test_html_escapes_provider_text_and_no_claim_of_independent_accuracy():
    predictions, labels = scoring_fixture()
    score = score_trial(predictions, labels)
    score["cases"][0]["reason"] = "<script>provider text</script>"
    page = render(score)
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert "HOLD" in page and "development sample" in page


def test_isolated_read_only_workflow_executes_actual_local_worker_without_daily_changes():
    path = ROOT / ".github/workflows/cc001-open-model-trial.yml"
    workflow = yaml.safe_load(path.read_text())
    assert workflow["permissions"] == {"contents": "read"}
    text = path.read_text()
    assert "127.0.0.1" in text and "sha256sum --check" in text
    assert "--execute" not in text  # the run mode calls the existing worker explicitly
    assert "company_change_model_trial run" in text
    assert "push origin" not in text and "schedule:" not in text
    assert "unset CC001_MODEL_API_KEY" in text
    assert "cases_with_generated_tokens" in text
    assert workflow["jobs"]["actual-inference-measurement"]["timeout-minutes"] <= 30
