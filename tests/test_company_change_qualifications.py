from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_news import setup
from marketlab.company_change_qualifications import (
    PROVENANCE,
    covered,
    diagnose,
    main,
    render,
    validate_manifest,
)
from marketlab.company_change_store import EvidenceStore

NOW = "2026-11-08T08:00:00Z"
TEXT = ("EXAMPLE LIMITED signed the purchase agreement. "
        "The cover says the subsidiary was acquired. "
        "The annexure says completion will occur next week. "
        "Payment is conditional and has not been confirmed.")


def seal(report):
    report.pop("report_sha256", None)
    report["report_sha256"] = canonical_hash(report)
    return report


def span(quote):
    start = TEXT.index(quote)
    return {"start": start, "end": start + len(quote), "quote": quote}


def sample(root):
    with EvidenceStore(root, clock=lambda: NOW) as store:
        setup(store)
        capture = store.capture(b"exact original disclosure", {"url": "https://issuer.test/source.pdf"})
        reading = {"symbol": "TEST", "isin": "INE000A01001", "url": "https://issuer.test/source.pdf",
                   "raw_sha256": capture["raw_sha256"], "text_sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
                   "text": TEXT, "capture_id": capture["id"], "known_at": NOW,
                   "published_at": "2026-11-07T10:00:00Z"}
        reading["reading_sha256"] = canonical_hash(reading)
        store.db.execute("INSERT INTO cc_news_readings VALUES (?,?,?,?,?)",
                         (reading["reading_sha256"], "candidate", "recipe", NOW, json.dumps(reading)))
        store.db.commit()
    source = {k: reading[k] for k in ("symbol", "isin", "url", "raw_sha256", "text_sha256")}
    proposal = {"source": source, "category": "ACQUISITION", "stage": "COMPLETED", "actor_scope": "ISSUER",
                "interpretation": "This interpretation is intentionally wrong despite citing the full text.",
                "next_check": "No automatic approval is permitted by the diagnostic.",
                "claims": [{"field": field, "start": 0, "end": len(TEXT), "quote": TEXT}
                           for field in ("event", "stage", "actor")]}
    predictions = seal({"model_key": "test", "as_of": NOW, "planned_cases": 1,
                        "attempts": [{"source": source, "reading_sha256": reading["reading_sha256"],
                                      "status": "PROPOSED", "proposals": [proposal]}]})
    manifest = {"schema_version": 1, "provenance": PROVENANCE, "author": "test-author",
                "independent_labels": False, "requirements_selected_after_predictions": True,
                "cases": [{"source": source, "requirements": [{"id": "completion-conflict",
                    "dimension": "COMPLETION_STATUS", "reviewer_interpretation": "Both conflicting statements must be retained.",
                    "spans": [span("The cover says the subsidiary was acquired."),
                              span("The annexure says completion will occur next week.")]}]}]}
    return predictions, manifest, reading


def test_complete_citation_coverage_never_certifies_wrong_interpretation(tmp_path):
    p, m, _ = sample(tmp_path)
    result = diagnose(tmp_path, p, m)
    assert result["required_passage_coverage"] == 1
    assert result["model_output_approved"] is False
    assert result["live_capital_allowed"] is False
    assert result["cases"][0]["requirements"][0]["interpretation_entailment"] == "NOT_EVALUATED"
    assert result["counts"]["documents_with_all_passages_selected"] == 1
    assert result["requirements_selected_after_predictions"] is True


def test_counterevidence_requires_both_sides_not_just_optimistic_sentence(tmp_path):
    p, m, _ = sample(tmp_path)
    for c in p["attempts"][0]["proposals"][0]["claims"]:
        c.update(span("The cover says the subsidiary was acquired."))
    result = diagnose(tmp_path, seal(p), m)
    assert result["required_passage_coverage"] == 0
    assert [s["present_in_selected_evidence"] for s in result["cases"][0]["requirements"][0]["spans"]] == [True, False]


def test_ranges_join_exactly_without_bridging_missing_characters():
    assert covered((20, 40), [(0, 30), (30, 45)])
    assert not covered((20, 40), [(0, 29), (30, 45)])
    assert not covered((20, 40), [(21, 40)])
    assert not covered((20, 40), [])
    assert covered((20, 40), [(0, 100)])


@pytest.mark.parametrize("status", ["ABSTAIN", "FAILED_NO_AUTOMATIC_RETRY", "MISSING_SOURCE", "RUNNING"])
def test_failed_or_abstaining_predictions_never_vanish_from_denominator(tmp_path, status):
    p, m, _ = sample(tmp_path)
    p["attempts"][0]["status"] = status
    result = diagnose(tmp_path, seal(p), m)
    assert result["counts"]["requirements"] == 1
    assert result["required_passage_coverage"] == 0
    assert result["cases"][0]["model_interpretations"] == []


def test_missing_prediction_is_counted_not_silently_excluded(tmp_path):
    p, m, _ = sample(tmp_path)
    p["attempts"] = []
    result = diagnose(tmp_path, seal(p), m)
    assert result["counts"]["missing_predictions"] == 1
    assert result["counts"]["requirements"] == 1
    assert result["required_passage_coverage"] == 0


def test_read_only_access_and_deterministic_output(tmp_path):
    p, m, _ = sample(tmp_path)
    before = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in tmp_path.rglob("*") if f.is_file()}
    original_p, original_m = copy.deepcopy(p), copy.deepcopy(m)
    first = diagnose(tmp_path, p, m)
    assert first == diagnose(tmp_path, p, m)
    assert p == original_p and m == original_m
    after = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in tmp_path.rglob("*") if f.is_file()}
    assert before == after


@pytest.mark.parametrize("fault", ["raw", "reading", "prediction", "required_quote", "boolean_offset"])
def test_corrupted_evidence_does_not_produce_a_report(tmp_path, fault):
    p, m, r = sample(tmp_path)
    if fault == "raw":
        sha = r["raw_sha256"]
        (tmp_path / "blobs" / sha[:2] / sha).write_bytes(b"changed")
    elif fault == "reading":
        with EvidenceStore(tmp_path) as store:
            r["text"] += "changed"
            store.db.execute("UPDATE cc_news_readings SET payload=?", (json.dumps(r),))
            store.db.commit()
    elif fault == "prediction":
        p["attempts"][0]["status"] = "ABSTAIN"
    elif fault == "required_quote":
        m["cases"][0]["requirements"][0]["spans"][0]["quote"] = "Invented original statement"
    else:
        m["cases"][0]["requirements"][0]["spans"][0]["start"] = True
    with pytest.raises(ChangeError):
        diagnose(tmp_path, p, m)


@pytest.mark.parametrize("fault", ["source", "attempt", "requirement", "independent", "prospective", "denominator"])
def test_invalid_annotation_or_case_accounting_is_rejected(tmp_path, fault):
    p, m, _ = sample(tmp_path)
    if fault == "source":
        m["cases"] *= 2
    elif fault == "attempt":
        p["attempts"] *= 2
        seal(p)
    elif fault == "requirement":
        m["cases"][0]["requirements"] *= 2
    elif fault == "independent":
        m["independent_labels"] = True
    elif fault == "prospective":
        m["requirements_selected_after_predictions"] = False
    else:
        p["planned_cases"] = 0
        seal(p)
    with pytest.raises(ChangeError):
        diagnose(tmp_path, p, m)


def test_wrong_identity_or_future_evidence_is_blocked(tmp_path):
    p, m, _ = sample(tmp_path)
    p["attempts"][0]["source"] = {**p["attempts"][0]["source"], "symbol": "OTHER"}
    with pytest.raises(ChangeError):
        diagnose(tmp_path, seal(p), m)
    p, m, _ = sample(tmp_path / "future")
    p["as_of"] = "2026-11-07T23:00:00Z"
    with pytest.raises(ChangeError, match="cutoff"):
        diagnose(tmp_path / "future", seal(p), m)


def test_no_wrong_source_claims_can_count_as_coverage(tmp_path):
    p, m, _ = sample(tmp_path)
    p["attempts"][0]["proposals"][0]["source"] = {**p["attempts"][0]["source"], "symbol": "OTHER"}
    with pytest.raises(ChangeError):
        diagnose(tmp_path, seal(p), m)


def test_cli_and_escaped_rendering(tmp_path):
    root = tmp_path / "evidence"
    p, m, _ = sample(root)
    m["cases"][0]["requirements"][0]["reviewer_interpretation"] = "<script>untrusted interpretation</script>"
    pred, manifest = tmp_path / "p.json", tmp_path / "m.json"
    pred.write_text(json.dumps(p))
    manifest.write_text(json.dumps(m))
    output = tmp_path / "exports/diagnostic"
    assert main(["--workspace", str(root), "--predictions", str(pred), "--requirements", str(manifest), "--output-prefix", str(output)]) == 0
    result = json.loads(output.with_suffix(".json").read_text())
    page = render(result)
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert result["model_output_approved"] is False


def test_real_checklist_is_explicitly_retrospective_not_a_new_holdout():
    path = Path(__file__).resolve().parents[1] / "data/fixtures/company_change_critical_qualifications.json"
    manifest = json.loads(path.read_text())
    cases = validate_manifest(manifest)
    assert len(cases) == 4
    assert sum(len(c["requirements"]) for c in cases) == 12
    assert manifest["requirements_selected_after_predictions"]
    assert manifest["independent_labels"] is False


def test_active_uncheckpointed_journal_is_not_silently_ignored(tmp_path):
    p, m, _ = sample(tmp_path)
    with EvidenceStore(tmp_path) as store:
        store.db.execute("INSERT INTO attempts(recorded_at,source_id,status,detail) VALUES (?,?,?,?)",
                         (NOW, "test", "test", "new committed WAL data"))
        store.db.commit()
        with pytest.raises(ChangeError, match="checkpoint snapshot"):
            diagnose(tmp_path, p, m)
