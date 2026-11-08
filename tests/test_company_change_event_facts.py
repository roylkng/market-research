from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_event_facts import (
    REQUIRED,
    admit,
    compile_state,
    order_scenarios,
    reduce_assertions,
    states,
    validate,
)
from marketlab.company_change_fact_desk import build_report, main, render
from marketlab.company_change_news import setup
from marketlab.company_change_store import EvidenceStore

NOW = "2026-11-08T12:00:00Z"
TEXT = ("TEST LIMITED and its partner consortium received a letter of award.\n"
        "The amount for TEST LIMITED's own scope is USD 26.14 million exclusive of GST.\n"
        "Commencement will be intimated later.\n"
        "The transaction is completed.\n"
        "The transaction will complete next week.\n"
        "The investor has paid its contribution.\n"
        "The contribution has not yet been paid.\n")


def span(quote):
    start = TEXT.index(quote)
    return {"start": start, "end": start + len(quote), "quote": quote}


def observation(value, quote):
    return {"value": value, "evidence": [span(quote)]}


def case(store):
    setup(store)
    cap = store.capture(b"original bytes", {"url": "https://issuer.example/notice.pdf"})
    reading = {"symbol": "TEST", "isin": "INE000A01001", "url": "https://issuer.example/notice.pdf",
               "raw_sha256": cap["raw_sha256"], "text_sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
               "capture_id": cap["id"], "text": TEXT, "known_at": NOW,
               "published_at": "2026-11-07T14:00:00Z"}
    reading["reading_sha256"] = canonical_hash(reading)
    store.db.execute("INSERT INTO cc_news_readings VALUES (?,?,?,?,?)",
                     (reading["reading_sha256"], "candidate", "recipe", NOW, json.dumps(reading)))
    store.db.commit()
    source = {k: reading[k] for k in ("symbol", "isin", "url", "raw_sha256", "text_sha256")}
    award = "TEST LIMITED and its partner consortium received a letter of award."
    amount = "The amount for TEST LIMITED's own scope is USD 26.14 million exclusive of GST."
    obs = {k: [] for k in REQUIRED["ORDER"]}
    obs["legal_recipient"] = [observation("CONSORTIUM", award)]
    obs["award"] = [observation("AWARDED", award)]
    obs["operations"] = [observation("COMMENCEMENT_UNCONFIRMED", "Commencement will be intimated later.")]
    proposal = {"source": source, "event_key": "test-contract", "category": "ORDER", "observations": obs,
                "amounts": [{"id": "contract", "purpose": "CONTRACT_VALUE", "literal": "USD 26.14 million",
                             "evidence": [span(amount)], "owner": [observation("ISSUER_SCOPE", amount)],
                             "qualifiers": [observation("EXCLUDES_GST", amount)]}],
                "next_checks": ["Establish incremental margin, funding and collections before a valuation decision."]}
    return reading, proposal


def plan(source):
    return {"source_raw_sha256": source["raw_sha256"], "event_key": "test-contract", "amount_id": "contract",
            "rationale": "Illustrative assumptions, not a supported earnings forecast or actual FX rate.",
            "scenarios": [{"name": "Illustrative", "fx_inr_per_currency_unit": 85,
                "issuer_fraction": 1, "not_in_baseline_fraction": 1, "after_tax_cash_margin": .10,
                "additional_capex_crore": 0, "working_capital_crore": 0,
                "working_capital_recovery_fraction": 1, "cash_receipt_months": 12, "discount_rate": .15}]}


def test_recipient_and_amount_ownership_are_not_the_same_field(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, proposal = case(store)
        records = admit(store, [proposal], "assistant-source-review")
        state = compile_state(records, NOW)
        assert state["facts"]["legal_recipient"]["value"] == "CONSORTIUM"
        assert state["amounts"][0]["owner"]["value"] == "ISSUER_SCOPE"
        assert state["facts"]["payment"]["status"] == "UNKNOWN"
        assert state["facts"]["completion"]["status"] == "UNKNOWN"
        assert state["facts"]["signing"]["status"] == "UNKNOWN"
        assert state["facts"]["operations"]["value"] == "COMMENCEMENT_UNCONFIRMED"
        result = order_scenarios(state, plan(reading))
        assert result["scenarios"][0]["finite_incremental_npv_crore"] == pytest.approx(22.219 / 1.15)
        assert result["recognized_revenue"] is None and result["collected_cash"] is None
        assert result["per_share_value"] is None and not result["buy_approved"]


def test_payment_conflict_does_not_erase_incorporation_or_imply_operations(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        p["category"] = "ACQUISITION"
        p["observations"] = {k: [] for k in REQUIRED["ACQUISITION"]}
        p["observations"]["payment"] = [observation("PAID", "The investor has paid its contribution."),
                                           observation("PENDING", "The contribution has not yet been paid.")]
        p["observations"]["incorporation"] = [observation("INCORPORATED", "The transaction is completed.")]
        p["amounts"] = []
        record = admit(store, [p], "explicit-test-review")
        state = compile_state(record, NOW)
        assert state["facts"]["payment"]["status"] == "CONFLICT"
        assert state["facts"]["payment"]["value"] is None
        assert state["facts"]["incorporation"]["value"] == "INCORPORATED"
        assert state["facts"]["operations"]["status"] == "UNKNOWN"
        report = build_report(store)
        assert report["dossiers"][0]["decision"]["research_action"] == "RECONCILE_SOURCE_FIRST"
        # Exact citations do not prove the reviewer's chosen semantic value.
        assert not state["independently_verified"] and not state["model_accuracy_claimed"]


def test_append_only_reviews_cannot_vote_away_contradictory_statement(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        p["observations"]["completion"] = [observation("COMPLETED", "The transaction is completed.")]
        first = admit(store, [p], "reviewer-one")
        p["observations"]["completion"] = [observation("PENDING", "The transaction will complete next week.")]
        second = admit(store, [p], "reviewer-two")
        p["observations"]["completion"] = [observation("COMPLETED", "The transaction is completed.")]
        admit(store, [p], "reviewer-three")
        result = states(store, NOW)[0]
        assert result["facts"]["completion"]["status"] == "CONFLICT"
        assert compile_state(first + second, NOW)["facts"] == compile_state(second + first, NOW)["facts"]
        assert len(result["review_ids"]) == 3
        with pytest.raises(ChangeError, match="conflicted"):
            order_scenarios(result, plan(p["source"]))


def test_duplicate_admission_is_idempotent_and_original_financial_tables_unchanged(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, p = case(store)
        first = admit(store, [p], "assistant-source-review")
        assert first == admit(store, [p], "assistant-source-review")
        assert len(states(store, NOW)) == 1
        assert store.read_blob(reading["raw_sha256"]) == b"original bytes"
        for table in ("extractions", "reviews", "decisions"):
            assert store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        assert store.db.execute("SELECT COUNT(*) FROM cc_event_fact_reviews").fetchone()[0] == 1


@pytest.mark.parametrize("field", ["symbol", "isin", "url", "raw_sha256", "text_sha256"])
def test_cross_source_reviews_rejected(tmp_path, field):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        p["source"][field] = "other"
        with pytest.raises(ChangeError, match="unavailable"):
            admit(store, [p], "reviewer")


@pytest.mark.parametrize("fault", ["missing_question", "invalid_value", "boolean_offset", "wrong_quote",
                                   "extra_field", "duplicate_assertion", "duplicate_amount", "substring_amount"])
def test_invalid_or_incomplete_review_rejected(tmp_path, fault):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, p = case(store)
        if fault == "missing_question":
            p["observations"].pop("payment")
        elif fault == "invalid_value":
            p["observations"]["operations"][0]["value"] = "GUARANTEED_REVENUE"
        elif fault == "boolean_offset":
            p["observations"]["award"][0]["evidence"][0]["start"] = True
        elif fault == "wrong_quote":
            p["amounts"][0]["owner"][0]["evidence"][0]["quote"] = "invented ownership"
        elif fault == "extra_field":
            p["target_price"] = 9999
        elif fault == "duplicate_assertion":
            p["observations"]["award"] *= 2
        elif fault == "duplicate_amount":
            p["amounts"] *= 2
        else:
            p["amounts"][0]["literal"] = "USD 26"
        with pytest.raises(ChangeError):
            validate(reading, p)


def test_batch_validation_is_atomic(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        other = copy.deepcopy(p)
        other["event_key"] = "another"
        other["observations"]["payment"] = None
        with pytest.raises(ChangeError):
            admit(store, [p, other], "reviewer")
        assert store.db.execute("SELECT COUNT(*) FROM cc_event_fact_reviews").fetchone()[0] == 0


def test_unknown_owner_and_consortium_scope_cannot_be_assumed_issuer_specific(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        p["amounts"][0]["owner"] = []
        state = compile_state(admit(store, [p], "reviewer"), NOW)
        with pytest.raises(ChangeError, match="owner unresolved"):
            order_scenarios(state, plan(p["source"]))


def test_amount_inconsistent_across_reviews_is_conflict_not_last_value_wins(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        admit(store, [p], "reviewer-one")
        p["amounts"][0]["purpose"] = "SUBSCRIPTION_CONSIDERATION"
        admit(store, [p], "reviewer-two")
        state = states(store, NOW)[0]
        assert state["amounts"][0]["status"] == "CONFLICT"
        assert state["amounts"][0]["amount_units"] is None
        with pytest.raises(ChangeError):
            order_scenarios(state, plan(p["source"]))


def test_no_double_consortium_allocation_or_fake_recurring_value(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        state = compile_state(admit(store, [p], "reviewer"), NOW)
        scenarios = plan(p["source"])
        scenarios["scenarios"][0]["issuer_fraction"] = .5
        with pytest.raises(ChangeError, match="second time"):
            order_scenarios(state, scenarios)
        scenarios["scenarios"][0]["issuer_fraction"] = 1
        scenarios["scenarios"][0]["exit_pe"] = 15
        with pytest.raises(ChangeError):
            order_scenarios(state, scenarios)


def test_future_review_and_source_mutation_fail(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, p = case(store)
        records = admit(store, [p], "reviewer")
        with pytest.raises(ChangeError, match="cutoff"):
            compile_state(records, "2026-11-07T20:00:00Z")
        assert states(store, "2026-11-07T20:00:00Z") == []
        sha = reading["raw_sha256"]
        (store.root / "blobs" / sha[:2] / sha).write_bytes(b"tampered")
        with pytest.raises(ChangeError, match="integrity"):
            states(store, NOW)


def test_model_proposal_and_tampered_record_cannot_be_compiled(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        records = admit(store, [p], "reviewer")
        records[0]["review_status"] = "MODEL_PROPOSED_NOT_APPROVED"
        with pytest.raises(ChangeError):
            compile_state(records, NOW)
        row = store.db.execute("SELECT id,payload FROM cc_event_fact_reviews").fetchone()
        record = json.loads(row[1])
        record["category"] = "CREDIT"
        store.db.execute("UPDATE cc_event_fact_reviews SET payload=? WHERE id=?", (json.dumps(record), row[0]))
        store.db.commit()
        with pytest.raises(ChangeError, match="integrity"):
            states(store, NOW)


def test_original_schema_or_event_revisions_never_merge_silently(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        first = admit(store, [p], "reviewer")
        p["event_key"] = "different-event"
        second = admit(store, [p], "reviewer")
        with pytest.raises(ChangeError, match="mix"):
            compile_state(first + second, NOW)
        assert len(states(store, NOW)) == 2


def test_cli_actual_review_export_and_economic_blocker(tmp_path, capsys):
    root = tmp_path / "workspace"
    with EvidenceStore(root, clock=lambda: NOW) as store:
        _, p = case(store)
    package = tmp_path / "package.json"
    package.write_text(json.dumps([p]))
    output = tmp_path / "exports/review"
    assert main(["--workspace", str(root), "--package", str(package), "--reviewer", "assistant-source-review",
                 "--output-prefix", str(output)]) == 0
    report = json.loads(output.with_suffix(".json").read_text())
    assert report["counts"]["source_events"] == 1
    assert not report["model_called"]
    assert report["dossiers"][0]["price_timing"]["status"] == "NO_PRICE"
    assert output.with_suffix(".html").exists()
    with pytest.raises(ChangeError, match="together"):
        main(["--workspace", str(root), "--package", str(package), "--output-prefix", str(output)])
    assert capsys.readouterr().out


def test_unmatched_plan_is_visible_and_invalid_scenario_does_not_drop_source(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        admit(store, [p], "reviewer")
        scenarios = plan(p["source"])
        scenarios["event_key"] = "absent"
        result = build_report(store, [scenarios])
        assert len(result["dossiers"]) == 1 and len(result["unmatched_plan_keys"]) == 1
        scenarios["event_key"] = p["event_key"]
        scenarios["scenarios"][0]["issuer_fraction"] = .5
        result = build_report(store, [scenarios])
        assert result["dossiers"][0]["economic_use_blocker"]
        assert result["dossiers"][0]["hypothetical_economics"] is None


def test_html_source_content_is_escaped(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, p = case(store)
        p["next_checks"] = ["<script>Source text must not execute in a review page.</script>"]
        admit(store, [p], "reviewer")
        page = render(build_report(store))
        assert "<script>Source text" not in page
        assert "&lt;script&gt;Source text" in page
        assert 'id="filter"' in page and 'id="search"' in page


def test_unknown_is_not_a_negative_or_automatic_completion():
    assert reduce_assertions([]) == {"status": "UNKNOWN", "value": None, "alternatives": [], "evidence": []}
    assert reduce_assertions([{"value": "PAID"}, {"value": "PENDING"}])["status"] == "CONFLICT"


def test_development_fixture_preserves_real_source_qualifications():
    root = Path(__file__).resolve().parents[1]
    fixtures = json.loads((root / "data/fixtures/company_change_fact_reviews.json").read_text())
    assert {p["source"]["symbol"] for p in fixtures} == {"SEAMECLTD", "DHRUV", "VIKRAN", "PRESTIGE"}
    by = {p["source"]["symbol"]: p for p in fixtures}
    assert {v["value"] for v in by["DHRUV"]["observations"]["payment"]} == {"PAID", "PENDING"}
    assert {v["value"] for v in by["PRESTIGE"]["observations"]["completion"]} == {"COMPLETED", "PENDING"}
    assert by["VIKRAN"]["observations"]["credit_grade"][0]["value"] == "REAFFIRMED"
    assert by["VIKRAN"]["observations"]["credit_outlook"][0]["value"] == "NEGATIVE"
    assert by["SEAMECLTD"]["amounts"][0]["owner"][0]["value"] == "ISSUER_SCOPE"


def test_source_workflow_is_bounded_isolated_and_never_executes_a_model():
    root = Path(__file__).resolve().parents[1]
    text = (root / '.github/workflows/cc001-fact-review-smoke.yml').read_text()
    assert 'contents: read' in text
    assert 'schedule:' not in text and 'push origin' not in text
    assert 'company_change_fact_desk' in text
    assert 'company_change_semantics --execute' not in text
    assert "table_counts(store)==" in text
    assert 'timeout-minutes: 12' in text


def test_empty_nonlist_plans_are_not_silently_treated_as_no_plan(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store, pytest.raises(ChangeError, match="plans"):
        build_report(store, {})
