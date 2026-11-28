"""Synthetic evaluator checks. No fixture below is a real company forecast/outcome."""
import copy
import json
import unittest
from pathlib import Path

from calculate import predict_model, score, validate_baseline_bytes


ROOT = Path(__file__).resolve().parent
ORIGINAL = json.loads((ROOT / "../forecast-scale-2026-11-27/forecast_register.json").read_text())
SELECTION = json.loads((ROOT / "selection.json").read_text())


def synthetic_packet():
    cases = []
    for item in SELECTION["attempted"]:
        cases.append({**{k: item[k] for k in ("symbol", "isin", "scope", "target")},
                      "status": "ABSTAIN", "source_valid": False,
                      "source_review_status": "SYNTHETIC_TEST_ONLY",
                      "abstention_reason": "Deliberate test of retained denominator",
                      "verified_pat_cr": dict.fromkeys(("q1", "q2", "prior_q2", "prior_q3")),
                      "sources": [], "model": None})
    for c in cases[:2]:
        c.update(status="FORECAST", source_valid=True,
                 verified_pat_cr={"q1": 4., "q2": 8., "prior_q2": 5., "prior_q3": 7.},
                 normalization_adjustments_cr={"q1": 0., "q2": -1., "prior_q2": 2., "prior_q3": 1.},
                 normalization_basis="Explicit synthetic one-off adjustment",
                 sources=[{"url": "https://example.com/synthetic-only", "publication_date": "2026-11-01",
                           "observed_at_utc": "2026-11-28T00:00:00Z", "status": "SYNTHETIC_TEST_ONLY"}],
                 model={"kind": "pbt_margin", "revenue_cr": 100., "pbt_margin": .20,
                        "exceptional_pretax_cr": 0., "tax_rate": .25, "nci_cr": 1.,
                        "associates_after_tax_cr": 2.})
    cases[1]["verified_pat_cr"]["prior_q2"] = None
    cases[1]["verified_pat_cr"]["prior_q3"] = None
    return {"research_date_ist": "2026-11-28", "evidence_cutoff_utc": "2026-11-28T01:00:00Z",
            "target_period_end": "2026-12-31", "cases": cases, "actuals": [], "ratio_denominator_floor_cr": 1.}


def actual(index=0, pat=10.):
    item = SELECTION["attempted"][index]
    return {**{k: item[k] for k in ("symbol", "isin", "scope", "target")},
            "period_end": "2026-12-31", "actual_pat_cr": pat, "unit": "INR_CRORE",
            "first_release_date": "2027-01-15", "reviewed_at_utc": "2027-01-15T18:00:00Z",
            "source_url": "https://example.com/synthetic-outcome",
            "source_review_status": "FIRST_REPORTED_QUARTER_SOURCE_CHECKED"}


class SupplementalEvaluatorTests(unittest.TestCase):
    def test_pinned_original_bytes_enforced(self):
        original_bytes = (ROOT / "../forecast-scale-2026-11-27/forecast_register.json").read_bytes()
        self.assertEqual(validate_baseline_bytes(original_bytes, {}, SELECTION), SELECTION["baseline_sha256"])
        with self.assertRaises(ValueError):
            validate_baseline_bytes(original_bytes+b"\n", {}, SELECTION)
        with self.assertRaises(ValueError):
            validate_baseline_bytes(original_bytes, {"original_register_sha256": "0"*64}, SELECTION)
        with self.assertRaises(ValueError):
            validate_baseline_bytes(original_bytes, {}, {**SELECTION, "baseline_sha256": None})

    def test_published_scenarios_all_reproduce_and_order_explicit(self):
        p = synthetic_packet()
        case = p["cases"][0]
        case["scenario_order"] = ["adverse", "base", "favorable"]
        case["scenarios"] = {}
        for name, revenue, expected in [("adverse", 80., 13.), ("base", 100., 16.), ("favorable", 120., 19.)]:
            model = {**case["model"], "revenue_cr": revenue}
            case["scenarios"][name] = {"model": model, "forecast_pat_cr": expected}
        result = score(p, ORIGINAL, SELECTION)
        self.assertEqual(result["rows"][0]["scenario_calculations"]["adverse"]["owner_pat_cr"], 13.)
        bad = copy.deepcopy(p)
        bad["cases"][0]["scenarios"]["adverse"]["forecast_pat_cr"] = 99.
        with self.assertRaises(ValueError):
            score(bad, ORIGINAL, SELECTION)
        bad = copy.deepcopy(p)
        del bad["cases"][0]["scenario_order"]
        with self.assertRaises(ValueError):
            score(bad, ORIGINAL, SELECTION)
        bad = copy.deepcopy(p)
        bad["cases"][0]["scenarios"]["adverse"]["model"]["revenue_cr"] = 200.
        bad["cases"][0]["scenarios"]["adverse"]["forecast_pat_cr"] = 31.
        with self.assertRaises(ValueError):
            score(bad, ORIGINAL, SELECTION)
        bad = copy.deepcopy(p)
        bad["cases"][0]["scenarios"]["base"]["model"]["tax_rate"] = .3
        bad["cases"][0]["scenarios"]["base"]["forecast_pat_cr"] = 15.
        with self.assertRaises(ValueError):
            score(bad, ORIGINAL, SELECTION)

    def test_null_outcomes_and_retained_denominators(self):
        result = score(synthetic_packet(), ORIGINAL, SELECTION)
        self.assertEqual(result["coverage"]["attempted"], 12)
        self.assertEqual(result["coverage"]["assisted_forecasted"], 2)
        self.assertEqual(result["coverage"]["abstained"], 10)
        self.assertEqual(result["coverage"]["attempted_actuals_missing"], 12)
        self.assertEqual(result["primary_comparison"]["available_pairs"], 1)
        self.assertIsNone(result["primary_comparison"]["mean_lhs_scaled_abs"])
        self.assertTrue(all(r["actual"] is None and r["errors"] is None for r in result["rows"]))

    def test_partial_outcomes_use_identical_pairs_and_original_scale(self):
        # Include an outcome for an abstained name. It must stay in coverage,
        # while neither manufacturing a model forecast nor diluting model error.
        result = score(synthetic_packet(), ORIGINAL, SELECTION, [actual(), actual(2, 7)], "2027-02-01T00:00:00Z")
        self.assertEqual(result["coverage"]["attempted_actuals_observed"], 2)
        self.assertEqual(result["coverage"]["assisted_actuals_observed"], 1)
        self.assertEqual(result["primary_comparison"]["matured_pairs"], 1)
        row = result["rows"][0]
        frozen = next(p for p in ORIGINAL["predictions"] if p["isin"] == row["isin"])
        self.assertEqual(row["original_scale_cr"], frozen["scale_cr"])
        self.assertAlmostEqual(row["errors"]["assisted_driver"]["scaled_abs"], 6/frozen["scale_cr"])
        self.assertAlmostEqual(row["errors"]["normalized_seasonal_additive"]["scaled_abs"], 2/frozen["scale_cr"])
        self.assertEqual(result["primary_comparison"]["losses"], 1)
        self.assertEqual(row["forecasts"]["frozen_latest_quarter"], frozen["forecasts"]["latest_quarter"])

    def test_tax_associates_nci_and_signed_pbt_components(self):
        operating = {"kind": "operating", "revenue_cr": 100., "ebit_margin": .2,
                     "other_income_cr": 5., "finance_cost_cr": 3., "exceptional_pretax_cr": -2.,
                     "tax_rate": .25, "nci_cr": 1., "associates_after_tax_cr": 2.}
        self.assertEqual(predict_model(operating)["owner_pat_cr"], 16.)
        components = {"kind": "pbt_components", "components": [{"name": "A", "amount_cr": 25}, {"name": "B", "amount_cr": -5}],
                      "tax_rate": .25, "nci_cr": 1., "associates_after_tax_cr": 2.}
        self.assertEqual(predict_model(components)["owner_pat_cr"], 16.)

    def test_invalid_and_future_release_dates_rejected(self):
        for replacement in ("2027-99-99", "2027-02-29", "20270115", "2026-12-31", "2099-01-01"):
            with self.subTest(replacement=replacement):
                a = actual()
                a["first_release_date"] = replacement
                with self.assertRaises(ValueError):
                    score(synthetic_packet(), ORIGINAL, SELECTION, [a], "2027-02-01T00:00:00Z")
        with self.assertRaises(ValueError):
            score(synthetic_packet(), ORIGINAL, SELECTION, [actual()])

    def test_duplicate_wrong_identity_units_and_unreviewed_actual_rejected(self):
        a = actual()
        bad_sets = [[a, copy.deepcopy(a)]]
        for key, value in [("scope", "WRONG"), ("isin", "WRONG"), ("unit", "INR_LAKH"),
                           ("source_review_status", "UNREVIEWED"), ("actual_pat_cr", True),
                           ("reviewed_at_utc", "2027-01-14T18:00:00Z")]:
            b = copy.deepcopy(a)
            b[key] = value
            bad_sets.append([b])
        for bad in bad_sets:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                score(synthetic_packet(), ORIGINAL, SELECTION, bad, "2027-02-01T00:00:00Z")

    def test_failed_source_and_unreproduced_prediction_rejected(self):
        p = synthetic_packet()
        p["cases"][0]["source_valid"] = False
        with self.assertRaises(ValueError):
            score(p, ORIGINAL, SELECTION)
        p = synthetic_packet()
        p["cases"][0]["sources"][0]["observed_at_utc"] = "2026-11-29T00:00:00Z"
        with self.assertRaises(ValueError):
            score(p, ORIGINAL, SELECTION)
        p = synthetic_packet()
        p["cases"][0]["forecast_pat_cr"] = 99
        with self.assertRaises(ValueError):
            score(p, ORIGINAL, SELECTION)

    def test_missing_seasonality_and_small_denominator_are_abstentions(self):
        p = synthetic_packet()
        p["cases"][0]["verified_pat_cr"]["prior_q2"] = .1
        p["cases"][0]["normalization_adjustments_cr"]["prior_q2"] = 0
        result = score(p, ORIGINAL, SELECTION)
        self.assertIsNone(result["rows"][0]["forecasts"]["raw_yoy_trend"])
        self.assertIsNone(result["rows"][0]["forecasts"]["normalized_yoy_trend"])
        self.assertIsNone(result["rows"][1]["forecasts"]["seasonal_additive"])
        self.assertIsNotNone(result["rows"][1]["forecasts"]["latest_verified_quarter"])

    def test_no_replacement_or_missing_attempt_allowed(self):
        p = synthetic_packet()
        p["cases"].pop()
        with self.assertRaises(ValueError):
            score(p, ORIGINAL, SELECTION)
        s = copy.deepcopy(SELECTION)
        s["attempted"][0], s["attempted"][1] = s["attempted"][1], s["attempted"][0]
        with self.assertRaises(ValueError):
            score(synthetic_packet(), ORIGINAL, s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
