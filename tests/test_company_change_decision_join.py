from __future__ import annotations

import json
from pathlib import Path

from marketlab.company_change_pipeline import ingest, record_decision
from marketlab.company_change_store import EvidenceStore

ROOT = Path(__file__).resolve().parents[1]


def test_persistent_decision_does_not_ignore_later_issuance(tmp_path):
    demo = json.loads((ROOT / "data/fixtures/company_change_v1.json").read_text())
    records = [demo["sources"][0], demo["sources"][6]]
    specs = []
    for index, source in enumerate(records):
        filename = f"source-{index}.txt"
        (tmp_path / filename).write_text(source["text"])
        spec = {k: source[k] for k in ("source_id", "url", "isin", "kind", "event_key",
                                      "scope", "period_start", "period_end", "rights")}
        spec.update(symbol="DEMOGROW", local_file=filename, format="text", extractor="labels")
        specs.append(spec)
    manifest = {"schema_version": 1, "sources": specs[:1]}
    with EvidenceStore(tmp_path / "workspace", clock=lambda: "2026-11-07T10:00:00Z") as store:
        first = ingest(manifest, store, base=tmp_path)
        assert not first["failures"]
        store.review(first["successes"][0]["extraction_id"], "test-reviewer", "ACCEPT", "Fixture review")
        before = record_decision(store, demo["valuations"][0])
        assert before["illustrative_disposition"] == "REVIEW_CANDIDATE"
        manifest["sources"] = specs[1:]
        second = ingest(manifest, store, base=tmp_path)
        assert not second["failures"]
        after = record_decision(store, demo["valuations"][0])
        assert after["disposition"] == "WAIT"
        assert any("capital events" in b for b in after["blockers"])
        assert after["live_capital_allowed"] is False
