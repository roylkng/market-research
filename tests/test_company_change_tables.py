from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_tables import (
    METRICS,
    evaluate_corpus,
    extract_statement,
    html_tables,
    main,
    render_replay,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def corpus():
    return json.loads((ROOT / "data/fixtures/company_change_real_v1.json").read_text())


def extract(corpus, source=0, case=0):
    item = corpus["sources"][source]
    item["manifest"]["payload_sha256"] = canonical_hash(item["tables"])
    return extract_statement(item["tables"], item["manifest"], corpus["cases"][case]["selector"], corpus["as_of"])


def row(corpus, label, source=0):
    return next(r for r in corpus["sources"][source]["tables"][1] if r[1] == label)


def test_primary_source_derived_replay(corpus):
    before = copy.deepcopy(corpus)
    report = evaluate_corpus(corpus)
    assert corpus == before
    assert report["status"] == "PASS"
    assert report["counts"] == {"sources": 2, "cases": 3, "checks": 36, "passed_checks": 36, "failed_checks": 0}
    assert report["evaluation_class"] == "SEEN_DEVELOPMENT_REPLAY_NOT_BLIND_ACCURACY"
    assert not report["live_capital_allowed"]
    assert not report["trained_predictor"]
    assert report["report_sha256"] == canonical_hash({k: v for k, v in report.items() if k != "report_sha256"})


def test_period_and_scope_separation(corpus):
    report = evaluate_corpus(corpus)
    quarter, annual = [c["statement"] for c in report["cases"][1:]]
    assert quarter["facts"]["revenue"]["value"] == 1525.5
    assert annual["facts"]["revenue"]["value"] == 6097.86
    assert quarter["facts"]["diluted_eps"]["value"] == 6.79
    assert annual["facts"]["diluted_eps"]["value"] == 28.31
    assert quarter["period_start"] != annual["period_start"]
    assert quarter["facts"]["revenue"]["column"] != annual["facts"]["revenue"]["column"]


def test_equivalent_q1_and_ytd_not_two_independent_observations(corpus):
    statement = extract(corpus)
    assert statement["equivalent_column_count"] == 2
    assert statement["facts"]["revenue"]["value"] == 247.0288


def test_blanks_not_group_profit_not_zero(corpus):
    statement = extract(corpus)
    assert "owner_pat" in statement["missing_fields"]
    assert "owner_pat" not in statement["facts"]
    assert statement["facts"]["reported_pat"]["value"] == 58.9517
    assert statement["bridge"]["normalized_owner_pat_crore"] is None
    assert statement["bridge"]["normalized_owner_eps"] is None


def test_pre_tax_zero_not_proof_of_no_nonrecurring_owner_income(corpus):
    statement = extract(corpus, source=1, case=2)
    assert statement["facts"]["pretax_exceptional_items"]["value"] == 0
    assert statement["facts"]["owner_pat"]["value"] == 648.04
    assert statement["bridge"]["normalized_owner_pat_crore"] is None
    assert statement["bridge"]["normalized_owner_eps"] is None


def test_eps_and_face_value_not_scaled_as_lakhs(corpus):
    statement = extract(corpus)
    assert statement["facts"]["diluted_eps"]["unit"] == "INR_per_share"
    assert statement["facts"]["diluted_eps"]["value"] == 13.57
    assert statement["facts"]["face_value"]["value"] == 5
    assert statement["facts"]["paid_up_capital"]["value"] == 21.7263
    assert "shares" not in statement["facts"]


def test_signed_number_parentheses(corpus):
    row(corpus, "Other income")[2:] = ["(2,267.95)"] * 2
    assert extract(corpus)["facts"]["other_income"]["value"] == -22.6795


@pytest.mark.parametrize("bad", ["NaN", "inf", "1,20,00", "(-1)", "USD 10", "1e4"])
def test_invalid_numeric_literals_fail(corpus, bad):
    row(corpus, "Other income")[2:] = [bad] * 2
    with pytest.raises(ChangeError):
        extract(corpus)


def test_mismatched_duplicate_period_fails(corpus):
    row(corpus, "Revenue from operations")[3] = "99"
    with pytest.raises(ChangeError, match="conflicting columns"):
        extract(corpus)


def test_missing_cell_preserved_not_shifted_to_annual(corpus):
    row(corpus, "Profit or loss, attributable to owners of parent", source=1)[2] = ""
    q = extract(corpus, source=1, case=1)
    annual = extract(corpus, source=1, case=2)
    assert "owner_pat" not in q["facts"]
    assert annual["facts"]["owner_pat"]["value"] == 648.04


def test_repeated_rows_fail(corpus):
    corpus["sources"][0]["tables"][1].append(copy.deepcopy(row(corpus, "Revenue from operations")))
    with pytest.raises(ChangeError, match="ambiguous repeated"):
        extract(corpus)


def test_segment_table_does_not_contaminate_income(corpus):
    corpus["sources"][0]["tables"].append([["Revenue from operations", "99999"]])
    assert extract(corpus)["facts"]["revenue"]["value"] == 247.0288


def test_conflicting_metadata_fails(corpus):
    corpus["sources"][0]["tables"][0].append(["Description of presentation currency", "USD"])
    with pytest.raises(ChangeError, match="conflicting statement context"):
        extract(corpus)


@pytest.mark.parametrize("field,value", [("symbol", "OTHER"), ("isin", "INE001B01026")])
def test_wrong_issuer_never_silently_used(corpus, field, value):
    corpus["sources"][0]["manifest"][field] = value
    with pytest.raises(ChangeError, match="identity"):
        extract(corpus)


def test_wrong_scope_does_not_fallback(corpus):
    corpus["cases"][0]["selector"]["scope"] = "CONSOLIDATED"
    with pytest.raises(ChangeError, match="no exact statement"):
        extract(corpus)


def test_start_date_is_required_not_just_end_date(corpus):
    del corpus["cases"][1]["selector"]["period_start"]
    with pytest.raises(ChangeError, match="selector requires"):
        extract(corpus, 1, 1)


def test_unavailable_source_fails(corpus):
    corpus["as_of"] = "2026-11-06T00:00:00Z"
    with pytest.raises(ChangeError, match="cutoff"):
        extract(corpus)


def test_tampered_table_fails_without_new_hash(corpus):
    corpus["sources"][0]["tables"][1][3][2] = "1"
    with pytest.raises(ChangeError, match="hash"):
        evaluate_corpus(corpus)


def test_unsupported_currency_fails(corpus):
    corpus["sources"][0]["tables"][0][2][1] = "USD"
    with pytest.raises(ChangeError, match="currency"):
        extract(corpus)


def test_evidence_replays_exact_cells_and_context(corpus):
    for case in evaluate_corpus(corpus)["cases"]:
        statement = case["statement"]
        source = next(s for s in corpus["sources"] if s["manifest"]["source_id"] == statement["source_id"])
        for fact in statement["facts"].values():
            assert source["tables"][fact["table"]][fact["row"]][fact["column"]] == fact["literal"]
            for loc in fact["context"].values():
                assert source["tables"][loc["table"]][loc["row"]][loc["column"]] == loc["text"]
            for loc in fact["period_context"].values():
                assert source["tables"][fact["table"]][loc["row"]][loc["column"]] == loc["text"]


def test_changing_gold_changes_score_not_extraction(corpus):
    before = evaluate_corpus(corpus)
    corpus["cases"][0]["expected"]["revenue"] = 1
    after = evaluate_corpus(corpus)
    assert before["cases"][0]["statement"] == after["cases"][0]["statement"]
    assert after["status"] == "FAIL"
    assert after["counts"]["failed_checks"] == 1


def test_unknown_expected_fields_rejected(corpus):
    corpus["cases"][0]["expected"]["future_return"] = .4
    with pytest.raises(ChangeError, match="unsupported"):
        evaluate_corpus(corpus)


def test_unlabelled_extraction_is_not_an_accuracy_success(corpus):
    del corpus["cases"][0]["expected"]["revenue"]
    assert evaluate_corpus(corpus)["counts"]["failed_checks"] == 1


def test_html_preserves_blank_cells():
    assert html_tables(b"<table><tr><td>owners</td><td></td><td>100</td></tr></table>") == [[['owners', '', '100']]]


@pytest.mark.parametrize("body", [b"<table><tr><td colspan='2'>x</td></tr></table>",
                                  b"<table><tr><td rowspan='2'>x</td></tr></table>",
                                  b"<table><tr><td><table><tr><td>x</td></tr></table></td></tr></table>",
                                  b"not a table", b"\xff"])
def test_unsupported_html_layout_fails(body):
    with pytest.raises(ChangeError):
        html_tables(body)


def test_source_derived_html_roundtrip_extracts_same_values(corpus):
    item = corpus["sources"][1]
    import html
    markup = ''.join('<table>' + ''.join('<tr>' + ''.join('<td>' + html.escape(v) + '</td>' for v in r) + '</tr>'
                     for r in t) + '</table>' for t in item['tables'])
    parsed = html_tables(markup.encode())
    assert parsed == item['tables']
    result = extract_statement(parsed, item['manifest'], corpus['cases'][2]['selector'], corpus['as_of'])
    assert result['facts']['revenue']['value'] == 6097.86


def test_report_escapes_html(corpus):
    report = evaluate_corpus(corpus)
    report['cases'][0]['statement']['blockers'].append('<script>alert(1)</script>')
    page = render_replay(report)
    assert '<script>' not in page
    assert '&lt;script&gt;' in page


def test_cli_replay_and_content_addressing(corpus, tmp_path):
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(corpus))
    args = [str(source), '--out', str(tmp_path / 'out')]
    assert main(args) == 0
    assert main(args) == 0
    assert len(list((tmp_path / 'out').glob('*'))) == 2
    next((tmp_path / 'out').glob('*.json')).write_text('tampered')
    assert main(args) == 2


def test_frozen_namespace_refused(corpus, tmp_path):
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(corpus))
    assert main([str(source), '--out', str(tmp_path / 'research' / 'hg009')]) == 2


def test_no_gold_values_embedded_in_extractor_source():
    source = (ROOT / 'src/marketlab/company_change_tables.py').read_text()
    for value in ('247.0288', '6097.86', 'MAYURUNIQ', 'INE001B01026'):
        assert value not in source
    assert len(METRICS) == 12
