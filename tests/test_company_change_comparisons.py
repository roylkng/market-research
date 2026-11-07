from __future__ import annotations

import copy
import json
from datetime import date

import pytest

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_comparisons import (
    build_comparisons,
    comparative,
    delta,
    full_months,
    main,
    render_comparisons,
    shift_months,
)
from marketlab.company_change_store import EvidenceStore


def record(start, end, revenue, pbt, *, scope="CONSOLIDATED", raw="a" * 64):
    fields = {"revenue": revenue, "pbt": pbt, "reported_pat": pbt * 0.75,
              "other_income": 1.0, "pretax_exceptional_items": 0.0}
    facts = {k: {"value": v, "unit": "INR_crore"} for k, v in fields.items()}
    facts["diluted_eps"] = {"value": 7.25, "unit": "INR_per_share"}
    facts["paid_up_capital"] = {"value": 10, "unit": "INR_crore"}
    return {"symbol": "TEST", "isin": "INE000A01001", "kind": "earnings_quality",
            "selector": {"period_start": start, "period_end": end, "scope": scope},
            "raw_sha256": raw, "extraction_id": canonical_hash([start, end, scope, raw]),
            "source_id": "source", "url": "https://example.test/filing.xml",
            "facts": facts, "warnings": [], "known_at": "2026-11-07T10:00:00Z",
            "review_status": "UNREVIEWED"}


def dataset():
    # Quarterly revenue rises from 100 to 120, margin rises from 10% to 15%.
    rows = [record("2026-07-01", "2026-09-30", 120, 18),
            record("2026-04-01", "2026-09-30", 220, 28)]
    snapshot = {"as_of": "2026-11-07T11:00:00Z", "active": rows}
    snapshot["snapshot_sha256"] = canonical_hash(snapshot)
    return snapshot


def test_same_source_additive_flows_never_eps_or_shares():
    report = build_comparisons(dataset())
    card = report["cards"][0]
    assert card["sequential"]["method"] == "DERIVED_HALF_YEAR_MINUS_CURRENT_QUARTER"
    assert card["metrics"]["revenue"]["previous"] == 100
    assert card["metrics"]["revenue"]["growth_fraction"] == pytest.approx(0.20)
    assert card["metrics"]["pbt_margin"]["change_pp"] == 5
    assert card["derived_prior_quarter_eps"] is None
    assert card["sequential"]["diluted_eps"] is None
    assert "diluted_eps" not in card["sequential"]["values"]
    assert "paid_up_capital" not in card["sequential"]["values"]
    assert card["sequential"]["equations"]["revenue"]["result"] == 100
    assert card["attention"] == "REPORTED_IMPROVEMENT_REVIEW"
    assert report["validated_predictive_edge"] is False
    assert report["live_capital_allowed"] is False
    assert any("unreviewed" in s for s in card["blockers"])


def test_direct_comparison_preferred_and_year_ago_is_exact():
    snapshot = dataset()
    snapshot["active"].append(record("2026-04-01", "2026-06-30", 99, 9))
    snapshot["active"].append(record("2025-07-01", "2025-09-30", 80, 8))
    card = build_comparisons(snapshot)["cards"][0]
    assert card["sequential"]["method"] == "DIRECT_SAME_DISCLOSURE"
    assert card["metrics"]["revenue"]["previous"] == 99
    assert card["year_ago"]["selector"]["period_end"] == "2025-09-30"
    assert card["year_ago_metrics"]["revenue"]["growth_fraction"] == 0.5


@pytest.mark.parametrize("field,new", [("raw_sha256", "b" * 64), ("isin", "INE000A01002"), ("symbol", "OTHER")])
def test_cannot_join_different_source_or_issuer(field, new):
    snapshot = dataset()
    snapshot["active"][1][field] = new
    card = next(c for c in build_comparisons(snapshot)["cards"] if c["symbol"] == "TEST" and c["current"])
    assert card["sequential"]["method"] == "UNAVAILABLE"
    assert card["metrics"]["revenue"]["growth_fraction"] is None


def test_cannot_mix_standalone_and_consolidated():
    snapshot = dataset()
    snapshot["active"][1]["selector"]["scope"] = "STANDALONE"
    cards = build_comparisons(snapshot)["cards"]
    assert len(cards) == 2
    assert all(c["attention"] == "INSUFFICIENT_COMPARISON" for c in cards)


def test_no_quarter_from_nine_months_or_partial_months():
    snapshot = dataset()
    snapshot["active"][1]["selector"]["period_start"] = "2026-01-01"
    assert build_comparisons(snapshot)["cards"][0]["sequential"]["method"] == "UNAVAILABLE"
    snapshot = dataset()
    snapshot["active"][0]["selector"]["period_start"] = "2026-07-02"
    assert build_comparisons(snapshot)["cards"][0]["current"] is None


def test_no_annualizing_latest_half_year_only():
    snapshot = dataset()
    snapshot["active"] = snapshot["active"][1:]
    card = build_comparisons(snapshot)["cards"][0]
    assert card["current"] is None
    assert "annualization" in card["blockers"][0]


def test_no_silent_missing_to_zero_conversion():
    snapshot = dataset()
    del snapshot["active"][1]["facts"]["revenue"]
    card = build_comparisons(snapshot)["cards"][0]
    assert card["metrics"]["revenue"]["previous"] is None
    assert card["metrics"]["revenue"]["growth_fraction"] is None
    assert card["metrics"]["pbt_margin"]["previous_pct"] is None
    assert card["sequential"]["values"]["owner_pat"] is None


@pytest.mark.parametrize("previous", [0, -1, -100])
def test_nonpositive_base_never_becomes_growth_percentage(previous):
    result = delta(10, previous)
    assert result["growth_fraction"] is None
    assert result["absolute_change"] == 10 - previous


@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_invalid_numbers_fail(value):
    snapshot = dataset()
    snapshot["active"][0]["facts"]["revenue"]["value"] = value
    with pytest.raises(ChangeError):
        build_comparisons(snapshot)


def test_units_and_future_information_fail():
    snapshot = dataset()
    snapshot["active"][1]["facts"]["revenue"]["unit"] = "INR_lakh"
    with pytest.raises(ChangeError, match="units"):
        build_comparisons(snapshot)
    snapshot = dataset()
    snapshot["active"][1]["known_at"] = "2026-11-08T00:00:00Z"
    with pytest.raises(ChangeError, match="future"):
        build_comparisons(snapshot)


def test_later_source_clock_is_preserved_for_derivation():
    snapshot = dataset()
    snapshot["active"][1]["known_at"] = "2026-11-07T10:30:00Z"
    card = build_comparisons(snapshot)["cards"][0]
    assert card["sequential"]["known_at"] == "2026-11-07T10:30:00+00:00"


@pytest.mark.parametrize("fault", ["REJECT", "warning"])
def test_rejected_or_inconsistent_evidence_cannot_be_improvement_label(fault):
    snapshot = dataset()
    if fault == "REJECT":
        snapshot["active"][1]["review_status"] = "REJECT"
    else:
        snapshot["active"][0]["warnings"].append("Owner plus minority profit fails reconciliation.")
    card = build_comparisons(snapshot)["cards"][0]
    assert card["attention"] == "ACCOUNTING_REVIEW_REQUIRED"
    assert card["live_capital_allowed"] is False


def test_exceptional_profit_and_other_income_are_not_normalized():
    snapshot = dataset()
    facts = snapshot["active"][0]["facts"]
    facts["pretax_exceptional_items"]["value"] = 2
    facts["other_income"]["value"] = 20
    card = build_comparisons(snapshot)["cards"][0]
    assert "OTHER_INCOME_AT_LEAST_REPORTED_PBT" in card["flags"]
    assert "PRETAX_EXCEPTIONAL_ITEM_PRESENT" in card["flags"]
    assert card["metrics"]["pbt"]["current"] == 18
    assert any("recurring owner" in b for b in card["blockers"])


def test_duplicate_quarters_and_ambiguous_prefix_fail():
    snapshot = dataset()
    snapshot["active"].append(copy.deepcopy(snapshot["active"][0]))
    with pytest.raises(ChangeError, match="ambiguous"):
        build_comparisons(snapshot)
    snapshot = dataset()
    snapshot["active"].append(copy.deepcopy(snapshot["active"][1]))
    with pytest.raises(ChangeError, match="ambiguous"):
        build_comparisons(snapshot)


def test_month_boundaries_include_leap_year_and_january():
    assert shift_months(date(2024, 3, 31), -1) == date(2024, 2, 29)
    assert full_months({"period_start": "2024-01-01", "period_end": "2024-03-31"}, 3)
    q = record("2026-01-01", "2026-03-31", 120, 12)
    previous = record("2025-10-01", "2025-12-31", 100, 10)
    assert comparative(q, [q, previous], year_ago=False)["selector"]["period_end"] == "2025-12-31"


def test_renderer_escapes_source_and_does_not_accept_review():
    report = build_comparisons(dataset())
    report["cards"][0]["symbol"] = "<script>bad</script>"
    page = render_comparisons(report)
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "<form" not in page
    assert "not buy recommendations" in page


def test_comparison_is_deterministic_and_does_not_mutate_input():
    snapshot = dataset()
    original = copy.deepcopy(snapshot)
    first = build_comparisons(snapshot)
    assert build_comparisons(snapshot) == first
    assert snapshot == original
    assert first["report_sha256"] == canonical_hash({k: v for k, v in first.items() if k != "report_sha256"})


def test_empty_store_cli_exports_research_report(tmp_path, capsys):
    with EvidenceStore(tmp_path / "workspace"):
        pass
    output = tmp_path / "exports/changes"
    assert main(["--workspace", str(tmp_path / "workspace"), "--output-prefix", str(output)]) == 0
    report = json.loads(output.with_suffix(".json").read_text())
    assert report["counts"]["issuers"] == 0
    assert output.with_suffix(".html").exists()
    assert report["live_capital_allowed"] is False
    capsys.readouterr()


def test_overlapping_direct_periods_must_reconcile_before_improvement():
    snapshot = dataset()
    snapshot["active"].append(record("2026-04-01", "2026-06-30", 10, 1))
    card = build_comparisons(snapshot)["cards"][0]
    assert card["sequential"]["method"] == "DIRECT_SAME_DISCLOSURE"
    assert card["attention"] == "ACCOUNTING_REVIEW_REQUIRED"
    assert any("do not sum" in b for b in card["blockers"])


def test_negative_derived_revenue_requires_accounting_review():
    snapshot = dataset()
    snapshot["active"][1]["facts"]["revenue"]["value"] = 50
    card = build_comparisons(snapshot)["cards"][0]
    assert card["metrics"]["revenue"]["previous"] == -70
    assert card["metrics"]["revenue"]["growth_fraction"] is None
    assert card["attention"] == "ACCOUNTING_REVIEW_REQUIRED"


def test_unsafe_source_link_and_future_period_rejected():
    snapshot = dataset()
    snapshot["active"][0]["url"] = "javascript:alert(1)"
    with pytest.raises(ChangeError):
        build_comparisons(snapshot)
    snapshot = dataset()
    snapshot["active"][0]["selector"]["period_end"] = "2026-12-31"
    with pytest.raises(ChangeError, match="observation"):
        build_comparisons(snapshot)


def test_daily_workflow_retains_comparison_exports():
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/cc001-daily-operations.yml").read_text())
    steps = workflow["jobs"]["refresh-research-workspace"]["steps"]
    export = next(s["run"] for s in steps if s.get("name") == "Export research desk and checkpoint durable state")
    assert "python -m marketlab.company_change_comparisons" in export
    assert "business-changes.json business-changes.html" in export
    upload = next(s for s in steps if s.get("uses") == "actions/upload-artifact@v4")
    assert "business-changes.json" in upload["with"]["path"]
    assert "business-changes.html" in upload["with"]["path"]
    assert "--limit 40" in next(s["run"] for s in steps if s.get("id") == "intake")
